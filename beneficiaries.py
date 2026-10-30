
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.beneficiary import (
    AssistanceCreate,
    AssistanceListResponse,
    AssistanceResponse,
    BeneficiaryCreate,
    BeneficiaryListResponse,
    BeneficiaryProjectCreate,
    BeneficiaryProjectListResponse,
    BeneficiaryProjectResponse,
    BeneficiaryResponse,
    BeneficiaryUpdate,
)
from services.beneficiary_service import BeneficiaryService


router = APIRouter(
    prefix="/api/v1/beneficiaries",
    tags=["Beneficiaries"],
)


@router.post(
    "",
    response_model=BeneficiaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_beneficiary(
    payload: BeneficiaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BeneficiaryService(db).create_beneficiary(
        payload,
        current_user,
    )


@router.get("", response_model=BeneficiaryListResponse)
def list_beneficiaries(
    category: str | None = Query(
        None,
        pattern=(
            "^(CHILDREN|FAMILIES|ELDERLY|MEDICAL_ASSISTANCE|"
            "DISABILITY_SUPPORT|OTHER)$"
        ),
    ),
    beneficiary_status: str | None = Query(
        None,
        alias="status",
        pattern="^(ACTIVE|INACTIVE)$",
    ),
    city: str | None = Query(None, max_length=100),
    search: str | None = Query(None, max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = BeneficiaryService(db).list_beneficiaries(
        current_user,
        category=category,
        beneficiary_status=beneficiary_status,
        city=city,
        search=search,
        page=page,
        page_size=page_size,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{beneficiary_id}",
    response_model=BeneficiaryResponse,
)
def get_beneficiary(
    beneficiary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BeneficiaryService(db).get_beneficiary(
        beneficiary_id,
        current_user,
    )


@router.patch(
    "/{beneficiary_id}",
    response_model=BeneficiaryResponse,
)
def update_beneficiary(
    beneficiary_id: int,
    payload: BeneficiaryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BeneficiaryService(db).update_beneficiary(
        beneficiary_id,
        payload,
        current_user,
    )


@router.post(
    "/{beneficiary_id}/projects",
    response_model=BeneficiaryProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_beneficiary_to_project(
    beneficiary_id: int,
    payload: BeneficiaryProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BeneficiaryService(db).link_project(
        beneficiary_id,
        payload,
        current_user,
    )


@router.get(
    "/{beneficiary_id}/projects",
    response_model=BeneficiaryProjectListResponse,
)
def list_beneficiary_projects(
    beneficiary_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = BeneficiaryService(db).list_beneficiary_projects(
        beneficiary_id,
        current_user,
        page=page,
        page_size=page_size,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/assistance",
    response_model=AssistanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_assistance(
    payload: AssistanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return BeneficiaryService(db).record_assistance(
        payload,
        current_user,
    )


@router.get(
    "/{beneficiary_id}/assistance",
    response_model=AssistanceListResponse,
)
def list_beneficiary_assistance(
    beneficiary_id: int,
    project_id: int | None = Query(None, gt=0),
    resource_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = BeneficiaryService(db).list_assistance(
        beneficiary_id,
        current_user,
        project_id=project_id,
        resource_id=resource_id,
        page=page,
        page_size=page_size,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
