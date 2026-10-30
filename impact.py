
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.impact import (
    ImpactSummaryResponse,
    ImpactUpdateCreate,
    ImpactUpdateListResponse,
    ImpactUpdateResponse,
)
from services.impact_service import ImpactService


router = APIRouter(prefix="/api/v1/impact", tags=["Impact Tracking"])


@router.post(
    "/projects/{project_id}/updates",
    response_model=ImpactUpdateResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_impact_update(
    project_id: int,
    payload: ImpactUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ImpactService(db).create_update(project_id, payload, current_user)


@router.get(
    "/projects/{project_id}/history",
    response_model=ImpactUpdateListResponse,
)
def get_impact_history(
    project_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ImpactService(db).list_updates(
        project_id,
        current_user,
        page,
        page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/projects/{project_id}/summary",
    response_model=ImpactSummaryResponse,
)
def get_impact_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ImpactService(db).get_summary(project_id, current_user)
