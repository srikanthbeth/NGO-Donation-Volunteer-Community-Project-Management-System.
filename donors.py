
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from routes.dependencies import get_current_user
from schemas.donor import DonorCreate, DonorListResponse, DonorResponse, DonorUpdate
from services import donor_service


router = APIRouter(prefix="/donors", tags=["Donors"])


@router.post(
    "",
    response_model=DonorResponse,
    status_code=201,
)
def create_donor(
    data: DonorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return donor_service.create_donor(db, data, current_user)


@router.get(
    "/me",
    response_model=DonorResponse,
)
def get_my_donor_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return donor_service.get_my_donor_profile(db, current_user)


@router.get(
    "",
    response_model=DonorListResponse,
)
def list_donors(
    search: str | None = Query(default=None, max_length=200),
    donor_type: Literal["INDIVIDUAL", "ORGANIZATION"] | None = None,
    city: str | None = Query(default=None, max_length=100),
    country: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal[
        "id", "created_at", "updated_at", "city", "country", "donor_type"
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return donor_service.list_donors_response(
        db,
        current_user,
        search=search,
        donor_type=donor_type,
        city=city,
        country=country,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/{donor_id}",
    response_model=DonorResponse,
)
def get_donor(
    donor_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return donor_service.get_donor(db, donor_id, current_user)


@router.patch(
    "/{donor_id}",
    response_model=DonorResponse,
)
def update_donor(
    donor_id: int,
    data: DonorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return donor_service.update_donor(db, donor_id, data, current_user)
