
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from repositories import donor_repository as repository
from schemas.donor import DonorCreate, DonorListResponse, DonorResponse, DonorUpdate


STAFF_ROLES = {"SUPER_ADMIN", "NGO_MANAGER", "FINANCE_OFFICER"}
SORT_FIELDS = {"id", "created_at", "updated_at", "city", "country", "donor_type"}


def role_value(user) -> str:
    role = user.role
    return str(getattr(role, "value", role)).upper()


def ensure_staff(user) -> None:
    if role_value(user) not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage donor records",
        )


def ensure_donor_access(donor, user) -> None:
    if role_value(user) in STAFF_ROLES:
        return

    if role_value(user) != "DONOR" or donor.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this donor profile",
        )


def create_donor(
    db: Session,
    data: DonorCreate,
    current_user,
) -> DonorResponse:
    role = role_value(current_user)

    if role == "DONOR":
        user_id = current_user.id
    elif role in STAFF_ROLES:
        if data.user_id is None:
            raise HTTPException(
                status_code=422,
                detail="user_id is required when staff create a donor profile",
            )
        user_id = data.user_id
    else:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to create donor profiles",
        )

    target_user = repository.get_user_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_role = str(getattr(target_user.role, "value", target_user.role)).upper()
    if target_role != "DONOR":
        raise HTTPException(
            status_code=422,
            detail="A donor profile can only be created for a user with DONOR role",
        )

    if repository.get_donor_by_user_id(db, user_id):
        raise HTTPException(
            status_code=409,
            detail="A donor profile already exists for this user",
        )

    payload = data.model_dump(exclude={"user_id"})
    payload["user_id"] = user_id

    try:
        donor = repository.create_donor(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A donor profile already exists for this user",
        ) from exc

    return DonorResponse.model_validate(donor)


def get_donor(
    db: Session,
    donor_id: int,
    current_user,
) -> DonorResponse:
    donor = repository.get_donor_by_id(db, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    ensure_donor_access(donor, current_user)
    return DonorResponse.model_validate(donor)


def get_my_donor_profile(db: Session, current_user) -> DonorResponse:
    if role_value(current_user) != "DONOR":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available to donor accounts",
        )

    donor = repository.get_donor_by_user_id(db, current_user.id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor profile not found")

    return DonorResponse.model_validate(donor)


def update_donor(
    db: Session,
    donor_id: int,
    data: DonorUpdate,
    current_user,
) -> DonorResponse:
    donor = repository.get_donor_by_id(db, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")

    ensure_donor_access(donor, current_user)

    changes = data.model_dump(exclude_unset=True)

    new_type = changes.get("donor_type", donor.donor_type)
    new_organization = changes.get(
        "organization_name", donor.organization_name
    )

    if new_type == "ORGANIZATION" and not new_organization:
        raise HTTPException(
            status_code=422,
            detail="organization_name is required for organization donors",
        )

    if new_type == "INDIVIDUAL" and new_organization:
        raise HTTPException(
            status_code=422,
            detail="organization_name is only allowed for organization donors",
        )

    updated = repository.update_donor(db, donor, changes)
    return DonorResponse.model_validate(updated)


def list_donors_response(
    db: Session,
    current_user,
    *,
    search: str | None,
    donor_type: str | None,
    city: str | None,
    country: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> DonorListResponse:
    ensure_staff(current_user)

    if sort_by not in SORT_FIELDS:
        raise HTTPException(status_code=422, detail="Invalid sort_by")

    items, total = repository.list_donors(
        db,
        search=search,
        donor_type=donor_type,
        city=city,
        country=country,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return DonorListResponse(
        items=[DonorResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )
