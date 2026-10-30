from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.dashboard import DashboardSummary
from services.dashboard_service import get_dashboard_summary


router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/summary",
    response_model=DashboardSummary,
)
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return organization-wide dashboard metrics.

    Only SUPER_ADMIN and NGO_MANAGER users can view this dashboard.
    """
    allowed_roles = {"SUPER_ADMIN", "NGO_MANAGER"}

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view the dashboard.",
        )

    return get_dashboard_summary(db)