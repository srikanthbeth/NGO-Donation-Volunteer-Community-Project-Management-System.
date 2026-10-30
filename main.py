
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from core.config import settings
from db.base import Base
from db.session import engine

# Import models so SQLAlchemy registers their tables in Base.metadata.
from models.user import PasswordResetToken, RefreshToken, User  # noqa: F401
from models.donation import Donation




from routes.auth import router as auth_router
from routes.users import router as users_router
from models.donor import Donor
from routes.donors import router as donors_router
from routes.campaigns import router as campaigns_router
from routes.donations import router as donations_router
from routes.volunteers import router as volunteers_router
from routes.volunteer_assignments import router as volunteer_assignments_router
from routes.projects import router as projects_router
from routes.project_milestones import router as project_milestones_router
from routes.project_tasks import router as project_tasks_router
from routes.project_approvals import router as project_approvals_router
from routes.expenses import router as expenses_router
from routes.budgets import router as budgets_router
from routes.resources import router as resources_router
from routes.beneficiaries import router as beneficiaries_router
from routes.impact import router as impact_router
from routes.receipts import router as receipts_router
from routes.dashboard import router as dashboard_router
from routes.reports import router as reports_router
from routes.audit_logs import router as audit_logs_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""
    # Database schema creation is handled by Alembic migrations.
    # Do not call Base.metadata.create_all() in production.
    yield
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend API for NGO donations, volunteers, fundraising campaigns, "
        "community projects, resources, expenses, and impact reporting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)



app.include_router(
    auth_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    users_router,
    prefix=settings.API_V1_PREFIX,
)



app.include_router(
    donors_router,
    prefix=settings.API_V1_PREFIX,
)


app.include_router(
    campaigns_router,
    prefix=settings.API_V1_PREFIX,
)


app.include_router(
    donations_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(volunteers_router)

app.include_router(volunteer_assignments_router)

app.include_router(projects_router)

app.include_router(project_milestones_router)
app.include_router(project_tasks_router)

app.include_router(project_approvals_router)

app.include_router(expenses_router)


app.include_router(budgets_router)



app.include_router(resources_router)


app.include_router(beneficiaries_router)




app.include_router(impact_router)

app.include_router(receipts_router)

app.include_router(dashboard_router)


app.include_router(reports_router)

app.include_router(audit_logs_router, prefix="/api/v1")




@app.get("/", tags=["Health"])
def health_check():
    return {
        "message": settings.APP_NAME,
        "status": "running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/database", tags=["Health"])
def database_health_check():
    """Check whether PostgreSQL accepts a simple query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"database": "connected"}
