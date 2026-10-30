
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.project_milestone import (
    ProjectMilestoneCreate,
    ProjectMilestoneUpdate,
    ProjectMilestoneResponse,
    ProjectMilestoneListResponse,
)
from services.project_milestone_service import ProjectMilestoneService

# Replace this import with the dependency used in routes/projects.py.
from routes.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/milestones", tags=["Project Milestones"])


def _role(user) -> str:
    role = getattr(user, "role", "")
    return str(getattr(role, "value", role)).upper()


def _require_manager(user) -> None:
    if _role(user) not in {"SUPER_ADMIN", "NGO_MANAGER"}:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )


@router.post(
    "",
    response_model=ProjectMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_milestone(
    payload: ProjectMilestoneCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_manager(current_user)
    service = ProjectMilestoneService(db)
    return service.create(
        payload.model_dump(),
        created_by=current_user.id,
    )


@router.get("", response_model=ProjectMilestoneListResponse)
def list_milestones(
    project_id: int | None = Query(default=None, gt=0),
    milestone_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = ProjectMilestoneService(db).list(
        project_id=project_id,
        status_filter=milestone_status,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result


@router.get("/{milestone_id}", response_model=ProjectMilestoneResponse)
def get_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return ProjectMilestoneService(db).get_by_id(milestone_id)


@router.patch("/{milestone_id}", response_model=ProjectMilestoneResponse)
def update_milestone(
    milestone_id: int,
    payload: ProjectMilestoneUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_manager(current_user)
    return ProjectMilestoneService(db).update(
        milestone_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_manager(current_user)
    ProjectMilestoneService(db).delete(milestone_id)
