
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


ApprovalStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class ProjectApprovalCreate(BaseModel):
    project_id: int = Field(gt=0)
    request_comments: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("request_comments")
    @classmethod
    def validate_request_comments(
        cls, value: str | None
    ) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value


class ProjectApprovalReview(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    review_comments: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("review_comments")
    @classmethod
    def validate_review_comments(
        cls, value: str | None
    ) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                return None
        return value


class ProjectApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    requested_by: int
    reviewed_by: int | None
    status: ApprovalStatus
    request_comments: str | None
    review_comments: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectApprovalListResponse(BaseModel):
    items: list[ProjectApprovalResponse]
    total: int
    page: int
    page_size: int
