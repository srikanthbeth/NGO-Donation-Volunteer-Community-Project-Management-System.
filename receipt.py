
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DonationReceipt(Base):
    __tablename__ = "donation_receipts"

    __table_args__ = (
        UniqueConstraint(
            "receipt_number",
            name="uq_donation_receipts_receipt_number",
        ),
        UniqueConstraint(
            "donation_id",
            name="uq_donation_receipts_donation_id",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_donation_receipts_amount_positive",
        ),
        Index("ix_donation_receipts_donor_id", "donor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    receipt_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    donation_id: Mapped[int] = mapped_column(
        ForeignKey("donations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount: Mapped[object] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    transaction_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ISSUED",
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
