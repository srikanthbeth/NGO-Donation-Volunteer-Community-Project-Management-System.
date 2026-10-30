
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


PaymentMethod = Literal[
    "CASH",
    "BANK_TRANSFER",
    "CARD",
    "UPI",
    "CHEQUE",
    "OTHER",
]

PaymentStatus = Literal[
    "PENDING",
    "SUCCESSFUL",
    "FAILED",
    "REFUNDED",
]


class DonationCreate(BaseModel):
    campaign_id: int = Field(gt=0)
    donor_id: int | None = Field(default=None, gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    payment_method: PaymentMethod
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class DonationStatusUpdate(BaseModel):
    payment_status: PaymentStatus
    transaction_reference: str | None = Field(
        default=None,
        max_length=150,
    )

    @field_validator("transaction_reference")
    @classmethod
    def clean_reference(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class DonationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    donor_id: int
    campaign_id: int
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    transaction_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DonationListResponse(BaseModel):
    items: list[DonationResponse]
    total: int
    page: int
    page_size: int
    pages: int
