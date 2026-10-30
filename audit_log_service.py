
from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.user import User


class AuditLogService:
    """Create audit entries in the caller's database transaction."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        actor: User | None,
        action: str,
        entity_type: str,
        entity_id: int | str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        if not action.strip():
            raise ValueError("Audit action cannot be empty.")

        if not entity_type.strip():
            raise ValueError("Audit entity_type cannot be empty.")

        entry = AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            action=action.strip().upper(),
            entity_type=entity_type.strip().upper(),
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details or {},
            ip_address=ip_address,
        )

        self.db.add(entry)
        self.db.flush()

        if commit:
            self.db.commit()
            self.db.refresh(entry)

        return entry
