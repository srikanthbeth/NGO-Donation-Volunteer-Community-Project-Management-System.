
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

TaskStatus = Literal[
    "TODO",
    "IN_PROGRESS",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
]

TaskPriority = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "URGENT",
]


class ProjectTaskCreate(BaseModel):
    project_id: int = Field(gt=0)
    milestone_id: int | None = Field(default=None, gt=0)
    assigned_volunteer_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: TaskPriority = "MEDIUM"
    status: TaskStatus = "TODO"
    start_date: datetime | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.due_date is not None
            and self.due_date < self.start_date
        ):
            raise ValueError("due_date must be on or after start_date.")
        return self


class ProjectTaskUpdate(BaseModel):
    milestone_id: int | None = Field(default=None, gt=0)
    assigned_volunteer_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Task title must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.due_date is not None
            and self.due_date < self.start_date
        ):
            raise ValueError("due_date must be on or after start_date.")
        return self


class ProjectTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    milestone_id: int | None
    assigned_volunteer_id: int | None
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    start_date: datetime | None
    due_date: datetime | None
    completed_at: datetime | None
    created_by: int
    created_at: datetime
    updated_at: datetime


class ProjectTaskListResponse(BaseModel):
    items: list[ProjectTaskResponse]
    total: int
    page: int
    page_size: int
