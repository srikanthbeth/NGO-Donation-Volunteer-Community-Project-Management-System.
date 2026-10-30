
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.expense import (
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseReview,
    ExpenseReimbursement,
)
from services.expense_service import ExpenseService

router = APIRouter(
    prefix="/api/v1/expenses",
    tags=["Expenses"],
)


@router.post(
    "",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ExpenseService(db).create_expense(
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=ExpenseListResponse,
)
def list_expenses(
    project_id: int | None = Query(default=None, gt=0),
    category: str | None = Query(default=None, min_length=1, max_length=50),
    expense_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(SUBMITTED|APPROVED|REJECTED|REIMBURSED)$",
    ),
    submitted_by: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(
        default="expense_date",
        pattern="^(id|project_id|category|amount|expense_date|status|submitted_at|created_at)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ExpenseService(db).list_expenses(
        current_user=current_user,
        project_id=project_id,
        category=category,
        expense_status=expense_status,
        submitted_by=submitted_by,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
)
def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = ExpenseService(db).get_expense(expense_id)

    role = current_user.role
    role = role.value if hasattr(role, "value") else str(role)

    if (
        role not in ExpenseService.APPROVER_ROLES
        and expense.submitted_by != current_user.id
    ):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view this expense.",
        )

    return expense


@router.patch(
    "/{expense_id}/review",
    response_model=ExpenseResponse,
)
def review_expense(
    expense_id: int,
    payload: ExpenseReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ExpenseService(db).review_expense(
        expense_id=expense_id,
        current_user=current_user,
        review_status=payload.status,
        review_comments=payload.review_comments,
    )


@router.patch(
    "/{expense_id}/reimburse",
    response_model=ExpenseResponse,
)
def reimburse_expense(
    expense_id: int,
    payload: ExpenseReimbursement,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ExpenseService(db).reimburse_expense(
        expense_id=expense_id,
        current_user=current_user,
        review_comments=payload.review_comments,
    )
