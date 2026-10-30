
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.campaign import Campaign
from repositories.campaign_repository import (
    create_campaign,
    get_campaign_by_id,
    list_campaigns,
    update_campaign,
)
from schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
)

MANAGER_ROLES = {"SUPER_ADMIN", "NGO_MANAGER"}


def role_value(user) -> str:
    role = user.role
    return str(getattr(role, "value", role)).upper()


def require_campaign_manager(user) -> None:
    if role_value(user) not in MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage campaigns",
        )


def get_campaign_or_404(db: Session, campaign_id: int) -> Campaign:
    campaign = get_campaign_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


def create_campaign_record(
    db: Session,
    data: CampaignCreate,
    current_user,
) -> CampaignResponse:
    require_campaign_manager(current_user)

    values = data.model_dump()
    values["raised_amount"] = 0
    values["created_by"] = current_user.id

    campaign = create_campaign(db, values)
    return CampaignResponse.model_validate(campaign)


def get_campaign_record(
    db: Session,
    campaign_id: int,
) -> CampaignResponse:
    campaign = get_campaign_or_404(db, campaign_id)
    return CampaignResponse.model_validate(campaign)


def update_campaign_record(
    db: Session,
    campaign_id: int,
    data: CampaignUpdate,
    current_user,
) -> CampaignResponse:
    require_campaign_manager(current_user)
    campaign = get_campaign_or_404(db, campaign_id)

    changes = data.model_dump(exclude_unset=True)

    for required_field in ("title", "description", "goal_amount",
                           "currency", "start_date", "end_date", "status"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required_field} cannot be null",
            )

    new_goal = changes.get("goal_amount", campaign.goal_amount)
    if new_goal < campaign.raised_amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="goal_amount cannot be less than raised_amount",
        )

    new_start = changes.get("start_date", campaign.start_date)
    new_end = changes.get("end_date", campaign.end_date)
    if new_end <= new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be after start_date",
        )

    updated = update_campaign(db, campaign, changes)
    return CampaignResponse.model_validate(updated)


def list_campaign_records(
    db: Session,
    *,
    search: str | None,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> CampaignListResponse:
    items, total = list_campaigns(
        db,
        search=search,
        status=status_filter,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return CampaignListResponse(
        items=[CampaignResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
