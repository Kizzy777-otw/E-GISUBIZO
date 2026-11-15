"""Smoke tests for the public and role-protected API behavior."""

from fastapi.testclient import TestClient


ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}
TECHNICIAN_HEADERS = {"Authorization": "Bearer test-technician-token"}


def test_diagnostic_trees_are_seeded(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/diagnostic-trees")

    assert response.status_code == 200
    trees = response.json()
    assert {tree["slug"] for tree in trees} == {"biogas-low-flame", "solar-red-indicator"}


def test_hardware_validation_normalizes_id_and_checks_model(api_client: TestClient) -> None:
    valid_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": " bio-rw-0001 ", "model_type": "biogas"},
    )
    wrong_model_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": "BIO-RW-0001", "model_type": "solar"},
    )
    unknown_unit_response = api_client.post(
        "/api/v1/hardware/validate",
        json={"hardware_id": "UNKNOWN-0001", "model_type": "biogas"},
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["hardware_id"] == "BIO-RW-0001"
    assert valid_response.json()["valid"] is True
    assert wrong_model_response.status_code == 422
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

    assert api_client.post("/api/v1/hardware", json=payload).status_code == 401
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
