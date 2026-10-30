
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.budget import Budget
from models.campaign import Campaign
from models.expense import Expense
from models.project import Project
from repositories.budget_repository import BudgetRepository


CENT = Decimal("0.01")

BUDGET_STATUSES = {
    "DRAFT",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "CLOSED",
}


class BudgetService:
    CREATE_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}
    APPROVER_ROLES = {"SUPER_ADMIN", "FINANCE_OFFICER"}

    def __init__(self, db: Session):
        self.db = db
        self.repository = BudgetRepository(db)

    @staticmethod
    def _role(user) -> str:
        role = user.role
        return role.value if hasattr(role, "value") else str(role)

    def _require_role(self, user, allowed_roles: set[str]) -> None:
        if self._role(user) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this budget action.",
            )

    def _get_budget(self, budget_id: int) -> Budget:
        budget = self.repository.get_by_id(budget_id)
        if budget is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found.",
            )
        return budget

    def _validate_parent(self, campaign_id, project_id) -> None:
        if (campaign_id is None) == (project_id is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide exactly one of campaign_id or project_id.",
            )

        if campaign_id is not None:
            campaign = (
                self.db.query(Campaign)
                .filter(Campaign.id == campaign_id)
                .first()
            )
            if campaign is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found.",
                )

        if project_id is not None:
            project = (
                self.db.query(Project)
                .filter(Project.id == project_id)
                .first()
            )
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found.",
                )

    def create_budget(self, payload, current_user) -> Budget:
        self._require_role(current_user, self.CREATE_ROLES)

        data = payload.model_dump()
        self._validate_parent(
            campaign_id=data.get("campaign_id"),
            project_id=data.get("project_id"),
        )

        data["created_by"] = current_user.id
        data["approved_by"] = None
        data["approved_at"] = None
        data["approval_comments"] = None
        data["status"] = "PENDING"

        return self.repository.create(data)

    def get_budget(self, budget_id: int, current_user) -> Budget:
        budget = self._get_budget(budget_id)
        role = self._role(current_user)

        if (
            role not in self.APPROVER_ROLES
            and budget.created_by != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot view this budget.",
            )

        return budget

    def update_budget(self, budget_id: int, payload, current_user) -> Budget:
        self._require_role(current_user, self.CREATE_ROLES)
        budget = self._get_budget(budget_id)

        if budget.created_by != current_user.id and self._role(current_user) != "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot update this budget.",
            )

        if budget.status not in {"DRAFT", "REJECTED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft or rejected budgets can be updated.",
            )

        data = payload.model_dump(exclude_unset=True)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least one field to update.",
            )

        data["status"] = "PENDING"
        data["approved_by"] = None
        data["approved_at"] = None
        data["approval_comments"] = None

        return self.repository.update(budget, data)

    def review_budget(
        self,
        budget_id: int,
        current_user,
        review_status: str,
        approval_comments: str | None = None,
    ) -> Budget:
        self._require_role(current_user, self.APPROVER_ROLES)
        budget = self._get_budget(budget_id)

        if budget.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending budgets can be reviewed.",
            )

        if review_status not in {"APPROVED", "REJECTED"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Budget review status must be APPROVED or REJECTED.",
            )

        if review_status == "APPROVED":
            spent = self._approved_expenses_for_budget(budget)

            if spent > budget.allocated_amount:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Budget cannot be approved because approved expenses exceed its allocation.",
                )

        return self.repository.update(
            budget,
            {
                "status": review_status,
                "approved_by": current_user.id,
                "approval_comments": approval_comments,
                "approved_at": datetime.now(timezone.utc),
            },
        )

    def close_budget(self, budget_id: int, current_user) -> Budget:
        self._require_role(current_user, self.APPROVER_ROLES)
        budget = self._get_budget(budget_id)

        if budget.status != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved budgets can be closed.",
            )

        return self.repository.update(
            budget,
            {"status": "CLOSED"},
        )

    def _approved_expenses_for_budget(self, budget: Budget) -> Decimal:
        if budget.project_id is not None:
            return self.repository.approved_expense_total(budget.project_id)

        # Expense records currently reference projects, not campaigns.
        # Campaign-level aggregation requires a campaign-to-project link.
        return Decimal("0.00")

    def get_summary(self, budget_id: int, current_user) -> dict:
        budget = self.get_budget(budget_id, current_user)
        expenses = self._approved_expenses_for_budget(budget)
        allocation = Decimal(str(budget.allocated_amount))

        remaining = allocation - expenses

        if allocation > 0:
            utilization = (
                expenses / allocation * Decimal("100")
            ).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            utilization = Decimal("0.00")

        return {
            "budget_id": budget.id,
            "campaign_id": budget.campaign_id,
            "project_id": budget.project_id,
            "allocated_amount": allocation.quantize(CENT),
            "approved_expenses": expenses.quantize(CENT),
            "remaining_budget": remaining.quantize(CENT),
            "utilization_percentage": utilization,
            "is_over_budget": expenses > allocation,
            "currency": budget.currency,
            "status": budget.status,
        }

    def list_budgets(
        self,
        current_user,
        campaign_id: int | None = None,
        project_id: int | None = None,
        budget_status: str | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        role = self._role(current_user)
        created_by = (
            None if role in self.APPROVER_ROLES else current_user.id
        )

        return self.repository.list(
            campaign_id=campaign_id,
            project_id=project_id,
            budget_status=budget_status,
            created_by=created_by,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
