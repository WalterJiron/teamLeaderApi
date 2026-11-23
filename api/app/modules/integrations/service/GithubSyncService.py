import json
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.common.exceptions.AppExceptions import (
    BadRequestException,
    BaseAppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    PayloadTooLargeException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.common.utils.WebhookSignatureHelper import WebhookSignatureHelper
from app.core.AppConfig import AppConfig
from app.modules.integrations.IntegrationRepository import IntegrationRepository
from app.modules.integrations.client.GithubApiClient import GithubApiClient
from app.modules.integrations.dto.GithubIntegrationTableDto import GithubIntegrationTableDto
from app.modules.integrations.schemas.GithubIntegrationSchema import (
    GithubIntegrationCreateSchema,
    GithubIntegrationResponse,
    GithubWebhookPayloadSchema,
)
from app.modules.integrations.utils.SecretEncryptionHelper import SecretEncryptionHelper
from app.modules.integrations.utils.SecurityAuditLogger import SecurityAuditLogger
from app.modules.metrics.schemas.AreaSnapshotSchema import AreaSnapshotResponse
from app.modules.metrics.service.MetricService import MetricService
from app.modules.projects.ProjectRepository import ProjectRepository


class GithubSyncService:

    ACTIONABLE_EVENT_TYPES: frozenset[str] = frozenset({"issues", "pull_request"})
    ACTIONABLE_ACTIONS: frozenset[str] = frozenset(
        {"opened", "closed", "reopened", "labeled", "unlabeled"}
    )
    DELIVERY_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9-]{1,128}$")
    EVENT_TYPE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z_]{1,64}$")

    def __init__(
        self,
        integration_repository: IntegrationRepository,
        project_repository: ProjectRepository,
        github_api_client: GithubApiClient,
        secret_encryption_helper: SecretEncryptionHelper,
        metric_service: MetricService,
        security_audit_logger: SecurityAuditLogger,
    ) -> None:
        """Initializes the GitHub synchronization service with its collaborators.

        Args:
            integration_repository (IntegrationRepository): Integration and delivery persistence repository.
            project_repository (ProjectRepository): Project and area ownership repository.
            github_api_client (GithubApiClient): Direct GitHub REST client.
            secret_encryption_helper (SecretEncryptionHelper): Credential encryption helper.
            metric_service (MetricService): Deterministic area metric service.
            security_audit_logger (SecurityAuditLogger): Security audit logger.
        """
        self.integration_repository = integration_repository
        self.project_repository = project_repository
        self.github_api_client = github_api_client
        self.secret_encryption_helper = secret_encryption_helper
        self.metric_service = metric_service
        self.security_audit_logger = security_audit_logger

    def _buildResponse(self, integration: GithubIntegrationTableDto) -> GithubIntegrationResponse:
        """Builds a sanitized integration response with masked credential previews.

        Args:
            integration (GithubIntegrationTableDto): Persisted integration entity.

        Returns:
            GithubIntegrationResponse: Sanitized integration response.
        """
        masked_access_token = "****"
        masked_webhook_secret = "****"
        try:
            masked_access_token = self.secret_encryption_helper.maskSecret(
                self.secret_encryption_helper.decryptSecret(integration.encrypted_access_token)
            )
        except ValueError:
            masked_access_token = "****"
        try:
            masked_webhook_secret = self.secret_encryption_helper.maskSecret(
                self.secret_encryption_helper.decryptSecret(integration.encrypted_webhook_secret)
            )
        except ValueError:
            masked_webhook_secret = "****"
        return GithubIntegrationResponse(
            integration_id=integration.integration_id,
            organization_id=integration.organization_id,
            project_id=integration.project_id,
            repository_owner=integration.repository_owner,
            repository_name=integration.repository_name,
            label_area_map={
                str(label): int(area_id)
                for label, area_id in (integration.label_area_map or {}).items()
            },
            blocked_label=integration.blocked_label,
            is_active=integration.is_active,
            last_synced_at=integration.last_synced_at,
            created_at=integration.created_at,
            masked_access_token=masked_access_token,
            masked_webhook_secret=masked_webhook_secret,
        )

    def _normalizeLabelMap(self, label_area_map: dict[str, Any]) -> dict[str, int]:
        """Normalizes label mappings for deterministic case-insensitive matching.

        Args:
            label_area_map (dict[str, Any]): Persisted GitHub label to area mapping.

        Returns:
            dict[str, int]: Case-folded label mapping.
        """
        return {
            str(label).strip().casefold(): int(area_id)
            for label, area_id in label_area_map.items()
            if str(label).strip()
        }

    def _extractLabelNames(self, issue: dict[str, Any]) -> set[str]:
        """Extracts case-folded label names from a GitHub issue payload.

        Args:
            issue (dict[str, Any]): GitHub issue payload.

        Returns:
            set[str]: Case-folded label names.
        """
        labels = issue.get("labels", [])
        names: set[str] = set()
        if not isinstance(labels, list):
            return names
        for label in labels:
            if isinstance(label, dict):
                label_name = label.get("name")
            elif isinstance(label, str):
                label_name = label
            else:
                label_name = None
            if label_name:
                names.add(str(label_name).strip().casefold())
        return names

    def _issueIdentity(self, issue: dict[str, Any]) -> str:
        """Builds a stable identity used to deduplicate issues per area.

        Args:
            issue (dict[str, Any]): GitHub issue payload.

        Returns:
            str: Stable issue identity.
        """
        identity = issue.get("id") or issue.get("node_id") or issue.get("number")
        if identity is not None:
            return str(identity)
        return f"{issue.get('title', '')}:{issue.get('created_at', '')}"

    async def registerIntegration(
        self,
        organization_id: int,
        payload: GithubIntegrationCreateSchema,
        actor_user_id: int | None = None,
    ) -> GithubIntegrationResponse:
        """Registers and encrypts a tenant-scoped GitHub repository integration.

        Args:
            organization_id (int): Tenant identifier.
            payload (GithubIntegrationCreateSchema): Repository and credential configuration.
            actor_user_id (int | None, optional): Authenticated actor identifier. Defaults to None.

        Returns:
            GithubIntegrationResponse: Sanitized persisted integration.

        Raises:
            NotFoundException: If the project does not belong to the tenant.
            BadRequestException: If mapped areas do not belong to the project.
            ConflictException: If the repository is already connected.
        """
        project = await self.project_repository.getProject(
            project_id=payload.project_id,
            organization_id=organization_id,
        )
        if project is None:
            raise NotFoundException(detail="Project not found.")

        mapped_area_ids = sorted(set(payload.label_area_map.values()))
        mapped_areas = await self.project_repository.getAreasByIds(
            project_id=payload.project_id,
            organization_id=organization_id,
            area_ids=mapped_area_ids,
        )
        resolved_area_ids = {area.area_id for area in mapped_areas}
        if resolved_area_ids != set(mapped_area_ids):
            raise BadRequestException(
                detail="One or more mapped areas do not belong to the selected project."
            )

        existing = await self.integration_repository.getIntegrationByRepository(
            organization_id=organization_id,
            project_id=payload.project_id,
            repository_owner=payload.repository_owner,
            repository_name=payload.repository_name,
        )
        if existing is not None:
            raise ConflictException(detail="This GitHub repository is already connected to the project.")

        repository_metadata = await self.github_api_client.verifyRepositoryAccess(
            owner=payload.repository_owner,
            repo=payload.repository_name,
            access_token=payload.access_token,
        )
        repository_owner = payload.repository_owner
        repository_name = payload.repository_name
        owner_metadata = repository_metadata.get("owner")
        if isinstance(owner_metadata, dict) and owner_metadata.get("login"):
            repository_owner = str(owner_metadata["login"])
        if repository_metadata.get("name"):
            repository_name = str(repository_metadata["name"])

        canonical_existing = await self.integration_repository.getIntegrationByRepository(
            organization_id=organization_id,
            project_id=payload.project_id,
            repository_owner=repository_owner,
            repository_name=repository_name,
        )
        if canonical_existing is not None:
            raise ConflictException(detail="This GitHub repository is already connected to the project.")

        integration = GithubIntegrationTableDto(
            organization_id=organization_id,
            project_id=payload.project_id,
            repository_owner=repository_owner,
            repository_name=repository_name,
            encrypted_access_token=self.secret_encryption_helper.encryptSecret(payload.access_token),
            encrypted_webhook_secret=self.secret_encryption_helper.encryptSecret(payload.webhook_secret),
            label_area_map=payload.label_area_map,
            blocked_label=payload.blocked_label,
            is_active=True,
        )
        try:
            saved_integration = await self.integration_repository.createIntegration(integration)
        except IntegrityError as exc:
            raise ConflictException(
                detail="This GitHub repository is already connected to the project."
            ) from exc

        await self.security_audit_logger.logIntegrationRegistered(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            integration_id=saved_integration.integration_id,
            repository_full_name=f"{saved_integration.repository_owner}/{saved_integration.repository_name}",
        )
        return self._buildResponse(saved_integration)

    async def listIntegrations(
        self,
        organization_id: int,
        page: int,
        limit: int,
    ) -> tuple[list[GithubIntegrationResponse], int]:
        """Lists sanitized GitHub integrations for a tenant with pagination.

        Args:
            organization_id (int): Tenant identifier.
            page (int): One-based page number.
            limit (int): Page size.

        Returns:
            tuple[list[GithubIntegrationResponse], int]: Sanitized integrations and total count.
        """
        offset = (page - 1) * limit
        integrations = await self.integration_repository.listIntegrations(
            organization_id=organization_id,
            offset=offset,
            limit=limit,
        )
        total = await self.integration_repository.countIntegrations(organization_id=organization_id)
        return [self._buildResponse(integration) for integration in integrations], total

    async def processWebhookEvent(
        self,
        integration_id: int,
        delivery_id: str,
        event_type: str,
        signature_header: str,
        raw_body: bytes,
    ) -> dict[str, str]:
        """Verifies, deduplicates, and processes a GitHub webhook delivery.

        Args:
            integration_id (int): Targeted integration identifier.
            delivery_id (str): GitHub X-GitHub-Delivery identifier.
            event_type (str): GitHub X-GitHub-Event type.
            signature_header (str): GitHub X-Hub-Signature-256 header value.
            raw_body (bytes): Raw webhook request body.

        Returns:
            dict[str, str]: Processing status payload.

        Raises:
            PayloadTooLargeException: If the payload exceeds the configured limit.
            BadRequestException: If identifiers or payload structure are invalid.
            NotFoundException: If the integration does not exist.
            UnauthorizedException: If the HMAC signature is invalid.
            ServiceUnavailableException: If stored credentials cannot be decrypted.
        """
        if len(raw_body) > AppConfig.GITHUB_WEBHOOK_MAX_PAYLOAD_BYTES:
            raise PayloadTooLargeException(detail="GitHub webhook payload exceeds the allowed size.")
        if not self.DELIVERY_ID_PATTERN.match(delivery_id or ""):
            raise BadRequestException(detail="Invalid or missing X-GitHub-Delivery header.")
        if not self.EVENT_TYPE_PATTERN.match(event_type or ""):
            raise BadRequestException(detail="Invalid or missing X-GitHub-Event header.")

        integration = await self.integration_repository.getIntegration(integration_id=integration_id)
        if integration is None:
            raise NotFoundException(detail="GitHub integration not found.")

        try:
            webhook_secret = self.secret_encryption_helper.decryptSecret(
                integration.encrypted_webhook_secret
            )
        except ValueError as exc:
            await self.security_audit_logger.logCredentialDecryptionFailure(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
            )
            raise ServiceUnavailableException(
                detail="Stored GitHub webhook credentials could not be decrypted."
            ) from exc

        if not WebhookSignatureHelper.verifyGithubSignature(
            raw_body=raw_body,
            signature_header=signature_header or "",
            secret=webhook_secret,
        ):
            await self.security_audit_logger.logWebhookSignatureFailure(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                delivery_id=delivery_id,
                event_type=event_type,
            )
            raise UnauthorizedException(detail="Invalid GitHub webhook signature.")

        if not integration.is_active:
            raise BadRequestException(detail="GitHub integration is inactive.")

        was_recorded = await self.integration_repository.recordDelivery(
            delivery_id=delivery_id,
            integration_id=integration.integration_id,
            event_type=event_type,
        )
        if not was_recorded:
            await self.security_audit_logger.logWebhookDuplicate(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                delivery_id=delivery_id,
                event_type=event_type,
            )
            return {"status": "duplicate_ignored"}

        if event_type not in self.ACTIONABLE_EVENT_TYPES:
            await self.security_audit_logger.logWebhookIgnored(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                delivery_id=delivery_id,
                event_type=event_type,
                reason="non_actionable_event",
            )
            return {"status": "ignored_event"}

        try:
            payload_json = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BadRequestException(detail="Invalid GitHub webhook payload.") from exc
        try:
            webhook_payload = GithubWebhookPayloadSchema.model_validate(payload_json)
        except ValidationError as exc:
            raise BadRequestException(detail="Invalid GitHub webhook payload structure.") from exc

        if webhook_payload.action not in self.ACTIONABLE_ACTIONS:
            await self.security_audit_logger.logWebhookIgnored(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                delivery_id=delivery_id,
                event_type=event_type,
                reason="non_actionable_action",
            )
            return {"status": "ignored_event"}

        snapshots = await self._syncLoadedIntegration(integration=integration)
        await self.security_audit_logger.logWebhookProcessed(
            organization_id=integration.organization_id,
            integration_id=integration.integration_id,
            delivery_id=delivery_id,
            event_type=event_type,
            area_count=len(snapshots),
        )
        return {"status": "processed"}

    async def syncIntegrationMetrics(
        self,
        integration_id: int,
        organization_id: int | None = None,
        actor_user_id: int | None = None,
        reference_time: datetime | None = None,
    ) -> list[AreaSnapshotResponse]:
        """Synchronizes deterministic area snapshots from GitHub issues.

        Args:
            integration_id (int): Integration identifier.
            organization_id (int | None, optional): Caller tenant used for isolation. Defaults to None.
            actor_user_id (int | None, optional): Authenticated actor identifier. Defaults to None.
            reference_time (datetime | None, optional): Deterministic calculation instant. Defaults to None.

        Returns:
            list[AreaSnapshotResponse]: Persisted deterministic area snapshots.

        Raises:
            NotFoundException: If the integration does not exist.
            ForbiddenException: If the integration belongs to another tenant.
            BadRequestException: If the integration is inactive or mappings are invalid.
            ServiceUnavailableException: If stored credentials cannot be decrypted.
        """
        integration = await self.integration_repository.getIntegration(integration_id=integration_id)
        if integration is None:
            raise NotFoundException(detail="GitHub integration not found.")
        if organization_id is not None and integration.organization_id != organization_id:
            await self.security_audit_logger.logIntegrationAccessDenied(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                integration_id=integration_id,
                action="sync_metrics",
            )
            raise ForbiddenException(detail="GitHub integration belongs to another organization.")
        return await self._syncLoadedIntegration(
            integration=integration,
            actor_user_id=actor_user_id,
            reference_time=reference_time,
        )

    async def _syncLoadedIntegration(
        self,
        integration: GithubIntegrationTableDto,
        actor_user_id: int | None = None,
        reference_time: datetime | None = None,
    ) -> list[AreaSnapshotResponse]:
        """Synchronizes a previously loaded integration while auditing failures.

        Args:
            integration (GithubIntegrationTableDto): Persisted integration entity.
            actor_user_id (int | None, optional): Authenticated actor identifier. Defaults to None.
            reference_time (datetime | None, optional): Deterministic calculation instant. Defaults to None.

        Returns:
            list[AreaSnapshotResponse]: Persisted deterministic area snapshots.

        Raises:
            BadRequestException: If the integration is inactive or mappings are invalid.
            ServiceUnavailableException: If stored credentials cannot be decrypted.
        """
        if not integration.is_active:
            raise BadRequestException(detail="GitHub integration is inactive.")

        try:
            access_token = self.secret_encryption_helper.decryptSecret(
                integration.encrypted_access_token
            )
        except ValueError as exc:
            await self.security_audit_logger.logCredentialDecryptionFailure(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
            )
            raise ServiceUnavailableException(
                detail="Stored GitHub credentials could not be decrypted."
            ) from exc

        try:
            issues = await self.github_api_client.fetchRepositoryIssues(
                owner=integration.repository_owner,
                repo=integration.repository_name,
                access_token=access_token,
            )
            synced_at = reference_time or datetime.now(timezone.utc)
            snapshots = await self._buildSnapshots(
                integration=integration,
                issues=issues,
                reference_time=synced_at,
            )
            await self.integration_repository.updateLastSyncedAt(
                integration=integration,
                synced_at=synced_at,
            )
            await self.security_audit_logger.logSyncCompleted(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                actor_user_id=actor_user_id,
                issue_count=len(issues),
                area_count=len(snapshots),
            )
            return snapshots
        except BaseAppException as exc:
            await self.security_audit_logger.logSyncFailed(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                actor_user_id=actor_user_id,
                reason=str(getattr(exc, "code", "sync_failed")).lower(),
            )
            raise
        except Exception:
            await self.security_audit_logger.logSyncFailed(
                organization_id=integration.organization_id,
                integration_id=integration.integration_id,
                actor_user_id=actor_user_id,
                reason="unexpected_error",
            )
            raise

    async def _buildSnapshots(
        self,
        integration: GithubIntegrationTableDto,
        issues: list[dict[str, Any]],
        reference_time: datetime,
    ) -> list[AreaSnapshotResponse]:
        """Aggregates GitHub issues into deterministic per-area metric snapshots.

        Args:
            integration (GithubIntegrationTableDto): Persisted integration entity.
            issues (list[dict[str, Any]]): Normalized GitHub issues.
            reference_time (datetime): Deterministic calculation instant.

        Returns:
            list[AreaSnapshotResponse]: Persisted area snapshots ordered by area identifier.

        Raises:
            BadRequestException: If mappings are empty or reference missing areas.
        """
        label_area_map = self._normalizeLabelMap(integration.label_area_map or {})
        if not label_area_map:
            raise BadRequestException(detail="GitHub integration has no label to area mappings.")
        area_ids = sorted(set(label_area_map.values()))
        areas = await self.project_repository.getAreasByIds(
            project_id=integration.project_id,
            organization_id=integration.organization_id,
            area_ids=area_ids,
        )
        areas_by_id = {area.area_id: area for area in areas}
        if set(areas_by_id) != set(area_ids):
            raise BadRequestException(
                detail="GitHub integration references areas that no longer exist."
            )

        blocked_label = (integration.blocked_label or "blocked").strip().casefold()
        area_issue_buckets: dict[int, dict[str, dict[str, Any]]] = {
            area_id: {} for area_id in area_ids
        }
        for issue in issues:
            issue_labels = self._extractLabelNames(issue)
            matched_area_ids = {
                label_area_map[label]
                for label in issue_labels
                if label in label_area_map
            }
            if not matched_area_ids:
                continue
            issue_identity = self._issueIdentity(issue)
            for area_id in matched_area_ids:
                area_issue_buckets[area_id][issue_identity] = issue

        snapshots: list[AreaSnapshotResponse] = []
        for area_id in area_ids:
            area_issues = list(area_issue_buckets[area_id].values())
            total_tasks = len(area_issues)
            completed_tasks = sum(
                1 for issue in area_issues if str(issue.get("state", "")).casefold() == "closed"
            )
            blocked_tasks = sum(
                1
                for issue in area_issues
                if blocked_label in self._extractLabelNames(issue)
            )
            snapshot = await self.metric_service.createAreaSnapshot(
                organization_id=integration.organization_id,
                project_id=integration.project_id,
                area_id=area_id,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                blocked_tasks=blocked_tasks,
                deadline=areas_by_id[area_id].deadline,
                reference_time=reference_time,
            )
            snapshots.append(snapshot)
        return snapshots
