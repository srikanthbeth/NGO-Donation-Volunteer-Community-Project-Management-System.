
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DonorType = Literal["INDIVIDUAL", "ORGANIZATION"]
ContactMethod = Literal["EMAIL", "PHONE", "SMS"]


class DonorCreate(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    donor_type: DonorType = "INDIVIDUAL"
    organization_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=25)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    preferred_contact_method: ContactMethod = "EMAIL"
    anonymous_default: bool = False

    @field_validator(
        "organization_name", "phone", "address", "city",
        "state", "country", "postal_code",
    )
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_organization(self):
        if self.donor_type == "ORGANIZATION" and not self.organization_name:
            raise ValueError(
                "organization_name is required for organization donors"
            )
        if self.donor_type == "INDIVIDUAL" and self.organization_name:
            raise ValueError(
                "organization_name is only allowed for organization donors"
            )
        return self


class DonorUpdate(BaseModel):
    donor_type: DonorType | None = None
    organization_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=25)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    preferred_contact_method: ContactMethod | None = None
    anonymous_default: bool | None = None

    @field_validator(
        "organization_name", "phone", "address", "city",
        "state", "country", "postal_code",
    )
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class DonorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    donor_type: DonorType
    organization_name: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    preferred_contact_method: ContactMethod
    anonymous_default: bool
    created_at: datetime
    updated_at: datetime


class DonorListResponse(BaseModel):
    items: list[DonorResponse]
    total: int
    page: int
    page_size: int
    pages: int
