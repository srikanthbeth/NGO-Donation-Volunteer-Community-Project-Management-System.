
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy.orm import relationship
from models.user import User

from db.base import Base


class Volunteer(Base):
    __tablename__ = "volunteers"

    __table_args__ = (
        CheckConstraint(
            "experience_years >= 0",
            name="ck_volunteers_experience_nonnegative",
        ),
        CheckConstraint(
            "hours_per_week >= 0 AND hours_per_week <= 168",
            name="ck_volunteers_hours_per_week",
        ),
        CheckConstraint(
            "availability IN "
            "('WEEKDAYS', 'WEEKENDS', 'EVENINGS', 'FLEXIBLE', 'CUSTOM')",
            name="ck_volunteers_availability",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'INACTIVE')",
            name="ck_volunteers_status",
        ),
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

    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    availability: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="FLEXIBLE",
    )

    hours_per_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    experience_years: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    preferred_areas: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(25),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User")