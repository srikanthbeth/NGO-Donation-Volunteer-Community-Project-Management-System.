
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.project import Project
from models.project_approval import ProjectApproval
from repositories.project_approval_repository import (
    ProjectApprovalRepository,
)


class ProjectApprovalService:
    REVIEWER_ROLES = {"SUPER_ADMIN"}
    REQUESTER_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjectApprovalRepository(db)

    @staticmethod
    def _role(user) -> str:
        role = user.role
        return role.value if hasattr(role, "value") else str(role)

    def submit_request(
        self,
        project_id: int,
        current_user,
        request_comments: str | None = None,
    ) -> ProjectApproval:
        if self._role(current_user) not in self.REQUESTER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to submit projects for approval.",
            )

        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        if getattr(project, "status", None) in {
            "CANCELLED",
            "COMPLETED",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cancelled or completed projects cannot be submitted for approval.",
            )

        existing_items, _ = self.repository.list(
            project_id=project_id,
            approval_status="PENDING",
            page=1,
            page_size=1,
        )
        if existing_items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This project already has a pending approval request.",
            )

        return self.repository.create(
            {
                "project_id": project_id,
                "requested_by": current_user.id,
                "status": "PENDING",
                "request_comments": request_comments,
            }
        )

    def review_request(
        self,
        approval_id: int,
        current_user,
        review_status: str,
        review_comments: str | None = None,
    ) -> ProjectApproval:
        if self._role(current_user) not in self.REVIEWER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super administrator can review approval requests.",
            )

        approval = self.repository.get_by_id(approval_id)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found.",
            )

        if approval.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This approval request has already been reviewed.",
            )

        normalized_status = review_status.upper()
        if normalized_status not in {"APPROVED", "REJECTED"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Review status must be APPROVED or REJECTED.",
            )

        return self.repository.update(
            approval,
            {
                "status": normalized_status,
                "reviewed_by": current_user.id,
                "review_comments": review_comments,
                "reviewed_at": datetime.now(timezone.utc),
            },
        )

    def get_request(self, approval_id: int) -> ProjectApproval:
        approval = self.repository.get_by_id(approval_id)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found.",
            )
        return approval

    def list_requests(
        self,
        current_user,
        project_id: int | None = None,
        approval_status: str | None = None,
        requested_by: int | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "submitted_at",
        sort_order: str = "desc",
    ) -> tuple[list[ProjectApproval], int]:
        role = self._role(current_user)

        if role not in self.REVIEWER_ROLES:
            # Non-reviewers can see only requests they submitted.
            requested_by = current_user.id

        return self.repository.list(
            project_id=project_id,
            approval_status=approval_status,
            requested_by=requested_by,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
