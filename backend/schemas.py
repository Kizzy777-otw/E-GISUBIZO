"""Pydantic request and response models."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


HardwareType = Literal["biogas", "solar"]
TicketStatus = Literal["Open", "InProgress", "Resolved", "Closed"]
TicketPriority = Literal["Low", "Medium", "High", "Urgent"]


def normalize_hardware_id(value: str) -> str:
    # Store serial IDs in one canonical form so lookup and de-duplication agree.
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,79}", normalized):
        raise ValueError("Use 3–80 letters, numbers, or hyphens for the hardware ID.")
    return normalized


class HardwareValidationRequest(BaseModel):
    hardware_id: str
    model_type: HardwareType

    @field_validator("hardware_id")
    @classmethod
    def clean_hardware_id(cls, value: str) -> str:
        return normalize_hardware_id(value)


class HardwareRegistrationRequest(HardwareValidationRequest):
    district: str = Field(min_length=1, max_length=100)
    sector: str = Field(min_length=1, max_length=100)

    @field_validator("district", "sector")
    @classmethod
    def clean_zone_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("District and sector cannot be blank.")
        return normalized


class HardwareUnitResponse(BaseModel):
    hardware_id: str
    model_type: HardwareType
    district: str
    sector: str

    model_config = ConfigDict(from_attributes=True)


class HardwareValidationResponse(HardwareUnitResponse):
    valid: Literal[True] = True


class DiagnosticTreeResponse(BaseModel):
    slug: str
    appliance_type: HardwareType
    version: int
    content: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class DiagnosticTreeUpdate(BaseModel):
    appliance_type: HardwareType
    version: int = Field(ge=1)
    content: dict[str, Any]
    active: bool = True


class FaultCodePayload(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{3,64}$")
    category: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=500)


class DiagnosticStep(BaseModel):
    node_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=300)
    answer_id: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=200)


class TicketSyncItem(BaseModel):
    client_ticket_id: str = Field(pattern=r"^[a-fA-F0-9-]{36}$")
    hardware_id: str
    model_type: HardwareType
    priority: TicketPriority
    fault_category: str = Field(min_length=2, max_length=120)
    fault_code: FaultCodePayload
    diagnostic_path: list[DiagnosticStep] = Field(min_length=1, max_length=12)

    @field_validator("hardware_id")
    @classmethod
    def clean_hardware_id(cls, value: str) -> str:
        return normalize_hardware_id(value)


class TicketSyncRequest(BaseModel):
    # Bound batch size to keep sync requests manageable on low-bandwidth links.
    tickets: list[TicketSyncItem] = Field(min_length=1, max_length=100)


class TicketSyncResult(BaseModel):
    client_ticket_id: str
    result: Literal["synced", "already_synced", "rejected"]
    ticket_id: int | None = None
    message: str | None = None


class TicketSyncResponse(BaseModel):
    results: list[TicketSyncResult]
    synced: int
    rejected: int


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    note: str | None = Field(default=None, max_length=500)


class TicketResponse(BaseModel):
    id: int
    client_ticket_id: str
    hardware_id: str
    model_type: HardwareType
    status: TicketStatus
    priority: TicketPriority
    fault_category: str
    fault_code: dict[str, Any]
    diagnostic_path: list[dict[str, Any]]
    requires_technician: bool
    district: str
    sector: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationRequest(BaseModel):
    ticket_id: int


class NotificationResponse(BaseModel):
    status: Literal["logged"] = "logged"
    ticket_id: int
    message: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    district: str | None
    sector: str | None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class UserCreateRequest(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    role: Literal["technician", "admin"]
    district: str | None = Field(default=None, max_length=100)
    sector: str | None = Field(default=None, max_length=100)

    @field_validator("district", "sector")
    @classmethod
    def normalize_optional_zone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UserCreatedResponse(UserResponse):
    # This plaintext token is returned only once; the database stores its hash.
    access_token: str


class UserAccessUpdate(BaseModel):
    active: bool
