
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    __table_args__ = (
        CheckConstraint(
            "allocated_quantity > 0",
            name="positive_allocated_resource_quantity",
        ),
        CheckConstraint(
            "distributed_quantity >= 0",
            name="nonnegative_distributed_resource_quantity",
        ),
        CheckConstraint(
            "distributed_quantity <= allocated_quantity",
            name="distributed_not_above_allocated_quantity",
        ),
        CheckConstraint(
            "status IN ('ALLOCATED', 'PARTIALLY_DISTRIBUTED', 'COMPLETED', 'CANCELLED')",
            name="valid_resource_allocation_status",
        ),
        Index(
            "ix_resource_allocations_project_resource",
            "project_id",
            "resource_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    allocated_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    distributed_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ALLOCATED",
        index=True,
    )

    allocated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
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
