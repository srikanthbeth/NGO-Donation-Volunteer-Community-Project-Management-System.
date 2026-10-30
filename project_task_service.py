
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.project import Project
from models.project_milestone import ProjectMilestone
from models.project_task import ProjectTask
from models.volunteer import Volunteer
from repositories.project_task_repository import ProjectTaskRepository


class ProjectTaskService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjectTaskRepository(db)

    def _validate_references(
        self,
        project_id: int,
        milestone_id: int | None = None,
        assigned_volunteer_id: int | None = None,
    ) -> None:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        if project.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign tasks to a cancelled project.",
            )

        if milestone_id is not None:
            milestone = self.db.get(ProjectMilestone, milestone_id)
            if milestone is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project milestone not found.",
                )

            if milestone.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Milestone must belong to the selected project.",
                )

            if milestone.status == "CANCELLED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign a task to a cancelled milestone.",
                )

        if assigned_volunteer_id is not None:
            volunteer = self.db.get(Volunteer, assigned_volunteer_id)
            if volunteer is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Volunteer not found.",
                )

            if volunteer.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only active volunteers can be assigned tasks.",
                )

    def create(self, data: dict, created_by: int) -> ProjectTask:
        self._validate_references(
            project_id=data["project_id"],
            milestone_id=data.get("milestone_id"),
            assigned_volunteer_id=data.get("assigned_volunteer_id"),
        )

        payload = {**data, "created_by": created_by}

        if payload.get("status") == "COMPLETED":
            payload["completed_at"] = datetime.now(timezone.utc)

        return self.repository.create(payload)

    def get_by_id(self, task_id: int) -> ProjectTask:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project task not found.",
            )
        return task

    def list(
        self,
        project_id: int | None = None,
        milestone_id: int | None = None,
        assigned_volunteer_id: int | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
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

        if milestone_id is not None:
            milestone = self.db.get(ProjectMilestone, milestone_id)
            if milestone is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project milestone not found.",
                )
            if project_id is not None and milestone.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Milestone does not belong to the selected project.",
                )

        if assigned_volunteer_id is not None:
            if self.db.get(Volunteer, assigned_volunteer_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Volunteer not found.",
                )

        items, total = self.repository.list(
            project_id=project_id,
            milestone_id=milestone_id,
            assigned_volunteer_id=assigned_volunteer_id,
            status=status_filter,
            priority=priority,
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

    def update(self, task_id: int, data: dict) -> ProjectTask:
        task = self.get_by_id(task_id)

        project_id = task.project_id
        milestone_id = data.get("milestone_id", task.milestone_id)
        volunteer_id = data.get(
            "assigned_volunteer_id", task.assigned_volunteer_id
        )

        self._validate_references(
            project_id=project_id,
            milestone_id=milestone_id,
            assigned_volunteer_id=volunteer_id,
        )

        if data.get("status") == "COMPLETED":
            if task.status != "COMPLETED":
                data["completed_at"] = datetime.now(timezone.utc)

        elif data.get("status") in {
            "TODO",
            "IN_PROGRESS",
            "BLOCKED",
            "CANCELLED",
        }:
            data["completed_at"] = None

        return self.repository.update(task, data)

    def delete(self, task_id: int) -> None:
        task = self.get_by_id(task_id)
        self.repository.delete(task)
