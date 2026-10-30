
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.receipt import (
    DonationReceiptListResponse,
    DonationReceiptResponse,
)
from services.receipt_service import ReceiptService


router = APIRouter(prefix="/api/v1/receipts", tags=["Donation Receipts"])


@router.post(
    "/donations/{donation_id}",
    response_model=DonationReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_receipt(
    donation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ReceiptService(db).create_receipt(donation_id, current_user)


@router.get("/me", response_model=DonationReceiptListResponse)
def list_my_receipts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ReceiptService(db).list_my_receipts(
        current_user,
        page,
        page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{receipt_id}", response_model=DonationReceiptResponse)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ReceiptService(db).get_receipt(receipt_id, current_user)
