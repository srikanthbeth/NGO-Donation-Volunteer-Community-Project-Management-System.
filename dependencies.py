
from collections.abc import Callable, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User, UserRole
from services.auth_service import AuthService


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the request and load the current active user."""

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthService(db).get_current_user_from_token(token)


def require_roles(*allowed_roles: str) -> Callable:
    """Build a dependency that permits only specified roles."""

    invalid_roles = set(allowed_roles) - set(UserRole.ALL)
    if invalid_roles:
        raise ValueError(f"Unknown role(s): {sorted(invalid_roles)}")

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker


def get_super_admin(
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
) -> User:
    """Allow only Super Admin users."""
    return current_user


def get_finance_user(
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.FINANCE_OFFICER)
    ),
) -> User:
    """Allow Super Admin and Finance Officer users."""
    return current_user


def get_ngo_manager(
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.NGO_MANAGER)
    ),
) -> User:
    """Allow Super Admin and NGO Manager users."""
    return current_user
