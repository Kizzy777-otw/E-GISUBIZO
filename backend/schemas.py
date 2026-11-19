"""Pydantic request and response models."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HardwareType = Literal["biogas", "solar"]
TicketStatus = Literal["Open", "InProgress", "Resolved", "Closed"]
TicketPriority = Literal["Low", "Medium", "High", "Urgent"]


def normalize_hardware_id(value: str) -> str:
    # Store serial IDs in one canonical form so lookup and de-duplication agree.
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,79}", normalized):
        raise ValueError("Use 3–80 letters, numbers, or hyphens for the hardware ID.")
    return normalized


def hardware_id_matches_model(hardware_id: str, model_type: HardwareType) -> bool:
    return model_type != "biogas" or re.fullmatch(r"HBGC-\d{5}", hardware_id) is not None


def validate_hardware_id_for_model(hardware_id: str, model_type: HardwareType) -> None:
    if not hardware_id_matches_model(hardware_id, model_type):
        raise ValueError("Biogas contract numbers must use the format HBGC-00001.")


class HardwareValidationRequest(BaseModel):
    hardware_id: str
    model_type: HardwareType

    @field_validator("hardware_id")
    @classmethod
    def clean_hardware_id(cls, value: str) -> str:
        return normalize_hardware_id(value)

    @model_validator(mode="after")
    def validate_model_hardware_id(self) -> "HardwareValidationRequest":
        validate_hardware_id_for_model(self.hardware_id, self.model_type)
        return self


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


class HardwareUnitAdminResponse(HardwareUnitResponse):
    account_name: str | None = None
    owner_name: str | None = None
    hub: str | None = None
    county: str | None = None
    constituency: str | None = None
    village: str | None = None
    appraisal_status: str | None = None
    commissioning_status: str | None = None
    contract_status: str | None = None
    payment_format: str | None = None
    lead_source: str | None = None
    sales_person: str | None = None
    installation_year: str | None = None
    source_reported_at: datetime | None = None


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

    @model_validator(mode="after")
    def validate_tree_graph(self) -> "DiagnosticTreeUpdate":
        nodes = self.content.get("nodes")
        start_node = self.content.get("start_node")
        if not isinstance(nodes, dict) or not nodes or len(nodes) > 100:
            raise ValueError("A diagnostic tree must contain between 1 and 100 nodes.")
        if not isinstance(start_node, str) or start_node not in nodes:
            raise ValueError("The diagnostic tree start_node must reference an existing node.")

        visiting: set[str] = set()
        visited: set[str] = set()
        maximum_questions_seen: dict[str, int] = {}

        def visit(node_id: str, questions_seen: int) -> None:
            if node_id in visiting:
                raise ValueError("Diagnostic trees cannot contain cycles.")
            if maximum_questions_seen.get(node_id, -1) >= questions_seen:
                return

            node = nodes.get(node_id)
            if not isinstance(node, dict):
                raise ValueError(f"Diagnostic node {node_id!r} must be an object.")
            node_type = node.get("type")
            if not isinstance(node_type, str) or node_type not in {"question", "resolution", "ticket"}:
                raise ValueError(f"Diagnostic node {node_id!r} has an unsupported type.")
            next_nodes: list[str] = []
            if node_type == "question":
                questions_seen += 1
                if questions_seen > 3:
                    raise ValueError("A diagnostic path cannot contain more than three questions.")
                answers = node.get("answers")
                if not isinstance(answers, list) or not answers or len(answers) > 10:
                    raise ValueError(f"Question node {node_id!r} must have 1 to 10 answers.")
                for answer in answers:
                    if not isinstance(answer, dict) or not isinstance(answer.get("next"), str):
                        raise ValueError(f"Every answer in question node {node_id!r} needs a next node.")
                    next_nodes.append(answer["next"])
            elif node_type == "ticket":
                if not all(isinstance(node.get(key), str) and node[key] for key in ("fault_code", "fault_category")):
                    raise ValueError(f"Ticket node {node_id!r} needs a fault code and category.")

            visiting.add(node_id)
            for next_node in next_nodes:
                if next_node not in nodes:
                    raise ValueError(f"Diagnostic node {node_id!r} points to a missing node.")
                visit(next_node, questions_seen)
            visiting.remove(node_id)
            visited.add(node_id)
            maximum_questions_seen[node_id] = max(questions_seen, maximum_questions_seen.get(node_id, -1))

        visit(start_node, 0)
        if visited != set(nodes):
            raise ValueError("Every diagnostic node must be reachable from start_node.")
        return self


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


class PasswordLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)


class PasswordLoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class UserCreateRequest(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_-]{3,80}$")
    password: str = Field(min_length=12, max_length=256)
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
