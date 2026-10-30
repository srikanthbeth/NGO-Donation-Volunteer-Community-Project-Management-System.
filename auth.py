
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.user import UserRole


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = " ".join(value.split())

        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters.")

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain a lowercase letter.")

        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain an uppercase letter.")

        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain a number.")

        if not any(not char.isalnum() for char in value):
            raise ValueError("Password must contain a special character.")

        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain a lowercase letter.")

        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain an uppercase letter.")

        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain a number.")

        if not any(not char.isalnum() for char in value):
            raise ValueError("Password must contain a special character.")

        return value


class AccountStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: Literal[
        "NGO_MANAGER",
        "FINANCE_OFFICER",
        "VOLUNTEER_COORDINATOR",
        "VOLUNTEER",
        "DONOR",
    ]
