
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import settings
from db.base import Base

# Import every model module here so Alembic can discover its tables.
from models.user import PasswordResetToken, RefreshToken, User  # noqa: F401
from models.donor import Donor
from models.campaign import Campaign
from models.donation import Donation
from models.volunteer import Volunteer
from models.volunteer_assignment import VolunteerAssignment
from models.project import Project
from models.project_milestone import ProjectMilestone  # noqa: F401
from models.project_task import ProjectTask  # noqa: F401
from models.project_approval import ProjectApproval  # noqa: F401
from models.expense import Expense  # noqa: F401
from models.budget import Budget  # noqa: F401
from models.resource import Resource  # noqa: F401
from models.resource_transaction import ResourceTransaction  # noqa: F401
from models.resource_allocation import ResourceAllocation  # noqa: F401
from models.beneficiary import Beneficiary  # noqa: F401
from models.beneficiary_project import BeneficiaryProject  # noqa: F401
from models.beneficiary_assistance import BeneficiaryAssistance  # noqa: F401
from models.impact_update import ImpactUpdate  # noqa: F401
from models.receipt import DonationReceipt
from models.audit_log import AuditLog  # noqa: F401



config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the same PostgreSQL URL as the application.
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate migrations without opening a database connection."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
