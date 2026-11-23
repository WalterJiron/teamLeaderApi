import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.modules.auth.AuditRepository import AuditRepository
from app.modules.auth.service.AuditService import AuditService

logger = logging.getLogger(__name__)


class SecurityAuditLogger:

    def __init__(
        self,
        audit_service: AuditService,
        independent_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        """Initializes the security audit logger with the authentication audit service.

        Args:
            audit_service (AuditService): Tamper-evident audit persistence service.
            independent_session_factory (async_sessionmaker[AsyncSession] | None, optional): Factory used to
                persist audits outside the business transaction. Defaults to None.
        """
        self.audit_service = audit_service
        self.independent_session_factory = independent_session_factory

    async def _record(
        self,
        event_type: str,
        organization_id: int | None,
        actor_user_id: int | None,
        severity: str,
        metadata: dict[str, Any],
    ) -> None:
        """Persists a redacted GitHub integration audit event without masking failures.

        Args:
            event_type (str): Stable audit event type.
            organization_id (int | None): Tenant identifier when known.
            actor_user_id (int | None): Authenticated actor identifier when known.
            severity (str): Audit severity level.
            metadata (dict[str, Any]): Non-secret event context.
        """
        logger.info(
            "github_security_audit",
            extra={
                "event_type": event_type,
                "organization_id": organization_id,
                "actor_user_id": actor_user_id,
                "severity": severity,
            },
        )
        try:
            if self.independent_session_factory is None:
                await self.audit_service.record(
                    event_type=event_type,
                    actor_user_id=actor_user_id,
                    organization_id=organization_id,
                    severity=severity,
                    metadata=metadata,
                )
                return
            async with self.independent_session_factory() as session:
                independent_audit_service = AuditService(
                    audit_repository=AuditRepository(db_session=session)
                )
                await independent_audit_service.record(
                    event_type=event_type,
                    actor_user_id=actor_user_id,
                    organization_id=organization_id,
                    severity=severity,
                    metadata=metadata,
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist GitHub security audit event %s.", event_type)

    async def logIntegrationRegistered(
        self,
        organization_id: int,
        actor_user_id: int | None,
        integration_id: int,
        repository_full_name: str,
    ) -> None:
        """Audits a successful GitHub repository integration registration.

        Args:
            organization_id (int): Tenant identifier.
            actor_user_id (int | None): Authenticated actor identifier.
            integration_id (int): Created integration identifier.
            repository_full_name (str): GitHub repository full name.
        """
        await self._record(
            event_type="GITHUB_INTEGRATION_REGISTERED",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            severity="INFO",
            metadata={
                "integration_id": integration_id,
                "repository": repository_full_name,
            },
        )

    async def logIntegrationAccessDenied(
        self,
        organization_id: int | None,
        actor_user_id: int | None,
        integration_id: int,
        action: str,
    ) -> None:
        """Audits a cross-tenant or unauthorized integration access attempt.

        Args:
            organization_id (int | None): Caller tenant identifier when known.
            actor_user_id (int | None): Authenticated actor identifier when known.
            integration_id (int): Targeted integration identifier.
            action (str): Attempted operation name.
        """
        await self._record(
            event_type="GITHUB_INTEGRATION_ACCESS_DENIED",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            severity="WARNING",
            metadata={"integration_id": integration_id, "action": action},
        )

    async def logWebhookSignatureFailure(
        self,
        organization_id: int | None,
        integration_id: int,
        delivery_id: str,
        event_type: str,
    ) -> None:
        """Audits a rejected GitHub webhook signature.

        Args:
            organization_id (int | None): Tenant identifier when known.
            integration_id (int): Targeted integration identifier.
            delivery_id (str): GitHub delivery identifier.
            event_type (str): GitHub event type.
        """
        await self._record(
            event_type="GITHUB_WEBHOOK_SIGNATURE_FAILURE",
            organization_id=organization_id,
            actor_user_id=None,
            severity="WARNING",
            metadata={
                "integration_id": integration_id,
                "delivery_id": delivery_id,
                "event_type": event_type,
            },
        )

    async def logWebhookDuplicate(
        self,
        organization_id: int,
        integration_id: int,
        delivery_id: str,
        event_type: str,
    ) -> None:
        """Audits an idempotently ignored duplicate GitHub webhook delivery.

        Args:
            organization_id (int): Tenant identifier.
            integration_id (int): Targeted integration identifier.
            delivery_id (str): GitHub delivery identifier.
            event_type (str): GitHub event type.
        """
        await self._record(
            event_type="GITHUB_WEBHOOK_DUPLICATE_IGNORED",
            organization_id=organization_id,
            actor_user_id=None,
            severity="INFO",
            metadata={
                "integration_id": integration_id,
                "delivery_id": delivery_id,
                "event_type": event_type,
            },
        )

    async def logWebhookIgnored(
        self,
        organization_id: int,
        integration_id: int,
        delivery_id: str,
        event_type: str,
        reason: str,
    ) -> None:
        """Audits a valid GitHub webhook that does not require metric updates.

        Args:
            organization_id (int): Tenant identifier.
            integration_id (int): Targeted integration identifier.
            delivery_id (str): GitHub delivery identifier.
            event_type (str): GitHub event type.
            reason (str): Stable reason code for ignoring the event.
        """
        await self._record(
            event_type="GITHUB_WEBHOOK_IGNORED",
            organization_id=organization_id,
            actor_user_id=None,
            severity="INFO",
            metadata={
                "integration_id": integration_id,
                "delivery_id": delivery_id,
                "event_type": event_type,
                "reason": reason,
            },
        )

    async def logWebhookProcessed(
        self,
        organization_id: int,
        integration_id: int,
        delivery_id: str,
        event_type: str,
        area_count: int,
    ) -> None:
        """Audits a GitHub webhook that produced deterministic area snapshots.

        Args:
            organization_id (int): Tenant identifier.
            integration_id (int): Targeted integration identifier.
            delivery_id (str): GitHub delivery identifier.
            event_type (str): GitHub event type.
            area_count (int): Number of area snapshots produced.
        """
        await self._record(
            event_type="GITHUB_WEBHOOK_PROCESSED",
            organization_id=organization_id,
            actor_user_id=None,
            severity="INFO",
            metadata={
                "integration_id": integration_id,
                "delivery_id": delivery_id,
                "event_type": event_type,
                "area_count": area_count,
            },
        )

    async def logSyncCompleted(
        self,
        organization_id: int,
        integration_id: int,
        actor_user_id: int | None,
        issue_count: int,
        area_count: int,
    ) -> None:
        """Audits a completed deterministic repository synchronization.

        Args:
            organization_id (int): Tenant identifier.
            integration_id (int): Synchronized integration identifier.
            actor_user_id (int | None): Authenticated actor identifier when triggered manually.
            issue_count (int): Number of normalized GitHub issues processed.
            area_count (int): Number of area snapshots produced.
        """
        await self._record(
            event_type="GITHUB_SYNC_COMPLETED",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            severity="INFO",
            metadata={
                "integration_id": integration_id,
                "issue_count": issue_count,
                "area_count": area_count,
            },
        )

    async def logSyncFailed(
        self,
        organization_id: int,
        integration_id: int,
        actor_user_id: int | None,
        reason: str,
    ) -> None:
        """Audits a failed repository synchronization.

        Args:
            organization_id (int): Tenant identifier.
            integration_id (int): Integration identifier.
            actor_user_id (int | None): Authenticated actor identifier when triggered manually.
            reason (str): Sanitized failure reason code.
        """
        await self._record(
            event_type="GITHUB_SYNC_FAILED",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            severity="ERROR",
            metadata={"integration_id": integration_id, "reason": reason},
        )

    async def logCredentialDecryptionFailure(
        self,
        organization_id: int | None,
        integration_id: int,
    ) -> None:
        """Audits a credential decryption failure without exposing encrypted material.

        Args:
            organization_id (int | None): Tenant identifier when known.
            integration_id (int): Integration identifier.
        """
        await self._record(
            event_type="GITHUB_CREDENTIAL_DECRYPTION_FAILURE",
            organization_id=organization_id,
            actor_user_id=None,
            severity="ERROR",
            metadata={"integration_id": integration_id},
        )
