
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportFilters(BaseModel):
    """Common filters accepted by report endpoints."""

    start_date: date | None = None
    end_date: date | None = None
    campaign_id: int | None = Field(default=None, ge=1)
    project_id: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, min_length=1, max_length=30)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    sort_by: str = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def validate_date_range(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError(
                "start_date must be on or before end_date"
            )
        return self


class ReportPage(BaseModel):
    items: list[dict[str, Any]]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class DonationReportItem(BaseModel):
    donation_id: int
    campaign_id: int
    campaign_title: str
    donor_id: int
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    created_at: datetime


class CampaignReportItem(BaseModel):
    campaign_id: int
    title: str
    goal_amount: Decimal
    raised_amount: Decimal
    currency: str
    status: str
    progress_percent: float
    start_date: datetime
    end_date: datetime
    created_at: datetime


class VolunteerReportItem(BaseModel):
    volunteer_id: int
    name: str
    status: str
    assignment_count: int
    scheduled_hours_per_week: int
    completed_assignments: int
    created_at: datetime


class ProjectReportItem(BaseModel):
    project_id: int
    title: str
    status: str
    budget: Decimal
    currency: str
    task_count: int
    completed_tasks: int
    milestone_count: int
    completed_milestones: int
    approved_expenses: Decimal
    budget_remaining: Decimal
    created_at: datetime


class ExpenseReportItem(BaseModel):
    expense_id: int
    project_id: int
    category: str
    amount: Decimal
    currency: str
    status: str
    expense_date: date
    description: str | None = None
    created_at: datetime


class ResourceReportItem(BaseModel):
    transaction_id: int
    resource_id: int
    resource_name: str
    project_id: int | None = None
    transaction_type: str
    quantity: int
    created_at: datetime


class BeneficiaryImpactReportItem(BaseModel):
    impact_update_id: int
    project_id: int
    beneficiaries_served: int
    volunteer_hours: Decimal
    resources_distributed: int
    projects_completed: int
    funds_utilized: Decimal
    milestones_achieved: int
    created_at: datetime


class ReportExportResponse(BaseModel):
    filename: str
    content_type: str = "text/csv"
    exported_rows: int = Field(ge=0)


class ReportStatusSummary(BaseModel):
    status: str
    count: int = Field(ge=0)


class DonationSummary(BaseModel):
    total_donations: int = Field(ge=0)
    successful_donations: int = Field(ge=0)
    total_successful_amount: Decimal = Field(ge=0)
