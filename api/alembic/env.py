import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.core.AppConfig import AppConfig
from app.core.PostgresManager import Base
from app.modules.agent.dto.AgentCacheTableDto import AgentCacheTableDto
from app.modules.auth.dto.AccountRecoveryRequestTableDto import AccountRecoveryRequestTableDto
from app.modules.auth.dto.AuthAuditLogTableDto import AuthAuditLogTableDto
from app.modules.auth.dto.AuthTokenTableDto import AuthTokenTableDto
from app.modules.auth.dto.EmailOutboxTableDto import EmailOutboxTableDto
from app.modules.auth.dto.LoginAttemptTableDto import LoginAttemptTableDto
from app.modules.auth.dto.OrganizationInvitationTableDto import OrganizationInvitationTableDto
from app.modules.auth.dto.OrganizationTableDto import OrganizationTableDto
from app.modules.auth.dto.PasswordHistoryTableDto import PasswordHistoryTableDto
from app.modules.auth.dto.UserEmailTableDto import UserEmailTableDto
from app.modules.auth.dto.UserMfaSettingTableDto import UserMfaSettingTableDto
from app.modules.auth.dto.UserRecoveryCodeTableDto import UserRecoveryCodeTableDto
from app.modules.auth.dto.UserSessionTableDto import UserSessionTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.integrations.dto.GithubIntegrationTableDto import GithubIntegrationTableDto
from app.modules.integrations.dto.GithubWebhookDeliveryTableDto import GithubWebhookDeliveryTableDto
from app.modules.integrations.dto.JiraIntegrationTableDto import JiraIntegrationTableDto
from app.modules.metrics.dto.AreaSnapshotTableDto import AreaSnapshotTableDto
from app.modules.projects.dto.AreaTableDto import AreaTableDto
from app.modules.projects.dto.ProjectTableDto import ProjectTableDto

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", AppConfig.POSTGRES_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Runs migrations in offline SQL generation mode."""
    context.configure(
        url=AppConfig.POSTGRES_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Runs migrations against an established synchronous connection.

    Args:
        connection: SQLAlchemy connection provided by the async engine.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Creates an async engine and executes migrations online."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Runs migrations online using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
