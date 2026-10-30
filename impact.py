
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
)


ImpactNotes = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=5000,
    ),
]


class ImpactUpdateCreate(BaseModel):
    beneficiaries_served: int = Field(default=0, ge=0)
    volunteer_hours: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    resources_distributed: int = Field(default=0, ge=0)
    projects_completed: int = Field(default=0, ge=0)
    funds_utilized: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    milestones_achieved: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=5000)


class ImpactUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    beneficiaries_served: int
    volunteer_hours: Decimal
    resources_distributed: int
    projects_completed: int
    funds_utilized: Decimal
    milestones_achieved: int
    notes: str | None
    submitted_by: int
    created_at: datetime

    @field_serializer("volunteer_hours", "funds_utilized", when_used="json")
    def serialize_decimal_metrics(self, value: Decimal) -> str:
        return format(value, ".2f")


class ImpactUpdateListResponse(BaseModel):
    items: list[ImpactUpdateResponse]
    total: int
    page: int
    page_size: int


class ImpactSummaryResponse(BaseModel):
    project_id: int
    update_count: int
    beneficiaries_served: int
    volunteer_hours: Decimal
    resources_distributed: int
    projects_completed: int
    funds_utilized: Decimal
    milestones_achieved: int

    @field_serializer("volunteer_hours", "funds_utilized", when_used="json")
    def serialize_decimal_metrics(self, value: Decimal) -> str:
        return format(value, ".2f")
