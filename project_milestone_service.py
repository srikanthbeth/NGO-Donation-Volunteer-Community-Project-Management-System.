
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.project import Project
from models.project_milestone import ProjectMilestone
from repositories.project_milestone_repository import (
    ProjectMilestoneRepository,
)


class ProjectMilestoneService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjectMilestoneRepository(db)

    def create(self, data: dict, created_by: int) -> ProjectMilestone:
        project = self.db.get(Project, data["project_id"])
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        if project.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create a milestone for a cancelled project.",
            )

        payload = {**data, "created_by": created_by}
        return self.repository.create(payload)

    def get_by_id(self, milestone_id: int) -> ProjectMilestone:
        milestone = self.repository.get_by_id(milestone_id)
        if milestone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project milestone not found.",
            )
        return milestone

    def list(
        self,
        project_id: int | None = None,
        status_filter: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        if project_id is not None and self.db.get(Project, project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        items, total = self.repository.list(
            project_id=project_id,
            status=status_filter,
            search=search,
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

    def update(
        self, milestone_id: int, data: dict
    ) -> ProjectMilestone:
        milestone = self.get_by_id(milestone_id)

        if milestone.status == "CANCELLED" and data.get("status") != "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A cancelled milestone cannot be reopened.",
            )

        return self.repository.update(milestone, data)

    def delete(self, milestone_id: int) -> None:
        milestone = self.get_by_id(milestone_id)
        self.repository.delete(milestone)
