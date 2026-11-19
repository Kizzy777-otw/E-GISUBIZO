"""Smoke tests for the public and role-protected API behavior."""

import json
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.database import should_create_schema, validate_database_configuration
from backend.schemas import DiagnosticTreeUpdate
from backend.import_installations import parse_installation_workbook
from backend.seed import DIAGNOSTIC_TREES

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}
TECHNICIAN_HEADERS = {"Authorization": "Bearer test-technician-token"}


def test_diagnostic_trees_are_seeded(api_client: TestClient) -> None:
    assert api_client.get("/").status_code == 200
    assert api_client.get("/sw.js").status_code == 200
    assert api_client.get("/healthz").json() == {"status": "ok"}
    for seed_tree in DIAGNOSTIC_TREES:
        DiagnosticTreeUpdate.model_validate(
            {
                "appliance_type": seed_tree["appliance_type"],
                "version": seed_tree["version"],
                "content": seed_tree["content"],
            }
        )

    response = api_client.get("/api/v1/diagnostic-trees")

    assert response.status_code == 200
    trees = response.json()
    assert {tree["slug"] for tree in trees} == {"biogas-low-flame", "solar-red-indicator"}


def test_installation_workbook_parser(tmp_path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rwanda Total Installations"
    sheet["B3"] = "As of 2026-11-19 20:07:45 Greenwich Mean Time/GMT"
    sheet["D18"] = "Appraisal status"
    sheet["E18"] = "Commissioning Status"
    sheet["F18"] = "Account Name"
    sheet["G18"] = "Full Name"
    sheet["H18"] = "HBG Contract Name"
    sheet["I18"] = "HBG Hub"
    sheet["J18"] = "County"
    sheet["K18"] = "Constituency"
    sheet["L18"] = "Village"
    sheet["M18"] = "Contract Status"
    sheet["N18"] = "Payment Format"
    sheet["O18"] = "Lead Source"
    sheet["Q18"] = "Sales Person"
    sheet["B19"] = "CY2026"
    sheet.append([None, None, None, "Done", "Done", "Homestead Test [Village]", "Test Owner [1190000000000000]", "HBGC-99999", "Rwanda - Eastern Province", "Eastern Province - Gatsibo", "Gatsibo Test", "Test Village", "Fulfilled", "UNDP", "Feasibility/Baseline Survey", None, "Test Sales [123]"])

    path = tmp_path / "installations.xlsx"
    workbook.save(path)

    records = parse_installation_workbook(path)

    assert len(records) == 1
    assert records[0]["hardware_id"] == "HBGC-99999"
    assert records[0]["owner_name"] == "Test Owner"
    assert records[0]["village"] == "Test Village"
    assert records[0]["installation_year"] == "CY2026"


def test_admin_hardware_registry_includes_metadata(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/hardware", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    units = response.json()
    assert any(unit["hardware_id"] == "HBGC-00001" for unit in units)


def test_password_login_for_seeded_admin_and_wrong_password(api_client: TestClient) -> None:
    valid = api_client.post(
        "/api/v1/auth/login",
        json={"username": "administrator", "password": "test-admin-password"},
    )
    invalid = api_client.post(
        "/api/v1/auth/login",
        json={"username": "administrator", "password": "wrong-password"},
    )

    assert valid.status_code == 200
    assert valid.json()["user"]["role"] == "admin"
    assert valid.json()["access_token"]
    assert invalid.status_code == 401

    session_headers = {"Authorization": f"Bearer {valid.json()['access_token']}"}
    assert api_client.get("/api/v1/auth/me", headers=session_headers).status_code == 200
    assert api_client.post("/api/v1/auth/logout", headers=session_headers).json()["status"] == "logged_out"
    assert api_client.get("/api/v1/auth/me", headers=session_headers).status_code == 401


def test_admin_password_user_creation(api_client: TestClient) -> None:
    payload = {
        "username": "field-admin",
        "password": "field-admin-password",
        "role": "admin",
        "district": None,
        "sector": None,
    }
    created = api_client.post("/api/v1/users", json=payload, headers=ADMIN_HEADERS)

    assert created.status_code == 201
    login = api_client.post(
        "/api/v1/auth/login",
        json={"username": "field-admin", "password": "field-admin-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"


def test_diagnostic_tree_update_rejects_more_than_three_questions(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/diagnostic-trees")
    tree = next(item for item in response.json() if item["slug"] == "biogas-low-flame")
    nodes = {
        f"question_{index}": {
            "type": "question",
            "question": f"Question {index}?",
            "answers": [{"id": "next", "label": "Next", "next": f"question_{index + 1}"}],
        }
        for index in range(1, 5)
    }
    nodes["question_5"] = {"type": "resolution", "title": "Finished"}
    update = api_client.put(
        "/api/v1/diagnostic-trees/biogas-low-flame",
        headers=ADMIN_HEADERS,
        json={
            "appliance_type": "biogas",
            "version": tree["version"] + 1,
            "active": True,
            "content": {"start_node": "question_1", "nodes": nodes},
        },
    )

    assert update.status_code == 422


def test_diagnostic_tree_update_requires_a_higher_version(api_client: TestClient) -> None:
    tree = next(
        item
        for item in api_client.get("/api/v1/diagnostic-trees").json()
        if item["slug"] == "biogas-low-flame"
    )
    response = api_client.put(
        "/api/v1/diagnostic-trees/biogas-low-flame",
        headers=ADMIN_HEADERS,
        json={
            "appliance_type": tree["appliance_type"],
            "version": tree["version"],
            "active": True,
            "content": tree["content"],
        },
    )

    assert response.status_code == 422


def test_deployed_environment_disables_metadata_schema_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DB_AUTO_CREATE", raising=False)
    assert should_create_schema() is False

    monkeypatch.setenv("DB_AUTO_CREATE", "true")
    with pytest.raises(RuntimeError, match="use Alembic"):
        should_create_schema()

    monkeypatch.delenv("DB_AUTO_CREATE")
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        validate_database_configuration()


def test_offline_assets_and_tree_payload_stay_under_one_megabyte() -> None:
    root = Path(__file__).resolve().parents[1]
    service_worker = (root / "frontend" / "sw.js").read_text(encoding="utf-8")
    asset_list = re.search(r"const APP_ASSETS = \[(.*?)\];", service_worker, re.DOTALL)
    assert asset_list is not None
    assets = re.findall(r'"([^"]+)"', asset_list.group(1))
    cached_bytes = sum(
        (root / "frontend" / ("index.html" if path == "/" else path.lstrip("/"))).stat().st_size
        for path in assets
    )
    cached_tree_response = [
        {
            "slug": tree["slug"],
            "appliance_type": tree["appliance_type"],
            "version": tree["version"],
            "content": tree["content"],
        }
        for tree in DIAGNOSTIC_TREES
    ]
    tree_bytes = len(
        json.dumps(cached_tree_response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )

    assert cached_bytes + tree_bytes <= 1_000_000


def test_hardware_validation_normalizes_biogas_contract_and_checks_model(api_client: TestClient) -> None:
    valid_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": " hbgc-00001 ", "model_type": "biogas"},
    )
    wrong_model_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": "HBGC-00001", "model_type": "solar"},
    )
    invalid_contract_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": "BIO-RW-0001", "model_type": "biogas"},
    )
    unknown_unit_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": "HBGC-99999", "model_type": "biogas"},
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["hardware_id"] == "HBGC-00001"
    assert valid_response.json()["valid"] is True
    assert wrong_model_response.status_code == 422
    assert invalid_contract_response.status_code == 422
    assert unknown_unit_response.status_code == 404


def test_hardware_registration_requires_admin_and_rejects_duplicates(
    api_client: TestClient,
) -> None:
    payload = {
        "hardware_id": "test-unit-0001",
        "model_type": "solar",
        "district": "Kigali",
        "sector": "Gasabo",
    }
    invalid_biogas_payload = {
        "hardware_id": "BIO-RW-0001",
        "model_type": "biogas",
        "district": "Kigali",
        "sector": "Gasabo",
    }

    assert api_client.post("/api/v1/hardware", json=payload).status_code == 401
    assert (
        api_client.post(
            "/api/v1/hardware",
            json=invalid_biogas_payload,
            headers=ADMIN_HEADERS,
        ).status_code
        == 422
    )
    assert (
        api_client.post(
            "/api/v1/hardware",
            json=payload,
            headers=TECHNICIAN_HEADERS,
        ).status_code
        == 403
    )

    created_response = api_client.post(
        "/api/v1/hardware",
        json=payload,
        headers=ADMIN_HEADERS,
    )
    duplicate_response = api_client.post(
        "/api/v1/hardware",
        json=payload,
        headers=ADMIN_HEADERS,
    )

    assert created_response.status_code == 201
    assert created_response.json()["hardware_id"] == "TEST-UNIT-0001"
    assert duplicate_response.status_code == 409


def test_ticket_sync_rejects_legacy_biogas_contract(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/tickets/sync",
        json={
            "tickets": [
                {
                    "client_ticket_id": "d85f1202-994d-4c50-a1aa-dbbbe8161997",
                    "hardware_id": "BIO-RW-0001",
                    "model_type": "biogas",
                    "priority": "High",
                    "fault_category": "Test fault",
                    "fault_code": {
                        "code": "TEST_FAULT",
                        "category": "Test fault",
                        "description": "A test fault description.",
                    },
                    "diagnostic_path": [
                        {
                            "node_id": "start",
                            "question": "Did the system start?",
                            "answer_id": "yes",
                            "answer": "Yes",
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["rejected"] == 1
    assert response.json()["results"][0]["result"] == "rejected"


def test_dispatch_api_requires_staff_and_preserves_ticket_diagnostic_path(
    api_client: TestClient,
) -> None:
    assert api_client.get("/api/v1/tickets").status_code == 401
    assert (
        api_client.post("/api/v1/notifications/sms-trigger", json={"ticket_id": 1}).status_code
        == 401
    )
    diagnostic_path = [
        {
            "node_id": "panel_check",
            "question": "Is the panel shaded?",
            "answer_id": "yes",
            "answer": "Yes",
        }
    ]
    sync_response = api_client.post(
        "/api/v1/tickets/sync",
        json={
            "tickets": [
                {
                    "client_ticket_id": "d85f1202-994d-4c50-a1aa-dbbbe8161998",
                    "hardware_id": "SOL-RW-0001",
                    "model_type": "solar",
                    "priority": "High",
                    "fault_category": "Panel obstruction",
                    "fault_code": {
                        "code": "SOLAR_PANEL_OBSTRUCTION",
                        "category": "Panel obstruction",
                        "description": "Possible shading or dirt.",
                    },
                    "diagnostic_path": diagnostic_path,
                }
            ]
        },
    )
    assert sync_response.status_code == 200
    ticket_id = sync_response.json()["results"][0]["ticket_id"]

    ticket_list = api_client.get("/api/v1/tickets", headers=TECHNICIAN_HEADERS)
    ticket = next(item for item in ticket_list.json() if item["id"] == ticket_id)
    assert ticket["diagnostic_path"] == diagnostic_path
    assert ticket["requires_technician"] is True
    assert not {"phone", "phone_number", "contact_number"} & ticket.keys()
    assert (
        api_client.patch(
            f"/api/v1/tickets/{ticket_id}/status",
            json={"status": "InProgress"},
        ).status_code
        == 401
    )
    updated = api_client.patch(
        f"/api/v1/tickets/{ticket_id}/status",
        headers=TECHNICIAN_HEADERS,
        json={"status": "InProgress"},
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "InProgress"
    assert updated.json()["diagnostic_path"] == diagnostic_path
    assert (
        api_client.post(
            "/api/v1/notifications/sms-trigger",
            headers=TECHNICIAN_HEADERS,
            json={"ticket_id": ticket_id},
        ).status_code
        == 200
    )
