from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CampaignGoalAchievement(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_campaigns: int = 0
    total_goal_amount: Decimal = Decimal("0.00")
    total_raised_amount: Decimal = Decimal("0.00")
    achievement_percentage: float = 0.0


class ResourceStockSummary(BaseModel):
    active_resources: int = 0
    total_quantity_available: int = 0
    low_stock_resources: int = 0


class ProjectBudgetUtilization(BaseModel):
    total_project_budget: Decimal = Decimal("0.00")
    approved_and_reimbursed_expenses: Decimal = Decimal("0.00")
    utilization_percentage: float = 0.0


class DashboardSummary(BaseModel):
    total_donations: int = 0
    confirmed_donations: int = 0

    active_fundraising_campaigns: int = 0
    campaign_goal_achievement: CampaignGoalAchievement

    total_volunteers: int = 0
    active_community_projects: int = 0

    pending_project_approvals: int = 0
    pending_expense_approvals: int = 0

    total_beneficiaries_served: int = 0
    resource_stock_levels: ResourceStockSummary
    total_volunteer_hours: Decimal = Field(default=Decimal("0.00"))

    project_budget_utilization: ProjectBudgetUtilization