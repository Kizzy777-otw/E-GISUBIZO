"""Idempotent import for the Rwanda biogas installation workbook."""

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select

from .database import SessionLocal
from .models import AuditLog, HardwareUnit

DEFAULT_WORKBOOK = Path(
    r"C:\Users\Pc\Downloads\Rwanda Total Installations-2026-11-19-20-07-45.xlsx"
)
CONTRACT_PATTERN = re.compile(r"^HBGC-\d{5}$")
OWNER_ID_PATTERN = re.compile(r"\s*\[[0-9]+\]\s*$")


def text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def parse_owner_name(value: object) -> str | None:
    name = text(value)
    if name is None:
        return None
    return OWNER_ID_PATTERN.sub("", name).strip() or None


def parse_source_reported_at(workbook) -> datetime | None:
    sheet = workbook.active
    for row in sheet.iter_rows(min_row=1, max_row=8, max_col=12, values_only=True):
        for value in row:
            value_text = text(value)
            if value_text:
                match = re.search(r"As of (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", value_text)
                if match:
                    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return None


def parse_installation_workbook(path: str | Path) -> list[dict]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Rwanda Total Installations"]
    source_reported_at = parse_source_reported_at(workbook)
    installation_year: str | None = None
    records: list[dict] = []

    for row in sheet.iter_rows(min_row=19, max_col=17, values_only=True):
        year_value = text(row[1])
        if year_value and year_value.startswith("CY"):
            installation_year = year_value
            continue

        contract = text(row[7])
        if contract is None:
            continue
        contract = contract.upper()
        if not CONTRACT_PATTERN.fullmatch(contract):
            continue

        county = text(row[9])
        constituency = text(row[10])
        if county is None or constituency is None:
            continue

        sales_person = text(row[16]) or text(row[15])
        records.append(
            {
                "hardware_id": contract,
                "model_type": "biogas",
                "district": county,
                "sector": constituency,
                "account_name": text(row[5]),
                "owner_name": parse_owner_name(row[6]),
                "hub": text(row[8]),
                "county": county,
                "constituency": constituency,
                "village": text(row[11]),
                "appraisal_status": text(row[3]),
                "commissioning_status": text(row[4]),
                "contract_status": text(row[12]),
                "payment_format": text(row[13]),
                "lead_source": text(row[14]),
                "sales_person": sales_person,
                "installation_year": installation_year,
                "source_reported_at": source_reported_at,
            }
        )

    workbook.close()
    if len({record["hardware_id"] for record in records}) != len(records):
        raise ValueError("The workbook contains duplicate HBGC contract numbers.")
    return records


def import_records(records: list[dict], actor_user_id: int | None = None) -> tuple[int, int]:
    inserted = 0
    updated = 0
    with SessionLocal() as db:
        for record in records:
            unit = db.get(HardwareUnit, record["hardware_id"])
            if unit is None:
                unit = HardwareUnit(**record)
                db.add(unit)
                inserted += 1
            else:
                for field, value in record.items():
                    if field != "hardware_id" and getattr(unit, field) != value:
                        setattr(unit, field, value)
                updated += 1
        db.flush()
        db.add(
            AuditLog(
                actor_user_id=actor_user_id,
                event_type="INSTALLATION_REGISTRY_IMPORTED",
                details={
                    "inserted": inserted,
                    "updated": updated,
                    "total": len(records),
                    "source": "Rwanda Total Installations workbook",
                },
            )
        )
        db.commit()
    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_WORKBOOK))
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    records = parse_installation_workbook(args.path)
    if args.report_only:
        print(f"Validated {len(records)} installations; no database changes made.")
        return

    inserted, updated = import_records(records)
    print(f"Imported {len(records)} installations: {inserted} inserted, {updated} updated.")


if __name__ == "__main__":
    main()
