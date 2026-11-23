from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.PostgresManager import PostgresManager
from app.core.dependencies.AuthDependencies import getAuditService
from app.core.dependencies.MetricDependencies import getMetricService
from app.core.dependencies.ProjectDependencies import getProjectRepository
from app.modules.auth.service.AuditService import AuditService
from app.modules.integrations.IntegrationRepository import IntegrationRepository
from app.modules.integrations.JiraIntegrationRepository import JiraIntegrationRepository
from app.modules.integrations.client.GithubApiClient import GithubApiClient
from app.modules.integrations.service.GithubSyncService import GithubSyncService
from app.modules.integrations.service.JiraSyncService import JiraSyncService
from app.modules.integrations.utils.SecretEncryptionHelper import SecretEncryptionHelper
from app.modules.integrations.utils.SecurityAuditLogger import SecurityAuditLogger
from app.modules.metrics.service.MetricService import MetricService
from app.modules.projects.ProjectRepository import ProjectRepository


def getIntegrationRepository(
    db_session: AsyncSession = Depends(PostgresManager.getSession),
) -> IntegrationRepository:
    """Provides an IntegrationRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        IntegrationRepository: GitHub integration persistence repository.
    """
    return IntegrationRepository(db_session=db_session)


def getJiraIntegrationRepository(
    db_session: AsyncSession = Depends(PostgresManager.getSession),
) -> JiraIntegrationRepository:
    """Provides a tenant-scoped Jira integration repository."""
    return JiraIntegrationRepository(db_session=db_session)


def getSecretEncryptionHelper() -> SecretEncryptionHelper:
    """Provides a credential encryption helper configured from application settings.

    Returns:
        SecretEncryptionHelper: Fernet credential encryption helper.
    """
    return SecretEncryptionHelper()


def getGithubApiClient() -> GithubApiClient:
    """Provides a GitHub REST client configured from application settings.

    Returns:
        GithubApiClient: GitHub API client with bounded retries and timeouts.
    """
    return GithubApiClient()


def getSecurityAuditLogger(
    audit_service: AuditService = Depends(getAuditService),
) -> SecurityAuditLogger:
    """Provides a GitHub security audit logger with an independent audit transaction.

    Args:
        audit_service (AuditService): Injected security audit service.

    Returns:
        SecurityAuditLogger: Redacting GitHub security audit logger.
    """
    return SecurityAuditLogger(
        audit_service=audit_service,
        independent_session_factory=PostgresManager.session_factory,
    )


def getGithubSyncService(
    integration_repository: IntegrationRepository = Depends(getIntegrationRepository),
    project_repository: ProjectRepository = Depends(getProjectRepository),
    github_api_client: GithubApiClient = Depends(getGithubApiClient),
    secret_encryption_helper: SecretEncryptionHelper = Depends(getSecretEncryptionHelper),
    metric_service: MetricService = Depends(getMetricService),
    security_audit_logger: SecurityAuditLogger = Depends(getSecurityAuditLogger),
) -> GithubSyncService:
    """Provides a GithubSyncService with all integration collaborators.

    Args:
        integration_repository (IntegrationRepository): Injected integration repository.
        project_repository (ProjectRepository): Injected project repository.
        github_api_client (GithubApiClient): Injected GitHub API client.
        secret_encryption_helper (SecretEncryptionHelper): Injected credential encryption helper.
        metric_service (MetricService): Injected deterministic metric service.
        security_audit_logger (SecurityAuditLogger): Injected security audit logger.

    Returns:
        GithubSyncService: GitHub synchronization and webhook service.
    """
    return GithubSyncService(
        integration_repository=integration_repository,
        project_repository=project_repository,
        github_api_client=github_api_client,
        secret_encryption_helper=secret_encryption_helper,
        metric_service=metric_service,
        security_audit_logger=security_audit_logger,
    )


def getJiraSyncService(
    integration_repository: JiraIntegrationRepository = Depends(
        getJiraIntegrationRepository
    ),
    project_repository: ProjectRepository = Depends(getProjectRepository),
    secret_encryption_helper: SecretEncryptionHelper = Depends(
        getSecretEncryptionHelper
    ),
) -> JiraSyncService:
    """Provides Jira connection and project synchronization services."""
    return JiraSyncService(
        integration_repository=integration_repository,
        project_repository=project_repository,
        secret_encryption_helper=secret_encryption_helper,
    )
