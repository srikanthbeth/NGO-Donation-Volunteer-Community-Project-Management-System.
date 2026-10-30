from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.session import get_db
from models.audit_log import AuditLog
from models.user import User, UserRole
from routes.dependencies import get_current_user, require_roles
from schemas.audit_log import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    actor_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: str | None = Query(default=None, min_length=1, max_length=100),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.NGO_MANAGER)
    ),
):
    """List audit logs with filters. Audit logs are read-only through this API."""

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be earlier than or equal to end_date.",
        )

    query = db.query(AuditLog)

    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)

    if action:
        query = query.filter(AuditLog.action == action.strip().upper())

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.strip().upper())

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    total = query.with_entities(func.count(AuditLog.id)).scalar() or 0

    items = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (total + page_size - 1) // page_size

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{audit_log_id}", response_model=AuditLogResponse)
def get_audit_log(
    audit_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.NGO_MANAGER)
    ),
):
    """Retrieve one audit log. Audit records cannot be changed via this API."""

    entry = db.query(AuditLog).filter(AuditLog.id == audit_log_id).first()

    if entry is None:
        raise HTTPException(status_code=404, detail="Audit log not found.")

    return entry
