
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from models.volunteer import Volunteer
from repositories.volunteer_repository import VolunteerRepository
from routes.dependencies import get_current_user
from schemas.volunteer import (
    VolunteerCreate,
    VolunteerListResponse,
    VolunteerResponse,
    VolunteerStatusUpdate,
    VolunteerUpdate,
)
from services.volunteer_service import VolunteerService


router = APIRouter(
    prefix="/api/v1/volunteers",
    tags=["Volunteers"],
)


STAFF_ROLES = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
}


def role_name(user: User) -> str:
    role = user.role
    return str(getattr(role, "value", role)).upper()


def require_staff(user: User) -> None:
    if role_name(user) not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage volunteers.",
        )


def get_volunteer_or_404(
    db: Session,
    volunteer_id: int,
) -> Volunteer:
    volunteer = VolunteerRepository.get_by_id(db, volunteer_id)

    if volunteer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Volunteer profile not found.",
        )

    return volunteer


def ensure_owner_or_staff(
    user: User,
    volunteer: Volunteer,
) -> None:
    if volunteer.user_id != user.id and role_name(user) not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another volunteer's profile.",
        )


@router.post(
    "",
    response_model=VolunteerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_volunteer_profile(
    payload: VolunteerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerService.create_profile(
            db,
            current_user,
            payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=VolunteerResponse,
)
def get_my_volunteer_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return VolunteerService.get_my_profile(db, current_user)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=VolunteerListResponse,
)
def list_volunteers(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    volunteer_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(PENDING|ACTIVE|INACTIVE)$",
    ),
    availability: str | None = Query(
        default=None,
        pattern="^(WEEKDAYS|WEEKENDS|EVENINGS|FLEXIBLE|CUSTOM)$",
    ),
    search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_staff(current_user)

    volunteers, total = VolunteerRepository.list(
        db=db,
        page=page,
        page_size=page_size,
        status=volunteer_status,
        availability=availability,
        search=search,
    )

    return VolunteerListResponse(
        items=volunteers,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{volunteer_id}",
    response_model=VolunteerResponse,
)
def get_volunteer_profile(
    volunteer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    volunteer = get_volunteer_or_404(db, volunteer_id)
    ensure_owner_or_staff(current_user, volunteer)
    return volunteer


@router.patch(
    "/{volunteer_id}",
    response_model=VolunteerResponse,
)
def update_volunteer_profile(
    volunteer_id: int,
    payload: VolunteerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    volunteer = get_volunteer_or_404(db, volunteer_id)
    ensure_owner_or_staff(current_user, volunteer)

    data = payload.model_dump(exclude_unset=True)

    # Only staff can change profile status; status is not accepted here.
    try:
        return VolunteerService.update_profile(db, volunteer, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{volunteer_id}/status",
    response_model=VolunteerResponse,
)
def update_volunteer_status(
    volunteer_id: int,
    payload: VolunteerStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_staff(current_user)
    volunteer = get_volunteer_or_404(db, volunteer_id)

    return VolunteerService.update_status(
        db,
        volunteer,
        payload.status,
    )
