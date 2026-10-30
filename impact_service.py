
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.impact_update import ImpactUpdate
from models.project import Project
from models.user import User


MANAGER_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}


class ImpactService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def require_manager(user: User) -> None:
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Inactive users cannot access impact tracking.",
            )

        if user.role not in MANAGER_ROLES:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Only Super Admins and NGO Managers "
                    "can manage impact reports."
                ),
            )

    def create_update(
        self,
        project_id: int,
        payload,
        user: User,
    ) -> ImpactUpdate:
        self.require_manager(user)

        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=404,
                detail="Project not found.",
            )

        update = ImpactUpdate(
            project_id=project_id,
            beneficiaries_served=payload.beneficiaries_served,
            volunteer_hours=payload.volunteer_hours,
            resources_distributed=payload.resources_distributed,
            projects_completed=payload.projects_completed,
            funds_utilized=payload.funds_utilized,
            milestones_achieved=payload.milestones_achieved,
            notes=payload.notes,
            submitted_by=user.id,
        )

        self.db.add(update)
        self.db.commit()
        self.db.refresh(update)

        return update

    def list_updates(
        self,
        project_id: int,
        user: User,
        page: int = 1,
        page_size: int = 10,
    ):
        self.require_manager(user)

        if self.db.get(Project, project_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Project not found.",
            )

        query = select(ImpactUpdate).where(
            ImpactUpdate.project_id == project_id
        )

        total = self.db.scalar(
            select(func.count()).select_from(query.subquery())
        ) or 0

        items = self.db.scalars(
            query.order_by(
                ImpactUpdate.created_at.desc(),
                ImpactUpdate.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return items, total

    def get_summary(self, project_id: int, user: User) -> dict:
        self.require_manager(user)

        if self.db.get(Project, project_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Project not found.",
            )

        row = self.db.execute(
            select(
                func.count(ImpactUpdate.id),
                func.coalesce(
                    func.sum(ImpactUpdate.beneficiaries_served), 0
                ),
                func.coalesce(
                    func.sum(ImpactUpdate.volunteer_hours),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(ImpactUpdate.resources_distributed), 0
                ),
                func.coalesce(
                    func.sum(ImpactUpdate.projects_completed), 0
                ),
                func.coalesce(
                    func.sum(ImpactUpdate.funds_utilized),
                    Decimal("0.00"),
                ),
                func.coalesce(
                    func.sum(ImpactUpdate.milestones_achieved), 0
                ),
            ).where(ImpactUpdate.project_id == project_id)
        ).one()

        return {
            "project_id": project_id,
            "update_count": row[0],
            "beneficiaries_served": row[1],
            "volunteer_hours": Decimal(str(row[2])).quantize(
                Decimal("0.01")
            ),
            "resources_distributed": row[3],
            "projects_completed": row[4],
            "funds_utilized": Decimal(str(row[5])).quantize(
                Decimal("0.01")
            ),
            "milestones_achieved": row[6],
        }
