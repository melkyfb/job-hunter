from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DesignVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    prompt: str
    type: Literal["resume", "cover_letter"]
    html_template: str
    inherit_from_design_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    is_default: bool = False
