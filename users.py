
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_super_admin
from schemas.auth import AccountStatusUpdate, UserResponse, UserRoleUpdate
from services.user_service import UserService


router = APIRouter(
    prefix="/users",
    tags=["User Administration"],
)


@router.get("", response_model=list[UserResponse])
def list_users(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    role: str | None = None,
    is_active: bool | None = None,
    search: Annotated[str | None, Query(max_length=150)] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    return UserService(db).list_users(
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
        search=search,
    )


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: Annotated[int, Path(gt=0)],
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    return UserService(db).update_role(
        user_id=user_id,
        data=data,
        actor=admin,
    )


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: Annotated[int, Path(gt=0)],
    data: AccountStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    return UserService(db).set_account_active(
        user_id=user_id,
        is_active=data.is_active,
        actor=admin,
    )
