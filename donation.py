
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Donation(Base):
    __tablename__ = "donations"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_donations_amount_positive",
        ),
        CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_donations_currency_format",
        ),
        CheckConstraint(
            "payment_method IN "
            "('CASH', 'BANK_TRANSFER', 'CARD', 'UPI', 'CHEQUE', 'OTHER')",
            name="ck_donations_payment_method",
        ),
        CheckConstraint(
            "payment_status IN "
            "('PENDING', 'SUCCESSFUL', 'FAILED', 'REFUNDED')",
            name="ck_donations_payment_status",
        ),
        Index("ix_donations_donor_status", "donor_id", "payment_status"),
        Index("ix_donations_campaign_status", "campaign_id", "payment_status"),
        Index("ix_donations_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    donor_id: Mapped[int] = mapped_column(
        ForeignKey("donors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )

    transaction_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        unique=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
