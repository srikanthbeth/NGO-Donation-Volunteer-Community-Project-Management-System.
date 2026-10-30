
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


BeneficiaryCategory = Literal[
    "CHILDREN",
    "FAMILIES",
    "ELDERLY",
    "MEDICAL_ASSISTANCE",
    "DISABILITY_SUPPORT",
    "OTHER",
]

BeneficiaryStatus = Literal["ACTIVE", "INACTIVE"]


class BeneficiaryCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    category: BeneficiaryCategory
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

    @field_validator("gender", "phone", "address", "city", "notes")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value or None
        return value


class BeneficiaryUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    category: BeneficiaryCategory | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    status: BeneficiaryStatus | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if len(value) < 2:
                raise ValueError("Full name must contain at least 2 characters")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

    @field_validator("gender", "phone", "address", "city", "notes")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            return value or None
        return value


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    category: BeneficiaryCategory
    date_of_birth: date | None
    gender: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    notes: str | None
    status: BeneficiaryStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class BeneficiaryListResponse(BaseModel):
    items: list[BeneficiaryResponse]
    total: int
    page: int
    page_size: int


class BeneficiaryStatusUpdate(BaseModel):
    status: BeneficiaryStatus


class BeneficiaryProjectCreate(BaseModel):
    project_id: int = Field(gt=0)
    notes: str | None = None


class BeneficiaryProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    beneficiary_id: int
    project_id: int
    notes: str | None
    linked_by: int
    created_at: datetime


class BeneficiaryProjectListResponse(BaseModel):
    items: list[BeneficiaryProjectResponse]
    total: int
    page: int
    page_size: int


class AssistanceCreate(BaseModel):
    beneficiary_id: int = Field(gt=0)
    project_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    assistance_type: str = Field(min_length=2, max_length=100)
    description: str | None = None
    quantity: int = Field(default=1, gt=0)
    distribution_date: date
    notes: str | None = None

    @field_validator("assistance_type")
    @classmethod
    def validate_assistance_type(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Assistance type must contain at least 2 characters")
        return value


class AssistanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    beneficiary_id: int
    project_id: int | None
    resource_id: int | None
    assistance_type: str
    description: str | None
    quantity: int
    distribution_date: date
    notes: str | None
    recorded_by: int
    created_at: datetime


class AssistanceListResponse(BaseModel):
    items: list[AssistanceResponse]
    total: int
    page: int
    page_size: int
