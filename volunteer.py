
from datetime import datetime
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


AvailabilityType = Literal[
    "WEEKDAYS",
    "WEEKENDS",
    "EVENINGS",
    "FLEXIBLE",
    "CUSTOM",
]

VolunteerStatus = Literal[
    "PENDING",
    "ACTIVE",
    "INACTIVE",
]


class VolunteerBase(BaseModel):
    bio: Optional[str] = Field(
        default=None,
        max_length=5000,
    )

    skills: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    availability: AvailabilityType = "FLEXIBLE"

    hours_per_week: int = Field(
        default=0,
        ge=0,
        le=168,
    )

    experience_years: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    preferred_areas: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    emergency_contact_name: Optional[str] = Field(
        default=None,
        max_length=120,
    )

    emergency_contact_phone: Optional[str] = Field(
        default=None,
        max_length=25,
    )

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, skills: list[str]) -> list[str]:
        cleaned = []

        for skill in skills:
            skill = skill.strip()

            if not skill:
                raise ValueError("Skills cannot contain blank values.")

            if len(skill) > 100:
                raise ValueError(
                    "Each skill must contain at most 100 characters."
                )

            if skill not in cleaned:
                cleaned.append(skill)

        return cleaned

    @field_validator(
        "bio",
        "preferred_areas",
        "emergency_contact_name",
        "emergency_contact_phone",
    )
    @classmethod
    def strip_optional_strings(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()
        return value or None


class VolunteerCreate(VolunteerBase):
    pass


class VolunteerUpdate(BaseModel):
    bio: Optional[str] = Field(default=None, max_length=5000)
    skills: Optional[list[str]] = Field(default=None, max_length=50)
    availability: Optional[AvailabilityType] = None
    hours_per_week: Optional[int] = Field(default=None, ge=0, le=168)
    experience_years: Optional[int] = Field(default=None, ge=0, le=100)
    preferred_areas: Optional[str] = Field(default=None, max_length=2000)
    emergency_contact_name: Optional[str] = Field(
        default=None,
        max_length=120,
    )
    emergency_contact_phone: Optional[str] = Field(
        default=None,
        max_length=25,
    )

    @field_validator("skills")
    @classmethod
    def validate_optional_skills(
        cls,
        skills: Optional[list[str]],
    ) -> Optional[list[str]]:
        if skills is None:
            return None

        return VolunteerBase.validate_skills(skills)

    @field_validator(
        "bio",
        "preferred_areas",
        "emergency_contact_name",
        "emergency_contact_phone",
    )
    @classmethod
    def strip_optional_strings(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()
        return value or None


class VolunteerStatusUpdate(BaseModel):
    status: VolunteerStatus


class VolunteerResponse(VolunteerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: VolunteerStatus
    created_at: datetime
    updated_at: datetime


class VolunteerListResponse(BaseModel):
    items: list[VolunteerResponse]
    total: int
    page: int
    page_size: int
