
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

MilestoneStatus = Literal[
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
]


class ProjectMilestoneCreate(BaseModel):
    project_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    due_date: datetime | None = None
    status: MilestoneStatus = "PENDING"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Milestone title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value


class ProjectMilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    due_date: datetime | None = None
    status: MilestoneStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Milestone title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value


class ProjectMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str | None
    due_date: datetime | None
    status: MilestoneStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class ProjectMilestoneListResponse(BaseModel):
    items: list[ProjectMilestoneResponse]
    total: int
    page: int
    page_size: int
