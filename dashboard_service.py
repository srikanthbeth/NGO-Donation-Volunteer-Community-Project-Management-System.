from sqlalchemy.orm import Session

from repositories.dashboard_repository import get_dashboard_data


def get_dashboard_summary(db: Session) -> dict:
    """Build the dashboard summary from current database records."""
    return get_dashboard_data(db)