
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatus,
    CampaignUpdate,
)
from services.campaign_service import (
    create_campaign_record,
    get_campaign_record,
    list_campaign_records,
    update_campaign_record,
)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_campaign_record(db, payload, current_user)


@router.get("", response_model=CampaignListResponse)
def get_campaigns(
    search: str | None = Query(default=None, max_length=200),
    status_filter: CampaignStatus | None = Query(
        default=None,
        alias="status",
    ),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    sort_by: Literal[
        "id",
        "title",
        "goal_amount",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
        "status",
    ] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_campaign_records(
        db,
        search=search,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_campaign_record(db, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_campaign_record(
        db,
        campaign_id,
        payload,
        current_user,
    )
