
import csv
import io
import math
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from repositories.report_repository import ReportRepository
from schemas.report import ReportFilters, ReportPage
from models.user import User, UserRole


MANAGEMENT_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.NGO_MANAGER,
)

FINANCE_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.NGO_MANAGER,
    UserRole.FINANCE_OFFICER,
)

VOLUNTEER_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.NGO_MANAGER,
    UserRole.VOLUNTEER_COORDINATOR,
)


class ReportService:
    """Business logic for filtered, paginated NGO reports."""

    REPORT_METHODS = {
        "donations": "donation_rows",
        "campaigns": "campaign_rows",
        "volunteers": "volunteer_rows",
        "projects": "project_rows",
        "expenses": "expense_rows",
        "resources": "resource_rows",
        "beneficiaries": "beneficiary_impact_rows",
    }

    def __init__(self, db: Session):
        self.repository = ReportRepository(db)

    @staticmethod
    def authorize(report_type: str, user: User) -> None:
        if report_type not in ReportService.REPORT_METHODS:
            raise HTTPException(
                status_code=404,
                detail="Unknown report type.",
            )

        if report_type in ("donations", "expenses"):
            allowed = FINANCE_ROLES
        elif report_type == "volunteers":
            allowed = VOLUNTEER_ROLES
        else:
            allowed = MANAGEMENT_ROLES

        if user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this report.",
            )

    def get_report(
        self,
        report_type: str,
        filters: ReportFilters,
        user: User,
    ) -> ReportPage:
        self.authorize(report_type, user)

        method_name = self.REPORT_METHODS[report_type]
        method = getattr(self.repository, method_name)

        rows = method(
            start_date=filters.start_date,
            end_date=filters.end_date,
            campaign_id=(
                filters.campaign_id
                if report_type in ("donations", "campaigns")
                else None
            ),
            project_id=(
                filters.project_id
                if report_type in (
                    "volunteers",
                    "projects",
                    "expenses",
                    "resources",
                    "beneficiaries",
                )
                else None
            ),
            status=(
                filters.status
                if report_type in (
                    "donations",
                    "campaigns",
                    "volunteers",
                    "projects",
                    "expenses",
                    "resources",
                )
                else None
            ),
        )

        if filters.start_date and filters.end_date:
            if filters.start_date > filters.end_date:
                raise HTTPException(
                    status_code=422,
                    detail="start_date must be on or before end_date.",
                )

        if not rows:
            return ReportPage(
                items=[],
                total=0,
                page=filters.page,
                page_size=filters.page_size,
                total_pages=0,
            )

        if filters.sort_by not in rows[0]:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid sort_by. Available fields: "
                    + ", ".join(sorted(rows[0].keys()))
                ),
            )

        if filters.sort_order not in ("asc", "desc"):
            raise HTTPException(
                status_code=422,
                detail="sort_order must be 'asc' or 'desc'.",
            )

        def key_function(row: dict[str, Any]):
            value = row.get(filters.sort_by)

            if value is None:
                return (1, "")

            if isinstance(value, (int, float, Decimal)):
                return (0, float(value))

            if isinstance(value, date):
                return (0, value.isoformat())

            return (0, str(value).lower())

        rows.sort(
            key=key_function,
            reverse=filters.sort_order == "desc",
        )

        total = len(rows)
        start = (filters.page - 1) * filters.page_size
        items = rows[start:start + filters.page_size]

        return ReportPage(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=math.ceil(total / filters.page_size),
        )

    def export_csv(
        self,
        report_type: str,
        filters: ReportFilters,
        user: User,
    ) -> tuple[str, str, int]:
        """Export all filtered records, not just the current page."""

        self.authorize(report_type, user)

        export_filters = filters.model_copy(
            update={"page": 1, "page_size": 200}
        )

        # Fetch the complete dataset directly from the repository so the
        # CSV is not limited to a single page.
        method_name = self.REPORT_METHODS[report_type]
        method = getattr(self.repository, method_name)

        rows = method(
            start_date=export_filters.start_date,
            end_date=export_filters.end_date,
            campaign_id=(
                export_filters.campaign_id
                if report_type in ("donations", "campaigns")
                else None
            ),
            project_id=(
                export_filters.project_id
                if report_type in (
                    "volunteers",
                    "projects",
                    "expenses",
                    "resources",
                    "beneficiaries",
                )
                else None
            ),
            status=(
                export_filters.status
                if report_type in (
                    "donations",
                    "campaigns",
                    "volunteers",
                    "projects",
                    "expenses",
                    "resources",
                )
                else None
            ),
        )

        output = io.StringIO()

        if rows:
            # CSV requires a stable, consistent column order.
            columns = list(rows[0].keys())
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()

            for row in rows:
                writer.writerow({
                    key: (
                        value.isoformat()
                        if hasattr(value, "isoformat")
                        else str(value) if isinstance(value, Decimal)
                        else value
                    )
                    for key, value in row.items()
                })
        else:
            output.write("no_data\n")

        return output.getvalue(), f"{report_type}_report.csv", len(rows)
