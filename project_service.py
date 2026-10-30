
from sqlalchemy.orm import Session

from models.project import Project
from models.user import User, UserRole
from repositories.project_repository import ProjectRepository
from schemas.project import ProjectCreate, ProjectUpdate


PROJECT_MANAGERS = {
    UserRole.SUPER_ADMIN,
    UserRole.NGO_MANAGER,
}


def _require_project_manager(user: User) -> None:
    if user.role not in PROJECT_MANAGERS:
        raise PermissionError("You do not have permission to manage projects.")


def create_project_record(
    db: Session,
    payload: ProjectCreate,
    current_user: User,
) -> Project:
    _require_project_manager(current_user)

    data = payload.model_dump()
    project = ProjectRepository(db).create(
        {
            **data,
            "created_by": current_user.id,
        }
    )
    return project


def get_project_record(db: Session, project_id: int) -> Project:
    project = ProjectRepository(db).get_by_id(project_id)
    if project is None:
        raise LookupError("Project not found.")
    return project


def list_project_records(
    db: Session,
    *,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    items, total = ProjectRepository(db).list(
        search=search,
        status_filter=status_filter,
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


def update_project_record(
    db: Session,
    project_id: int,
    payload: ProjectUpdate,
    current_user: User,
) -> Project:
    _require_project_manager(current_user)

    repository = ProjectRepository(db)
    project = repository.get_by_id(project_id)
    if project is None:
        raise LookupError("Project not found.")

    updates = payload.model_dump(exclude_unset=True)

    # Avoid accepting null for required fields.
    for field in ("title", "description", "start_date", "budget", "currency", "status"):
        if field in updates and updates[field] is None:
            raise ValueError(f"{field} cannot be null.")

    start_date = updates.get("start_date", project.start_date)
    end_date = updates.get("end_date", project.end_date)
    if end_date is not None and end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")

    if "title" in updates and not updates["title"].strip():
        raise ValueError("title must not be blank.")

    if "description" in updates and not updates["description"].strip():
        raise ValueError("description must not be blank.")

    return repository.update(project, updates)
