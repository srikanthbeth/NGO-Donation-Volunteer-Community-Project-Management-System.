
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.donation import Donation
from models.donor import Donor
from models.receipt import DonationReceipt
from models.user import User


STAFF_ROLES = {"SUPER_ADMIN", "NGO_MANAGER", "FINANCE_OFFICER"}


class ReceiptService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def require_active_user(user: User) -> None:
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Inactive users cannot access donation receipts.",
            )

    def _get_donor(self, user: User) -> Donor:
        donor = self.db.scalar(
            select(Donor).where(Donor.user_id == user.id)
        )
        if donor is None:
            raise HTTPException(
                status_code=404,
                detail="Donor profile not found.",
            )
        return donor

    def create_receipt(
        self,
        donation_id: int,
        user: User,
    ) -> DonationReceipt:
        self.require_active_user(user)

        donation = self.db.get(Donation, donation_id)
        if donation is None:
            raise HTTPException(status_code=404, detail="Donation not found.")

        is_staff = user.role in STAFF_ROLES
        if not is_staff:
            donor = self._get_donor(user)
            if user.role != "DONOR" or donor.id != donation.donor_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create receipts for your own donations.",
                )

        existing = self.db.scalar(
            select(DonationReceipt).where(
                DonationReceipt.donation_id == donation_id
            )
        )

        if donation.payment_status == "REFUNDED":
            if existing is not None:
                existing.status = "VOID"
                self.db.commit()
            raise HTTPException(
                status_code=409,
                detail="A receipt cannot be issued for a refunded donation.",
            )

        if donation.payment_status != "SUCCESSFUL":
            raise HTTPException(
                status_code=409,
                detail="A receipt can only be issued for a successful donation.",
            )

        if existing is not None:
            if existing.status == "VOID":
                raise HTTPException(
                    status_code=409,
                    detail="This donation's receipt has been voided.",
                )
            raise HTTPException(
                status_code=409,
                detail="A receipt already exists for this donation.",
            )

        receipt = DonationReceipt(
            receipt_number=(
                f"NGO-{datetime.now(timezone.utc):%Y%m%d}-"
                f"{uuid4().hex[:12].upper()}"
            ),
            donation_id=donation.id,
            donor_id=donation.donor_id,
            amount=donation.amount,
            currency=donation.currency,
            payment_method=donation.payment_method,
            transaction_reference=donation.transaction_reference,
            status="ISSUED",
        )

        try:
            self.db.add(receipt)
            self.db.commit()
            self.db.refresh(receipt)
            return receipt
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="A receipt already exists for this donation.",
            )

    def get_receipt(
        self,
        receipt_id: int,
        user: User,
    ) -> DonationReceipt:
        self.require_active_user(user)

        receipt = self.db.get(DonationReceipt, receipt_id)
        if receipt is None:
            raise HTTPException(
                status_code=404,
                detail="Receipt not found.",
            )

        if user.role not in STAFF_ROLES:
            donor = self._get_donor(user)
            if user.role != "DONOR" or donor.id != receipt.donor_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your own receipts.",
                )

        donation = self.db.get(Donation, receipt.donation_id)
        if donation and donation.payment_status == "REFUNDED":
            if receipt.status != "VOID":
                receipt.status = "VOID"
                self.db.commit()
                self.db.refresh(receipt)

        return receipt

    def list_my_receipts(
        self,
        user: User,
        page: int = 1,
        page_size: int = 10,
    ):
        self.require_active_user(user)
        donor = self._get_donor(user)

        query = select(DonationReceipt).where(
            DonationReceipt.donor_id == donor.id
        )

        total = self.db.scalar(
            select(func.count()).select_from(query.subquery())
        ) or 0

        items = self.db.scalars(
            query.order_by(
                DonationReceipt.issued_at.desc(),
                DonationReceipt.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        # Keep stored receipts consistent with refunds.
        changed = False
        for receipt in items:
            donation = self.db.get(Donation, receipt.donation_id)
            if donation and donation.payment_status == "REFUNDED":
                if receipt.status != "VOID":
                    receipt.status = "VOID"
                    changed = True

        if changed:
            self.db.commit()
            for receipt in items:
                self.db.refresh(receipt)

        return items, total
