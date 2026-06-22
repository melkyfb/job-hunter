from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.profile import ProfileMaster


class IngestionStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    HITL_REQUIRED = "hitl_required"  # Agent paused, needs human input
    FAILED = "failed"


class HITLField(BaseModel):
    """Represents a single field that the agent couldn't fill with confidence."""

    field_path: str = Field(
        description="Dot-notation path, e.g. 'work_experiences.0.achievements.0.metric'"
    )
    current_value: Optional[str] = Field(
        default=None,
        description="What the LLM extracted (may be empty or low-confidence)",
    )
    llm_suggestion: Optional[str] = Field(
        default=None,
        description="LLM's best-effort suggestion for the user to confirm or edit",
    )
    reason: str = Field(
        description="Why this field needs human review",
    )


class HITLRequest(BaseModel):
    """Returned by the ingestion endpoint when the agent needs clarification."""

    ingestion_id: UUID
    partial_profile: ProfileMaster
    missing_fields: list[HITLField] = Field(min_length=1)
    message: str = "Some fields require your input before saving."


class HITLResolution(BaseModel):
    """Sent by the frontend to resolve pending HITL fields."""

    ingestion_id: UUID
    resolved_fields: dict[str, str] = Field(
        description="Map of field_path → user-provided value"
    )


class IngestionResponse(BaseModel):
    ingestion_id: UUID
    status: IngestionStatus
    profile: Optional[ProfileMaster] = None
    hitl_request: Optional[HITLRequest] = None
    error: Optional[str] = None
