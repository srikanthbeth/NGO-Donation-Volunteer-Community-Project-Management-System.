
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_token,
    password_reset_expiry,
    refresh_token_expiry,
    verify_password,
)
from models.user import User, UserRole
from repositories.user_repository import UserRepository
from schemas.auth import UserRegister


class AuthService:
    """Authentication and account security business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    @staticmethod
    def _unauthorized() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _issue_access_token(user: User) -> str:
        return create_access_token(user.id, user.role)

    def _issue_refresh_token(self, user: User) -> str:
        raw_token = create_refresh_token()

        self.users.create_refresh_token(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=refresh_token_expiry(),
        )

        return raw_token

    def _token_response(self, user: User) -> dict:
        return {
            "access_token": self._issue_access_token(user),
            "refresh_token": self._issue_refresh_token(user),
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    def register(self, data: UserRegister) -> User:
        email = str(data.email).strip().lower()

        if self.users.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        try:
            user = self.users.create_user(
                full_name=data.full_name,
                email=email,
                hashed_password=hash_password(data.password),
                role=UserRole.DONOR,
                is_active=True,
                is_verified=False,
            )
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

    def login(self, email: str, password: str) -> dict:
        user = self.users.get_by_email(email)

        if user is None or not verify_password(
            password, user.hashed_password
        ):
            raise self._unauthorized()

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive.",
            )

        try:
            result = self._token_response(user)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def refresh(self, raw_refresh_token: str) -> dict:
        token_digest = hash_token(raw_refresh_token)

        try:
            record = self.users.get_refresh_token(
                token_digest,
                for_update=True,
            )

            now = datetime.now(timezone.utc)

            if record is None or record.revoked_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or revoked refresh token.",
                )

            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has expired.",
                )

            user = self.users.get_by_id_for_update(record.user_id)

            if user is None or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is unavailable.",
                )

            # Rotate the refresh token: the old token cannot be reused.
            self.users.revoke_refresh_token(record)
            result = self._token_response(user)

            self.db.commit()
            return result

        except Exception:
            self.db.rollback()
            raise

    def logout(self, raw_refresh_token: str) -> dict:
        try:
            record = self.users.get_refresh_token(
                hash_token(raw_refresh_token),
                for_update=True,
            )

            if record is not None and record.revoked_at is None:
                self.users.revoke_refresh_token(record)

            self.db.commit()

            # Idempotent logout: do not disclose whether a token existed.
            return {"message": "Logged out successfully."}

        except Exception:
            self.db.rollback()
            raise

    def request_password_reset(self, email: str) -> dict:
        """Return a generic response to avoid revealing registered emails."""
        generic_response = {
            "message": (
                "If an eligible account exists, password reset instructions "
                "will be provided."
            )
        }

        user = self.users.get_by_email(email)

        if user is None or not user.is_active:
            return generic_response

        try:
            self.users.invalidate_unused_password_reset_tokens(user.id)

            raw_token = create_password_reset_token()

            self.users.create_password_reset_token(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=password_reset_expiry(),
            )

            self.db.commit()

            # Local testing only. Production must deliver the token through
            # a verified email delivery workflow and never return it in HTTP.
            if settings.ENVIRONMENT == "development":
                return {
                    **generic_response,
                    "development_reset_token": raw_token,
                }

            return generic_response

        except Exception:
            self.db.rollback()
            raise

    def confirm_password_reset(
        self,
        raw_token: str,
        new_password: str,
    ) -> dict:
        try:
            record = self.users.get_password_reset_token(
                hash_token(raw_token),
                for_update=True,
            )

            now = datetime.now(timezone.utc)

            if record is None or record.used_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or already-used password reset token.",
                )

            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password reset token has expired.",
                )

            user = self.users.get_by_id_for_update(record.user_id)

            if user is None or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password reset is unavailable for this account.",
                )

            user.hashed_password = hash_password(new_password)
            record.used_at = now

            # Invalidate other outstanding reset links and all existing
            # refresh sessions after a successful password change.
            self.users.invalidate_unused_password_reset_tokens(user.id)
            self.users.revoke_all_refresh_tokens(user.id)

            self.db.commit()

            return {
                "message": (
                    "Password reset successfully. Please log in again."
                )
            }

        except Exception:
            self.db.rollback()
            raise

    def set_account_active(
        self,
        user_id: int,
        is_active: bool,
    ) -> User:
        try:
            user = self.users.get_by_id_for_update(user_id)

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                )

            user.is_active = is_active

            if not is_active:
                self.users.revoke_all_refresh_tokens(user.id)

            self.db.flush()
            self.db.commit()
            self.db.refresh(user)

            return user

        except Exception:
            self.db.rollback()
            raise

    def get_current_user_from_token(self, access_token: str) -> User:
        try:
            payload = decode_access_token(access_token)
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        user = self.users.get_by_id(user_id)

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is unavailable.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
