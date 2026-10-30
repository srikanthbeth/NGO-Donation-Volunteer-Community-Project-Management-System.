
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.resource import Resource
from models.resource_transaction import ResourceTransaction
from models.resource_allocation import ResourceAllocation
from repositories.resource_repository import ResourceRepository


MANAGE_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}
STOCK_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}
DISTRIBUTION_ROLES = {
    "SUPER_ADMIN",
    "NGO_MANAGER",
    "VOLUNTEER_COORDINATOR",
}


class ResourceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ResourceRepository(db)

    @staticmethod
    def _require_role(user, allowed_roles: set[str]):
        if getattr(user, "role", None) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

    def _lock_resource(self, resource_id: int) -> Resource:
        resource = self.db.scalar(
            select(Resource)
            .where(Resource.id == resource_id)
            .with_for_update()
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found.",
            )

        return resource

    def _get_active_resource(self, resource_id: int) -> Resource:
        resource = self._lock_resource(resource_id)

        if resource.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This resource is inactive.",
            )

        return resource

    def create_resource(self, payload, current_user):
        self._require_role(current_user, MANAGE_ROLES)

        resource = Resource(
            **payload.model_dump(),
            quantity_available=0,
            created_by=current_user.id,
            status="ACTIVE",
        )

        try:
            self.db.add(resource)
            self.db.flush()
            self.db.commit()
            self.db.refresh(resource)
            return resource
        except Exception:
            self.db.rollback()
            raise

    def get_resource(self, resource_id: int, current_user):
        if not getattr(current_user, "role", None):
            raise HTTPException(status_code=403, detail="Access denied.")

        resource = self.repository.get_resource(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=404,
                detail="Resource not found.",
            )

        return resource

    def list_resources(
        self,
        current_user,
        *,
        category=None,
        resource_status=None,
        low_stock_only=False,
        page=1,
        page_size=10,
    ):
        if not getattr(current_user, "role", None):
            raise HTTPException(status_code=403, detail="Access denied.")

        return self.repository.list_resources(
            category=category,
            resource_status=resource_status,
            low_stock_only=low_stock_only,
            page=page,
            page_size=page_size,
        )

    def update_resource(self, resource_id: int, payload, current_user):
        self._require_role(current_user, MANAGE_ROLES)

        resource = self._lock_resource(resource_id)
        changes = payload.model_dump(exclude_unset=True)

        if "quantity_available" in changes:
            raise HTTPException(
                status_code=422,
                detail="Use stock movement endpoints to change inventory.",
            )

        if not changes:
            raise HTTPException(
                status_code=422,
                detail="At least one field must be provided.",
            )

        try:
            for key, value in changes.items():
                setattr(resource, key, value)

            self.db.commit()
            self.db.refresh(resource)
            return resource
        except Exception:
            self.db.rollback()
            raise

    def move_stock(self, resource_id: int, payload, current_user):
        self._require_role(current_user, STOCK_ROLES)

        try:
            resource = self._get_active_resource(resource_id)
            quantity = payload.quantity
            movement_type = payload.transaction_type

            if movement_type == "STOCK_IN":
                resource.quantity_available += quantity

            elif movement_type == "STOCK_OUT":
                if resource.quantity_available < quantity:
                    raise HTTPException(
                        status_code=409,
                        detail="Insufficient available stock.",
                    )

                resource.quantity_available -= quantity

            else:
                raise HTTPException(
                    status_code=422,
                    detail="Unsupported stock movement type.",
                )

            transaction = ResourceTransaction(
                resource_id=resource.id,
                transaction_type=movement_type,
                quantity=quantity,
                performed_by=current_user.id,
                reference=payload.reference,
                notes=payload.notes,
            )

            self.db.add(transaction)
            self.db.flush()
            self.db.commit()
            self.db.refresh(resource)
            self.db.refresh(transaction)

            return {
                "resource": resource,
                "transaction": transaction,
            }
        except Exception:
            self.db.rollback()
            raise

    def allocate_resource(self, payload, current_user):
        self._require_role(current_user, MANAGE_ROLES)

        try:
            resource = self._get_active_resource(payload.resource_id)

            project = self.repository.get_project(payload.project_id)
            if project is None:
                raise HTTPException(
                    status_code=404,
                    detail="Project not found.",
                )

            if resource.quantity_available < payload.allocated_quantity:
                raise HTTPException(
                    status_code=409,
                    detail="Insufficient stock for this allocation.",
                )

            resource.quantity_available -= payload.allocated_quantity

            allocation = ResourceAllocation(
                resource_id=resource.id,
                project_id=project.id,
                allocated_quantity=payload.allocated_quantity,
                distributed_quantity=0,
                status="ALLOCATED",
                allocated_by=current_user.id,
                notes=payload.notes,
            )

            transaction = ResourceTransaction(
                resource_id=resource.id,
                transaction_type="ALLOCATION",
                quantity=payload.allocated_quantity,
                project_id=project.id,
                performed_by=current_user.id,
                notes=payload.notes,
            )

            self.db.add_all([allocation, transaction])
            self.db.flush()
            self.db.commit()
            self.db.refresh(allocation)

            return allocation
        except Exception:
            self.db.rollback()
            raise

    def distribute_resource(
        self,
        allocation_id: int,
        payload,
        current_user,
    ):
        self._require_role(current_user, DISTRIBUTION_ROLES)

        try:
            allocation = self.db.scalar(
                select(ResourceAllocation)
                .where(ResourceAllocation.id == allocation_id)
                .with_for_update()
            )

            if allocation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Resource allocation not found.",
                )

            if allocation.status in {"COMPLETED", "CANCELLED"}:
                raise HTTPException(
                    status_code=409,
                    detail="This allocation cannot receive more distributions.",
                )

            remaining = (
                allocation.allocated_quantity
                - allocation.distributed_quantity
            )

            if payload.quantity > remaining:
                raise HTTPException(
                    status_code=409,
                    detail="Distribution exceeds the remaining allocation.",
                )

            allocation.distributed_quantity += payload.quantity

            if allocation.distributed_quantity == allocation.allocated_quantity:
                allocation.status = "COMPLETED"
            else:
                allocation.status = "PARTIALLY_DISTRIBUTED"

            transaction = ResourceTransaction(
                resource_id=allocation.resource_id,
                transaction_type="DISTRIBUTION",
                quantity=payload.quantity,
                project_id=allocation.project_id,
                performed_by=current_user.id,
                reference=payload.reference,
                notes=payload.notes,
            )

            self.db.add(transaction)
            self.db.flush()
            self.db.commit()
            self.db.refresh(allocation)

            return allocation
        except Exception:
            self.db.rollback()
            raise

    def get_allocation(self, allocation_id: int, current_user):
        if not getattr(current_user, "role", None):
            raise HTTPException(status_code=403, detail="Access denied.")

        allocation = self.repository.get_allocation(allocation_id)

        if allocation is None:
            raise HTTPException(
                status_code=404,
                detail="Resource allocation not found.",
            )

        return allocation

    def list_allocations(
        self,
        current_user,
        *,
        resource_id=None,
        project_id=None,
        page=1,
        page_size=10,
    ):
        if not getattr(current_user, "role", None):
            raise HTTPException(status_code=403, detail="Access denied.")

        return self.repository.list_allocations(
            resource_id=resource_id,
            project_id=project_id,
            page=page,
            page_size=page_size,
        )

    def list_transactions(
        self,
        current_user,
        *,
        resource_id=None,
        project_id=None,
        transaction_type=None,
        page=1,
        page_size=10,
    ):
        if not getattr(current_user, "role", None):
            raise HTTPException(status_code=403, detail="Access denied.")

        return self.repository.list_transactions(
            resource_id=resource_id,
            project_id=project_id,
            transaction_type=transaction_type,
            page=page,
            page_size=page_size,
        )
