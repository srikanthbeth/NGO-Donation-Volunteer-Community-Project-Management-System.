
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

CampaignStatus = Literal[
    "DRAFT",
    "ACTIVE",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
]


class CampaignCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    goal_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    start_date: datetime
    end_date: datetime
    status: CampaignStatus = "DRAFT"

    @field_validator("title", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class CampaignUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10)
    goal_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: CampaignStatus | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value):
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    goal_amount: Decimal
    raised_amount: Decimal
    currency: str
    start_date: datetime
    end_date: datetime
    status: CampaignStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    page_size: int
    pages: int
