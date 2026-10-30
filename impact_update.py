
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ImpactUpdate(Base):
    __tablename__ = "impact_updates"

    __table_args__ = (
        CheckConstraint(
            "beneficiaries_served >= 0",
            name="impact_beneficiaries_nonnegative",
        ),
        CheckConstraint(
            "volunteer_hours >= 0",
            name="impact_volunteer_hours_nonnegative",
        ),
        CheckConstraint(
            "resources_distributed >= 0",
            name="impact_resources_nonnegative",
        ),
        CheckConstraint(
            "projects_completed >= 0",
            name="impact_projects_completed_nonnegative",
        ),
        CheckConstraint(
            "funds_utilized >= 0",
            name="impact_funds_utilized_nonnegative",
        ),
        CheckConstraint(
            "milestones_achieved >= 0",
            name="impact_milestones_nonnegative",
        ),
        Index(
            "ix_impact_updates_project_created",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    beneficiaries_served: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    volunteer_hours: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    resources_distributed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    projects_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    funds_utilized: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    milestones_achieved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    submitted_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
