
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.beneficiary import Beneficiary
from models.beneficiary_assistance import BeneficiaryAssistance
from models.resource import Resource
from models.resource_transaction import ResourceTransaction
from repositories.beneficiary_repository import BeneficiaryRepository


PROFILE_MANAGERS = {"SUPER_ADMIN", "NGO_MANAGER"}
PROFILE_CREATORS = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
}
PROFILE_READERS = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
    "FINANCE_OFFICER",
}
ASSISTANCE_RECORDERS = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
    "VOLUNTEER",
}


class BeneficiaryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BeneficiaryRepository(db)

    # --------------------------------------------------
    # Common helpers
    # --------------------------------------------------

    @staticmethod
    def _require_role(user, allowed_roles: set[str]) -> None:
        role = getattr(user, "role", None)

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise HTTPException(
                status_code=422,
                detail="Page must be greater than or equal to 1",
            )

        if page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=422,
                detail="Page size must be between 1 and 100",
            )

    def _get_beneficiary_or_404(
        self,
        beneficiary_id: int,
    ) -> Beneficiary:
        beneficiary = self.repository.get_beneficiary(beneficiary_id)

        if beneficiary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Beneficiary not found",
            )

        return beneficiary

    def _get_active_beneficiary(
        self,
        beneficiary_id: int,
    ) -> Beneficiary:
        beneficiary = self._get_beneficiary_or_404(beneficiary_id)

        if beneficiary.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inactive beneficiaries cannot receive assistance",
            )

        return beneficiary

    # --------------------------------------------------
    # Beneficiary profiles
    # --------------------------------------------------

    def create_beneficiary(self, payload, current_user):
        self._require_role(current_user, PROFILE_CREATORS)

        data = payload.model_dump()
        data["created_by"] = current_user.id
        data["status"] = "ACTIVE"

        try:
            beneficiary = self.repository.create_beneficiary(data)
            self.db.commit()
            self.db.refresh(beneficiary)
            return beneficiary
        except Exception:
            self.db.rollback()
            raise

    def get_beneficiary(self, beneficiary_id: int, current_user):
        self._require_role(current_user, PROFILE_READERS)
        return self._get_beneficiary_or_404(beneficiary_id)

    def list_beneficiaries(
        self,
        current_user,
        category: str | None = None,
        beneficiary_status: str | None = None,
        city: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        self._require_role(current_user, PROFILE_READERS)
        self._validate_page(page, page_size)

        return self.repository.list_beneficiaries(
            category=category,
            beneficiary_status=beneficiary_status,
            city=city,
            search=search,
            page=page,
            page_size=page_size,
        )

    def update_beneficiary(
        self,
        beneficiary_id: int,
        payload,
        current_user,
    ):
        self._require_role(current_user, PROFILE_MANAGERS)

        try:
            beneficiary = self.db.scalar(
                select(Beneficiary)
                .where(Beneficiary.id == beneficiary_id)
                .with_for_update()
            )

            if beneficiary is None:
                raise HTTPException(
                    status_code=404,
                    detail="Beneficiary not found",
                )

            changes = payload.model_dump(exclude_unset=True)

            if not changes:
                raise HTTPException(
                    status_code=422,
                    detail="At least one field must be provided",
                )

            if "full_name" in changes and changes["full_name"] is None:
                raise HTTPException(
                    status_code=422,
                    detail="Full name cannot be null",
                )

            if "category" in changes and changes["category"] is None:
                raise HTTPException(
                    status_code=422,
                    detail="Category cannot be null",
                )

            if "status" in changes and changes["status"] is None:
                raise HTTPException(
                    status_code=422,
                    detail="Status cannot be null",
                )

            for field, value in changes.items():
                setattr(beneficiary, field, value)

            self.db.commit()
            self.db.refresh(beneficiary)
            return beneficiary

        except Exception:
            self.db.rollback()
            raise

    # --------------------------------------------------
    # Beneficiary-project links
    # --------------------------------------------------

    def link_project(
        self,
        beneficiary_id: int,
        payload,
        current_user,
    ):
        self._require_role(current_user, PROFILE_CREATORS)

        try:
            beneficiary = self._get_active_beneficiary(beneficiary_id)
            project_id = payload.project_id

            project = self.repository.get_project(project_id)
            if project is None:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found",
                )

            existing = self.repository.get_beneficiary_project(
                beneficiary.id,
                project_id,
            )

            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Beneficiary is already linked to this project",
                )

            data = {
                "beneficiary_id": beneficiary.id,
                "project_id": project_id,
                "notes": payload.notes,
                "linked_by": current_user.id,
            }

            link = self.repository.link_project(data)
            self.db.commit()
            self.db.refresh(link)
            return link

        except Exception:
            self.db.rollback()
            raise

    def list_beneficiary_projects(
        self,
        beneficiary_id: int,
        current_user,
        page: int = 1,
        page_size: int = 10,
    ):
        self._require_role(current_user, PROFILE_READERS)
        self._validate_page(page, page_size)
        self._get_beneficiary_or_404(beneficiary_id)

        return self.repository.list_beneficiary_projects(
            beneficiary_id,
            page=page,
            page_size=page_size,
        )

    # --------------------------------------------------
    # Assistance and distribution history
    # --------------------------------------------------

    def record_assistance(self, payload, current_user):
        self._require_role(current_user, ASSISTANCE_RECORDERS)

        try:
            beneficiary = self._get_active_beneficiary(
                payload.beneficiary_id
            )

            project_id = payload.project_id

            if project_id is not None:
                project = self.repository.get_project(project_id)

                if project is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Project not found",
                    )

                link = self.repository.get_beneficiary_project(
                    beneficiary.id,
                    project_id,
                )

                if link is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Beneficiary must be linked to the project first",
                    )

            resource_id = payload.resource_id

            if resource_id is not None:
                resource = self.db.scalar(
                    select(Resource)
                    .where(Resource.id == resource_id)
                    .with_for_update()
                )

                if resource is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Resource not found",
                    )

                if resource.status != "ACTIVE":
                    raise HTTPException(
                        status_code=409,
                        detail="Inactive resources cannot be distributed",
                    )

                if resource.quantity_available < payload.quantity:
                    raise HTTPException(
                        status_code=409,
                        detail="Insufficient resource stock",
                    )

                resource.quantity_available -= payload.quantity

                transaction = ResourceTransaction(
                    resource_id=resource.id,
                    transaction_type="DISTRIBUTION",
                    quantity=payload.quantity,
                    project_id=project_id,
                    performed_by=current_user.id,
                    reference=f"BENEFICIARY-{beneficiary.id}",
                    notes=payload.notes,
                )
                self.db.add(transaction)

            data = payload.model_dump()
            data["recorded_by"] = current_user.id

            assistance = self.repository.create_assistance(data)

            self.db.commit()
            self.db.refresh(assistance)
            return assistance

        except Exception:
            self.db.rollback()
            raise

    def list_assistance(
        self,
        beneficiary_id: int,
        current_user,
        project_id: int | None = None,
        resource_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ):
        self._require_role(current_user, PROFILE_READERS)
        self._validate_page(page, page_size)
        self._get_beneficiary_or_404(beneficiary_id)

        return self.repository.list_assistance(
            beneficiary_id=beneficiary_id,
            project_id=project_id,
            resource_id=resource_id,
            page=page,
            page_size=page_size,
        )
