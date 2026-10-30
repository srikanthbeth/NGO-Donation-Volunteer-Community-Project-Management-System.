
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.auth import (
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserRegister,
    db: Session = Depends(get_db),
):
    """Register a new donor account."""
    return AuthService(db).register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
):
    """Authenticate with email and password."""
    return AuthService(db).login(
        email=str(data.email),
        password=data.password,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Rotate a refresh token and issue new tokens."""
    return AuthService(db).refresh(data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
def logout(
    data: LogoutRequest,
    db: Session = Depends(get_db),
):
    """Revoke a refresh token."""
    return AuthService(db).logout(data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    return current_user


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_200_OK,
)
def request_password_reset(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Request a password reset without revealing account existence."""
    return AuthService(db).request_password_reset(str(data.email))


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
)
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Set a new password using a valid reset token."""
    return AuthService(db).confirm_password_reset(
        raw_token=data.token,
        new_password=data.new_password,
    )
