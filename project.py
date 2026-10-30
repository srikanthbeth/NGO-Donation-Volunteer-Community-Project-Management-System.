
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ProjectStatus = Literal[
    "DRAFT",
    "PLANNED",
    "ACTIVE",
    "ON_HOLD",
    "COMPLETED",
    "CANCELLED",
]


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    location: str | None = Field(default=None, max_length=250)
    start_date: datetime
    end_date: datetime | None = None
    budget: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    currency: str = Field(default="INR", min_length=3, max_length=3)
    status: ProjectStatus = "DRAFT"

    @field_validator("title", "description")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value or None
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a three-letter code.")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    location: str | None = Field(default=None, max_length=250)
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: ProjectStatus | None = None

    @field_validator("title", "description")
    @classmethod
    def validate_nonblank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("This field must not be blank.")
        return value

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value or None
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a three-letter code.")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        # Check the date range when both dates are supplied.
        # The service validates the combined dates against the existing record.
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date.")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    location: str | None
    start_date: datetime
    end_date: datetime | None
    budget: Decimal
    currency: str
    status: ProjectStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
