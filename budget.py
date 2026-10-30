
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


BudgetStatus = Literal[
    "DRAFT",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "CLOSED",
]


class BudgetCreate(BaseModel):
    campaign_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)

    allocated_amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
    )

    description: str | None = Field(
        default=None,
        min_length=3,
        max_length=5000,
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()

        if len(value) != 3 or not value.isalpha():
            raise ValueError(
                "Currency must contain exactly three letters."
            )

        return value

    @field_validator("description")
    @classmethod
    def validate_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Description cannot be blank."
            )

        return value

    @model_validator(mode="after")
    def validate_budget_parent(self):
        if (self.campaign_id is None) == (
            self.project_id is None
        ):
            raise ValueError(
                "Provide exactly one of campaign_id or project_id."
            )

        return self


class BudgetUpdate(BaseModel):
    allocated_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    description: str | None = Field(
        default=None,
        min_length=3,
        max_length=5000,
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip().upper()

        if len(value) != 3 or not value.isalpha():
            raise ValueError(
                "Currency must contain exactly three letters."
            )

        return value

    @field_validator("description")
    @classmethod
    def validate_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Description cannot be blank."
            )

        return value

    @model_validator(mode="after")
    def require_update_field(self):
        if not self.model_fields_set:
            raise ValueError(
                "Provide at least one field to update."
            )

        return self


class BudgetReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]

    approval_comments: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("approval_comments")
    @classmethod
    def validate_comments(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int | None
    project_id: int | None
    allocated_amount: Decimal
    currency: str
    description: str | None
    status: BudgetStatus
    created_by: int
    approved_by: int | None
    approval_comments: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BudgetSummary(BaseModel):
    budget_id: int
    campaign_id: int | None
    project_id: int | None
    allocated_amount: Decimal
    approved_expenses: Decimal
    remaining_budget: Decimal
    utilization_percentage: Decimal
    is_over_budget: bool
    currency: str
    status: BudgetStatus


class BudgetListResponse(BaseModel):
    items: list[BudgetResponse]
    total: int
    page: int
    page_size: int
