
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.campaign import Campaign
from models.donation import Donation
from repositories.campaign_repository import get_campaign_by_id
from repositories.donation_repository import (
    create_donation,
    get_donation_by_id,
    list_donations,
    sync_campaign_raised_amount,
    update_donation,
)
from repositories.donor_repository import (
    get_donor_by_id,
    get_donor_by_user_id,
)
from schemas.donation import (
    DonationCreate,
    DonationListResponse,
    DonationResponse,
    DonationStatusUpdate,
)

STAFF_ROLES = {"SUPER_ADMIN", "NGO_MANAGER", "FINANCE_OFFICER"}
PAYMENT_MANAGER_ROLES = STAFF_ROLES


def role_value(user) -> str:
    return str(getattr(user.role, "value", user.role)).upper()


def require_staff(user, allowed_roles=STAFF_ROLES):
    if role_value(user) not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform this action",
        )


def get_donation_or_404(db: Session, donation_id: int) -> Donation:
    donation = get_donation_by_id(db, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found")
    return donation


def get_campaign_or_404(db: Session, campaign_id: int) -> Campaign:
    campaign = get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def create_donation_record(
    db: Session,
    data: DonationCreate,
    current_user,
) -> DonationResponse:
    role = role_value(current_user)
    campaign = get_campaign_or_404(db, data.campaign_id)

    if campaign.status != "ACTIVE":
        raise HTTPException(
            status_code=422,
            detail="Donations can only be made to active campaigns",
        )

    if data.currency != campaign.currency:
        raise HTTPException(
            status_code=422,
            detail="Donation currency must match the campaign currency",
        )

    if role == "DONOR":
        donor = get_donor_by_user_id(db, current_user.id)
        if donor is None:
            raise HTTPException(
                status_code=404,
                detail="Create a donor profile before donating",
            )

        if data.donor_id is not None and data.donor_id != donor.id:
            raise HTTPException(
                status_code=403,
                detail="You can only donate using your own donor profile",
            )

        donor_id = donor.id
    elif role in STAFF_ROLES:
        if data.donor_id is None:
            raise HTTPException(
                status_code=422,
                detail="donor_id is required when staff create a donation",
            )
        donor = get_donor_by_id(db, data.donor_id)
        if donor is None:
            raise HTTPException(status_code=404, detail="Donor not found")
        donor_id = donor.id
    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to create donations",
        )

    donation_data = data.model_dump(exclude={"donor_id"})
    donation_data["donor_id"] = donor_id
    donation_data["payment_status"] = "PENDING"

    try:
        donation = create_donation(db, donation_data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Donation conflicts with an existing transaction reference",
        )

    return DonationResponse.model_validate(donation)


def get_donation_record(
    db: Session,
    donation_id: int,
    current_user,
) -> DonationResponse:
    donation = get_donation_or_404(db, donation_id)

    if role_value(current_user) not in STAFF_ROLES:
        donor = get_donor_by_user_id(db, current_user.id)
        if donor is None or donor.id != donation.donor_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return DonationResponse.model_validate(donation)


def list_donation_records(
    db: Session,
    current_user,
    *,
    donor_id: int | None,
    campaign_id: int | None,
    payment_status: str | None,
    page: int,
    page_size: int,
) -> DonationListResponse:
    role = role_value(current_user)

    if role not in STAFF_ROLES:
        donor = get_donor_by_user_id(db, current_user.id)
        if donor is None:
            raise HTTPException(
                status_code=404,
                detail="Donor profile not found",
            )
        if donor_id is not None and donor_id != donor.id:
            raise HTTPException(status_code=403, detail="Access denied")
        donor_id = donor.id

    items, total = list_donations(
        db,
        donor_id=donor_id,
        campaign_id=campaign_id,
        payment_status=payment_status,
        page=page,
        page_size=page_size,
    )

    return DonationListResponse(
        items=[DonationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


def update_donation_status_record(
    db: Session,
    donation_id: int,
    data: DonationStatusUpdate,
    current_user,
) -> DonationResponse:
    require_staff(current_user, PAYMENT_MANAGER_ROLES)

    donation = get_donation_or_404(db, donation_id)
    campaign = get_campaign_or_404(db, donation.campaign_id)
    new_status = data.payment_status
    old_status = donation.payment_status

    if old_status == "REFUNDED" and new_status != "REFUNDED":
        raise HTTPException(
            status_code=422,
            detail="Refunded donations cannot be reopened",
        )

    if old_status == "SUCCESSFUL" and new_status == "PENDING":
        raise HTTPException(
            status_code=422,
            detail="Successful donations cannot be reset to pending",
        )

    if new_status == "SUCCESSFUL":
        from sqlalchemy import func
        from models.donation import Donation as DonationModel

        existing_total = (
            db.query(func.coalesce(func.sum(DonationModel.amount), 0))
            .filter(
                DonationModel.campaign_id == campaign.id,
                DonationModel.payment_status == "SUCCESSFUL",
                DonationModel.id != donation.id,
            )
            .scalar()
        )

        if existing_total + donation.amount > campaign.goal_amount:
            raise HTTPException(
                status_code=422,
                detail="Successful donations cannot exceed the campaign goal",
            )

    changes = {"payment_status": new_status}

    if data.transaction_reference is not None:
        changes["transaction_reference"] = data.transaction_reference

    try:
        for field, value in changes.items():
            setattr(donation, field, value)

        sync_campaign_raised_amount(db, campaign)
        db.commit()
        db.refresh(donation)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Transaction reference already exists",
        )

    # Recompute after the status change so totals reflect the new state.
    sync_campaign_raised_amount(db, campaign)
    db.commit()

    return DonationResponse.model_validate(donation)
