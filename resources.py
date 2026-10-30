
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from routes.dependencies import get_current_user
from db.session import get_db
from models.user import User
from schemas.resource import (
    LowStockResource,
    ResourceAllocationCreate,
    ResourceAllocationListResponse,
    ResourceAllocationResponse,
    ResourceCreate,
    ResourceDistributionCreate,
    ResourceListResponse,
    ResourceResponse,
    ResourceStockMovementCreate,
    ResourceTransactionListResponse,
    ResourceTransactionResponse,
    ResourceUpdate,
)
from services.resource_service import ResourceService


router = APIRouter(prefix="/api/v1/resources", tags=["Resources"])


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).create_resource(payload, current_user)


@router.get("", response_model=ResourceListResponse)
def list_resources(
    category: str | None = Query(
        None,
        pattern="^(FOOD|CLOTHING|EDUCATIONAL_MATERIALS|MEDICAL_SUPPLIES|EMERGENCY_KITS|OTHER)$",
    ),
    resource_status: str | None = Query(
        None,
        alias="status",
        pattern="^(ACTIVE|INACTIVE)$",
    ),
    low_stock_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ResourceService(db).list_resources(
        current_user,
        category=category,
        resource_status=resource_status,
        low_stock_only=low_stock_only,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/low-stock", response_model=list[LowStockResource])
def low_stock_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, _ = ResourceService(db).list_resources(
        current_user,
        low_stock_only=True,
        page=1,
        page_size=100,
    )
    return items


@router.get("/{resource_id}", response_model=ResourceResponse)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).get_resource(resource_id, current_user)


@router.patch("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).update_resource(
        resource_id,
        payload,
        current_user,
    )


@router.post(
    "/{resource_id}/stock-movements",
    status_code=status.HTTP_201_CREATED,
)
def move_stock(
    resource_id: int,
    payload: ResourceStockMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = ResourceService(db).move_stock(
        resource_id,
        payload,
        current_user,
    )
    return result


@router.get(
    "/{resource_id}/transactions",
    response_model=ResourceTransactionListResponse,
)
def list_resource_transactions(
    resource_id: int,
    transaction_type: str | None = Query(
        None,
        pattern="^(STOCK_IN|STOCK_OUT|ALLOCATION|DISTRIBUTION)$",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ResourceService(db).list_transactions(
        current_user,
        resource_id=resource_id,
        transaction_type=transaction_type,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/allocations",
    response_model=ResourceAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def allocate_resource(
    payload: ResourceAllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).allocate_resource(payload, current_user)


@router.get(
    "/allocations",
    response_model=ResourceAllocationListResponse,
)
def list_allocations(
    resource_id: int | None = Query(None, gt=0),
    project_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = ResourceService(db).list_allocations(
        current_user,
        resource_id=resource_id,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/allocations/{allocation_id}",
    response_model=ResourceAllocationResponse,
)
def get_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).get_allocation(
        allocation_id,
        current_user,
    )


@router.post(
    "/allocations/{allocation_id}/distributions",
    response_model=ResourceAllocationResponse,
)
def distribute_resource(
    allocation_id: int,
    payload: ResourceDistributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResourceService(db).distribute_resource(
        allocation_id,
        payload,
        current_user,
    )
