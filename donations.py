
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.donation import (
    DonationCreate,
    DonationListResponse,
    DonationResponse,
    DonationStatusUpdate,
    PaymentStatus,
)
from services.donation_service import (
    create_donation_record,
    get_donation_record,
    list_donation_records,
    update_donation_status_record,
)

router = APIRouter(prefix="/donations", tags=["Donations"])


@router.post(
    "",
    response_model=DonationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_donation(
    payload: DonationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_donation_record(db, payload, current_user)


@router.get("", response_model=DonationListResponse)
def get_donations(
    donor_id: int | None = Query(default=None, gt=0),
    campaign_id: int | None = Query(default=None, gt=0),
    payment_status: PaymentStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_donation_records(
        db,
        current_user,
        donor_id=donor_id,
        campaign_id=campaign_id,
        payment_status=payment_status,
        page=page,
        page_size=page_size,
    )


@router.get("/{donation_id}", response_model=DonationResponse)
def get_donation(
    donation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_donation_record(db, donation_id, current_user)


@router.patch(
    "/{donation_id}/status",
    response_model=DonationResponse,
)
def update_donation_status(
    donation_id: int,
    payload: DonationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_donation_status_record(
        db,
        donation_id,
        payload,
        current_user,
    )
