
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.expense import Expense
from models.project import Project
from repositories.expense_repository import ExpenseRepository


class ExpenseService:
    APPROVER_ROLES = {"SUPER_ADMIN", "FINANCE_OFFICER"}
    SUBMITTER_ROLES = {
        "SUPER_ADMIN",
        "NGO_MANAGER",
        "FINANCE_OFFICER",
    }

    def __init__(self, db: Session):
        self.db = db
        self.repository = ExpenseRepository(db)

    @staticmethod
    def _role(user) -> str:
        role = user.role
        return role.value if hasattr(role, "value") else str(role)

    def create_expense(self, payload, current_user) -> Expense:
        if self._role(current_user) not in self.SUBMITTER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to submit expenses.",
            )

        project = self.db.get(Project, payload.project_id)

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        if getattr(project, "status", None) == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expenses cannot be submitted for cancelled projects.",
            )

        data = payload.model_dump()
        data["submitted_by"] = current_user.id
        data["reviewed_by"] = None
        data["status"] = "SUBMITTED"
        data["review_comments"] = None
        data["reviewed_at"] = None
        data["reimbursed_at"] = None

        return self.repository.create(data)

    def get_expense(self, expense_id: int) -> Expense:
        expense = self.repository.get_by_id(expense_id)

        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found.",
            )

        return expense

    def review_expense(
        self,
        expense_id: int,
        current_user,
        review_status: str,
        review_comments: str | None = None,
    ) -> Expense:
        if self._role(current_user) not in self.APPROVER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only authorized finance users can approve or reject expenses.",
            )

        expense = self.get_expense(expense_id)

        if expense.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only submitted expenses can be reviewed.",
            )

        normalized_status = review_status.upper()

        if normalized_status not in {"APPROVED", "REJECTED"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Review status must be APPROVED or REJECTED.",
            )

        return self.repository.update(
            expense,
            {
                "status": normalized_status,
                "reviewed_by": current_user.id,
                "review_comments": review_comments,
                "reviewed_at": datetime.now(timezone.utc),
            },
        )

    def reimburse_expense(
        self,
        expense_id: int,
        current_user,
        review_comments: str | None = None,
    ) -> Expense:
        if self._role(current_user) not in self.APPROVER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only authorized finance users can mark expenses as reimbursed.",
            )

        expense = self.get_expense(expense_id)

        if expense.status != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved expenses can be reimbursed.",
            )

        return self.repository.update(
            expense,
            {
                "status": "REIMBURSED",
                "review_comments": review_comments,
                "reimbursed_at": datetime.now(timezone.utc),
            },
        )

    def list_expenses(
        self,
        current_user,
        project_id: int | None = None,
        category: str | None = None,
        expense_status: str | None = None,
        submitted_by: int | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "expense_date",
        sort_order: str = "desc",
    ) -> tuple[list[Expense], int]:
        role = self._role(current_user)

        if role not in self.APPROVER_ROLES:
            submitted_by = current_user.id

        return self.repository.list(
            project_id=project_id,
            category=category,
            expense_status=expense_status,
            submitted_by=submitted_by,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
