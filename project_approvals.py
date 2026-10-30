
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.project_approval import (
    ProjectApprovalCreate,
    ProjectApprovalListResponse,
    ProjectApprovalResponse,
    ProjectApprovalReview,
)
from services.project_approval_service import ProjectApprovalService

router = APIRouter(
    prefix="/api/v1/project-approvals",
    tags=["Project Approvals"],
)


@router.post(
    "",
    response_model=ProjectApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_approval_request(
    payload: ProjectApprovalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectApprovalService(db)
    return service.submit_request(
        project_id=payload.project_id,
        current_user=current_user,
        request_comments=payload.request_comments,
    )


@router.get(
    "",
    response_model=ProjectApprovalListResponse,
)
def list_approval_requests(
    project_id: int | None = Query(default=None, gt=0),
    approval_status: str | None = Query(
        default=None,
        pattern="^(PENDING|APPROVED|REJECTED)$",
    ),
    requested_by: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(
        default="submitted_at",
        pattern="^(id|project_id|status|submitted_at|reviewed_at|created_at|updated_at)$",
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectApprovalService(db)
    items, total = service.list_requests(
        current_user=current_user,
        project_id=project_id,
        approval_status=approval_status,
        requested_by=requested_by,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{approval_id}",
    response_model=ProjectApprovalResponse,
)
def get_approval_request(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectApprovalService(db)
    approval = service.get_request(approval_id)

    role = current_user.role
    role = role.value if hasattr(role, "value") else str(role)

    if role != "SUPER_ADMIN" and approval.requested_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot view this approval request.",
        )

    return approval


@router.patch(
    "/{approval_id}/review",
    response_model=ProjectApprovalResponse,
)
def review_approval_request(
    approval_id: int,
    payload: ProjectApprovalReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProjectApprovalService(db)
    return service.review_request(
        approval_id=approval_id,
        current_user=current_user,
        review_status=payload.status,
        review_comments=payload.review_comments,
    )
