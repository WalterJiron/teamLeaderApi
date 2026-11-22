import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.AppConfig import AppConfig
from app.core.RequestContext import getClientIp, getRequestId, getUserAgent
from app.modules.auth.AuditRepository import AuditRepository
from app.modules.auth.dto.AuthAuditLogTableDto import AuthAuditLogTableDto

logger = logging.getLogger(__name__)


class AuditService:

    def __init__(self, audit_repository: AuditRepository) -> None:
        """Initializes the audit service with its repository.

        Args:
            audit_repository (AuditRepository): Audit log persistence repository.
        """
        self.audit_repository = audit_repository

    @staticmethod
    def _sanitize(value: Any) -> Any:
        """Removes secrets and normalizes values before audit persistence.

        Args:
            value (Any): Arbitrary metadata value.

        Returns:
            Any: Sanitized JSON-compatible value.
        """
        blocked = {
            "password",
            "current_password",
            "new_password",
            "token",
            "access_token",
            "refresh_token",
            "mfa_token",
            "recovery_code",
            "secret",
            "authorization",
            "totp_secret",
            "invitation_token",
        }
        if isinstance(value, dict):
            return {
                str(key): AuditService._sanitize(item)
                for key, item in value.items()
                if str(key).lower() not in blocked
            }
        if isinstance(value, (list, tuple, set)):
            return [AuditService._sanitize(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    async def record(
        self,
        event_type: str,
        actor_user_id: int | None = None,
        target_user_id: int | None = None,
        organization_id: int | None = None,
        severity: str = "INFO",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Appends a tamper-evident authentication audit event.

        Args:
            event_type (str): Stable event type code.
            actor_user_id (int | None, optional): User who performed the action. Defaults to None.
            target_user_id (int | None, optional): User affected by the action. Defaults to None.
            organization_id (int | None, optional): Tenant identifier. Defaults to None.
            severity (str, optional): Event severity. Defaults to "INFO".
            metadata (dict[str, Any] | None, optional): Additional non-secret context. Defaults to None.
        """
        sanitized = self._sanitize(metadata or {})
        now = datetime.now(timezone.utc)
        previous_hash: str | None = None
        entry_hash: str | None = None
        if AppConfig.AUDIT_HASH_CHAIN_ENABLED:
            previous_hash = await self.audit_repository.getLastHash()
            canonical = json.dumps(
                {
                    "event_type": event_type,
                    "actor_user_id": actor_user_id,
                    "target_user_id": target_user_id,
                    "organization_id": organization_id,
                    "severity": severity,
                    "metadata": sanitized,
                    "created_at": now.isoformat(),
                },
                sort_keys=True,
                default=str,
            )
            entry_hash = hashlib.sha256(
                f"{previous_hash or ''}|{canonical}".encode("utf-8")
            ).hexdigest()

        log = AuthAuditLogTableDto(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            event_type=event_type,
            severity=severity,
            ip=getClientIp(),
            user_agent=getUserAgent(),
            request_id=getRequestId(),
            metadata_json=sanitized,
            created_at=now,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        await self.audit_repository.addLog(log)
