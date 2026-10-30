
import io

from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db.session import get_db
from models.user import User
from routes.dependencies import get_current_user
from schemas.report import ReportFilters, ReportPage
from services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def create_filters(
    start_date: date | None,
    end_date: date | None,
    campaign_id: int | None,
    project_id: int | None,
    status: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> ReportFilters:
    return ReportFilters(
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        project_id=project_id,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def report_endpoint(report_type: str):
    def endpoint(
        start_date: date | None = Query(None),
        end_date: date | None = Query(None),
        campaign_id: int | None = Query(None, ge=1),
        project_id: int | None = Query(None, ge=1),
        status: str | None = Query(None, min_length=1, max_length=30),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=200),
        sort_by: str = Query("created_at"),
        sort_order: str = Query("desc", pattern="^(asc|desc)$"),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> ReportPage:
        filters = create_filters(
            start_date,
            end_date,
            campaign_id,
            project_id,
            status,
            page,
            page_size,
            sort_by,
            sort_order,
        )

        return ReportService(db).get_report(
            report_type=report_type,
            filters=filters,
            user=user,
        )

    endpoint.__name__ = f"{report_type}_report"
    return endpoint


router.add_api_route(
    "/donations",
    report_endpoint("donations"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/campaigns",
    report_endpoint("campaigns"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/volunteers",
    report_endpoint("volunteers"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/projects",
    report_endpoint("projects"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/expenses",
    report_endpoint("expenses"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/resources",
    report_endpoint("resources"),
    methods=["GET"],
    response_model=ReportPage,
)
router.add_api_route(
    "/beneficiaries",
    report_endpoint("beneficiaries"),
    methods=["GET"],
    response_model=ReportPage,
)


@router.get("/{report_type}/export")
def export_report_csv(
    report_type: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    campaign_id: int | None = Query(None, ge=1),
    project_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, min_length=1, max_length=30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = ReportFilters(
        start_date=start_date,
        end_date=end_date,
        campaign_id=campaign_id,
        project_id=project_id,
        status=status,
    )

    content, filename, row_count = ReportService(db).export_csv(
        report_type=report_type,
        filters=filters,
        user=user,
    )

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Exported-Rows": str(row_count),
        },
    )
