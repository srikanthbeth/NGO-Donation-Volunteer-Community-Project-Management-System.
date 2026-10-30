
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ExpenseStatus = Literal[
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "REIMBURSED",
]

ExpenseCategory = Literal[
    "TRAVEL",
    "FOOD",
    "SUPPLIES",
    "EQUIPMENT",
    "TRANSPORT",
    "ACCOMMODATION",
    "UTILITIES",
    "MEDICAL",
    "EDUCATION",
    "ADMINISTRATION",
    "OTHER",
]


class ExpenseCreate(BaseModel):
    project_id: int = Field(gt=0)
    category: ExpenseCategory
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    expense_date: date
    receipt_reference: str | None = Field(default=None, max_length=255)
    attachment_url: str | None = Field(default=None, max_length=2048)
    description: str = Field(min_length=3, max_length=5000)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isalpha():
            raise ValueError("Currency must contain three alphabetic characters.")
        return value

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return value.upper()

    @field_validator("receipt_reference", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("attachment_url")
    @classmethod
    def validate_attachment_url(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
            if not value.startswith(("https://", "http://")):
                raise ValueError("Attachment URL must use HTTP or HTTPS.")
        return value

    @model_validator(mode="after")
    def validate_receipt_details(self):
        if not self.receipt_reference and not self.attachment_url:
            raise ValueError(
                "Provide a receipt reference or an attachment URL."
            )
        return self


class ExpenseReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    review_comments: str | None = Field(default=None, max_length=5000)

    @field_validator("review_comments")
    @classmethod
    def normalize_comments(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExpenseReimbursement(BaseModel):
    review_comments: str | None = Field(default=None, max_length=5000)

    @field_validator("review_comments")
    @classmethod
    def normalize_comments(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    submitted_by: int
    reviewed_by: int | None
    category: str
    amount: Decimal
    currency: str
    expense_date: date
    receipt_reference: str | None
    attachment_url: str | None
    description: str
    status: ExpenseStatus
    review_comments: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    reimbursed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(BaseModel):
    items: list[ExpenseResponse]
    total: int
    page: int
    page_size: int
