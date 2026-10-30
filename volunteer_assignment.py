
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AssignmentStatus = Literal[
    "ASSIGNED",
    "ACCEPTED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
]


class VolunteerAssignmentBase(BaseModel):
    volunteer_id: int = Field(gt=0)
    project_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    responsibilities: Optional[str] = Field(default=None, max_length=5000)
    start_date: date
    end_date: Optional[date] = None
    hours_per_week: int = Field(default=0, ge=0, le=168)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Title must contain at least 3 non-space characters.")
        return value

    @field_validator("description", "responsibilities")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return self


class VolunteerAssignmentCreate(VolunteerAssignmentBase):
    pass


class VolunteerAssignmentUpdate(BaseModel):
    project_id: Optional[int] = Field(default=None, gt=0)
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    responsibilities: Optional[str] = Field(default=None, max_length=5000)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    hours_per_week: Optional[int] = Field(default=None, ge=0, le=168)

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Title must contain at least 3 non-space characters.")
        return value

    @field_validator("description", "responsibilities")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be earlier than start date.")
        return self


class VolunteerAssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus


class VolunteerAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    volunteer_id: int
    project_id: Optional[int]
    title: str
    description: Optional[str]
    responsibilities: Optional[str]
    start_date: date
    end_date: Optional[date]
    hours_per_week: int
    status: AssignmentStatus
    assigned_by: int
    created_at: datetime
    updated_at: datetime


class VolunteerAssignmentListResponse(BaseModel):
    items: list[VolunteerAssignmentResponse]
    total: int
    page: int
    page_size: int
