
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Resource(Base):
    __tablename__ = "resources"

    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0",
            name="nonnegative_resource_quantity",
        ),
        CheckConstraint(
            "low_stock_threshold >= 0",
            name="nonnegative_low_stock_threshold",
        ),
        CheckConstraint(
            "category IN ('FOOD', 'CLOTHING', 'EDUCATIONAL_MATERIALS', "
            "'MEDICAL_SUPPLIES', 'EMERGENCY_KITS', 'OTHER')",
            name="valid_resource_category",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="valid_resource_status",
        ),
        Index("ix_resources_name_category", "name", "category"),
        Index("ix_resources_quantity_available", "quantity_available"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    unit: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unit",
    )

    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        index=True,
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
