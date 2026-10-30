
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.budget import (
    BudgetCreate,
    BudgetListResponse,
    BudgetResponse,
    BudgetReview,
    BudgetSummary,
    BudgetUpdate,
)
from services.budget_service import BudgetService


router = APIRouter(
    prefix="/api/v1/budgets",
    tags=["Budgets"],
)


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).create_budget(
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=BudgetListResponse,
)
def list_budgets(
    campaign_id: int | None = Query(None, gt=0),
    project_id: int | None = Query(None, gt=0),
    budget_status: str | None = Query(
        None,
        alias="status",
        pattern="^(DRAFT|PENDING|APPROVED|REJECTED|CLOSED)$",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query(
        "created_at",
        pattern="^(id|allocated_amount|status|created_at|updated_at)$",
    ),
    sort_order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = BudgetService(db).list_budgets(
        current_user=current_user,
        campaign_id=campaign_id,
        project_id=project_id,
        budget_status=budget_status,
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
    "/{budget_id}/summary",
    response_model=BudgetSummary,
)
def get_budget_summary(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).get_summary(
        budget_id=budget_id,
        current_user=current_user,
    )


@router.get(
    "/{budget_id}",
    response_model=BudgetResponse,
)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).get_budget(
        budget_id=budget_id,
        current_user=current_user,
    )


@router.patch(
    "/{budget_id}",
    response_model=BudgetResponse,
)
def update_budget(
    budget_id: int,
    payload: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).update_budget(
        budget_id=budget_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch(
    "/{budget_id}/review",
    response_model=BudgetResponse,
)
def review_budget(
    budget_id: int,
    payload: BudgetReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).review_budget(
        budget_id=budget_id,
        current_user=current_user,
        review_status=payload.status,
        approval_comments=payload.approval_comments,
    )


@router.patch(
    "/{budget_id}/close",
    response_model=BudgetResponse,
)
def close_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BudgetService(db).close_budget(
        budget_id=budget_id,
        current_user=current_user,
    )
