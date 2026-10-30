
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Donor(Base):
    __tablename__ = "donors"

    __table_args__ = (
        CheckConstraint(
            "donor_type IN ('INDIVIDUAL', 'ORGANIZATION')",
            name="ck_donors_donor_type",
        ),
        CheckConstraint(
            "preferred_contact_method IN ('EMAIL', 'PHONE', 'SMS')",
            name="ck_donors_contact_method",
        ),
        Index("ix_donors_city_country", "city", "country"),
        Index("ix_donors_donor_type", "donor_type"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    donor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="INDIVIDUAL",
    )

    organization_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(25),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    preferred_contact_method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="EMAIL",
    )

    anonymous_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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
