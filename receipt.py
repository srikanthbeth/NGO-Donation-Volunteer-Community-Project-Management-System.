
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DonationReceiptCreate(BaseModel):
    donation_id: int = Field(gt=0)


class DonationReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_number: str
    donation_id: int
    donor_id: int
    amount: Decimal
    currency: str
    payment_method: str
    transaction_reference: str | None
    status: str
    issued_at: datetime


class DonationReceiptListResponse(BaseModel):
    items: list[DonationReceiptResponse]
    total: int
    page: int
    page_size: int
