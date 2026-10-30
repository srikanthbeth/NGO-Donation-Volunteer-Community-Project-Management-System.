
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.auth import UserRoleUpdate


class UserService:
    """Business logic for administrative user management."""

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        role: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[User]:
        if skip < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="skip must be greater than or equal to zero.",
            )

        if not 1 <= limit <= 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="limit must be between 1 and 100.",
            )

        if role is not None and role not in UserRole.ALL:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid user role.",
            )

        return self.users.list_users(
            skip=skip,
            limit=limit,
            role=role,
            is_active=is_active,
            search=search,
        )

    def update_role(
        self,
        *,
        user_id: int,
        data: UserRoleUpdate,
        actor: User,
    ) -> User:
        """Update a user's role while protecting the Super Admin role."""

        target = self.users.get_by_id_for_update(user_id)

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Prevent changing or granting the protected Super Admin role
        # through the regular user-role endpoint.
        if target.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The Super Admin role cannot be changed here.",
            )

        if actor.id == target.id and target.role != data.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role.",
            )

        try:
            target.role = data.role
            self.db.flush()
            self.db.commit()
            self.db.refresh(target)
            return target
        except Exception:
            self.db.rollback()
            raise

    def set_account_active(
        self,
        *,
        user_id: int,
        is_active: bool,
        actor: User,
    ) -> User:
        """Activate or deactivate an account."""

        target = self.users.get_by_id_for_update(user_id)

        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if actor.id == target.id and not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )

        if target.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A Super Admin account cannot be changed here.",
            )

        try:
            target.is_active = is_active

            if not is_active:
                self.users.revoke_all_refresh_tokens(target.id)

            self.db.flush()
            self.db.commit()
            self.db.refresh(target)
            return target
        except Exception:
            self.db.rollback()
            raise
