
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.volunteer_assignment import (
    VolunteerAssignmentCreate,
    VolunteerAssignmentListResponse,
    VolunteerAssignmentResponse,
    VolunteerAssignmentStatusUpdate,
    VolunteerAssignmentUpdate,
)
from services.volunteer_assignment_service import (
    VolunteerAssignmentService,
)


router = APIRouter(
    prefix="/api/v1/volunteer-assignments",
    tags=["Volunteer Assignments"],
)


def handle_service_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.post("", response_model=VolunteerAssignmentResponse, status_code=201)
def create_assignment(
    payload: VolunteerAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerAssignmentService.create_assignment(
            db,
            current_user,
            payload.model_dump(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        handle_service_error(exc)


@router.get("", response_model=VolunteerAssignmentListResponse)
def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    volunteer_id: int | None = Query(None, gt=0),
    project_id: int | None = Query(None, gt=0),
    assignment_status: str | None = Query(
        None,
        alias="status",
        pattern="^(ASSIGNED|ACCEPTED|IN_PROGRESS|COMPLETED|CANCELLED)$",
    ),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assignments, total = VolunteerAssignmentService.list_assignments(
            db,
            current_user,
            page=page,
            page_size=page_size,
            volunteer_id=volunteer_id,
            project_id=project_id,
            status=assignment_status,
            search=search,
        )
        return VolunteerAssignmentListResponse(
            items=assignments,
            total=total,
            page=page,
            page_size=page_size,
        )
    except (LookupError, PermissionError, ValueError) as exc:
        handle_service_error(exc)


@router.get("/{assignment_id}", response_model=VolunteerAssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerAssignmentService.get_assignment(
            db,
            current_user,
            assignment_id,
        )
    except (LookupError, PermissionError, ValueError) as exc:
        handle_service_error(exc)


@router.patch("/{assignment_id}", response_model=VolunteerAssignmentResponse)
def update_assignment(
    assignment_id: int,
    payload: VolunteerAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerAssignmentService.update_assignment(
            db,
            current_user,
            assignment_id,
            payload.model_dump(exclude_unset=True),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        handle_service_error(exc)


@router.patch(
    "/{assignment_id}/status",
    response_model=VolunteerAssignmentResponse,
)
def update_assignment_status(
    assignment_id: int,
    payload: VolunteerAssignmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerAssignmentService.update_status(
            db,
            current_user,
            assignment_id,
            payload.status,
        )
    except (LookupError, PermissionError, ValueError) as exc:
        handle_service_error(exc)
