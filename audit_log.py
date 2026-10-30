
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogCreate(BaseModel):
    """Internal schema for recording an audit event."""

    action: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: str | None = Field(default=None, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = Field(default=None, max_length=45)
