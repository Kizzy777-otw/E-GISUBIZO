"""Hardware registry validation and administrator registration routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, HardwareUnit, User
from ..schemas import (
    HardwareRegistrationRequest,
    HardwareUnitResponse,
    HardwareValidationRequest,
    HardwareValidationResponse,
)
from .auth import require_role

router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/validate", response_model=HardwareValidationResponse)
def validate_hardware(payload: HardwareValidationRequest, db: DatabaseSession) -> HardwareUnit:
    # Require both serial and declared model to match before exposing any diagnostics.
    unit = db.scalar(select(HardwareUnit).where(HardwareUnit.hardware_id == payload.hardware_id))
    if unit is None:
        raise HTTPException(status_code=404, detail="This hardware ID is not in the registered unit list.")
    if unit.model_type != payload.model_type:
        raise HTTPException(
            status_code=422,
            detail=f"This hardware ID is registered as {unit.model_type}, not {payload.model_type}.",
        )
    return unit


@router.post("", response_model=HardwareUnitResponse, status_code=201)
def register_hardware(
    payload: HardwareRegistrationRequest,
    db: DatabaseSession,
    admin: Annotated[User, Depends(require_role("admin"))],
) -> HardwareUnit:
    if db.get(HardwareUnit, payload.hardware_id) is not None:
        raise HTTPException(status_code=409, detail="That hardware ID is already registered.")
    unit = HardwareUnit(
        hardware_id=payload.hardware_id,
        model_type=payload.model_type,
        district=payload.district.strip(),
        sector=payload.sector.strip(),
    )
    db.add(unit)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            event_type="HARDWARE_REGISTERED",
            details={
                "hardware_id": unit.hardware_id,
                "model_type": unit.model_type,
                "district": unit.district,
                "sector": unit.sector,
            },
        )
    )
    db.commit()
    db.refresh(unit)
    return unit
