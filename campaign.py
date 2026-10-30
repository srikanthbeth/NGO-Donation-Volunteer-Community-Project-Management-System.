
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    __table_args__ = (
        CheckConstraint(
            "goal_amount > 0",
            name="ck_campaigns_goal_amount_positive",
        ),
        CheckConstraint(
            "raised_amount >= 0",
            name="ck_campaigns_raised_amount_nonnegative",
        ),
        CheckConstraint(
            "raised_amount <= goal_amount",
            name="ck_campaigns_raised_not_over_goal",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED')",
            name="ck_campaigns_status",
        ),
        CheckConstraint(
            "end_date > start_date",
            name="ck_campaigns_end_after_start",
        ),
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_start_end", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    goal_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    raised_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT",
    )

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
