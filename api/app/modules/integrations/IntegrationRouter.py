from fastapi import APIRouter, Depends, Header, Path, Query, Request, status
from app.common.exceptions.AppExceptions import PayloadTooLargeException
from app.common.schemas.ApiResponseSchema import PaginatedResponseSchema, PaginationInfo, ResponseSchema
from app.core.AppConfig import AppConfig
from app.core.dependencies import getCurrentManager, getCurrentUser, getGithubSyncService
from app.core.RateLimiter import RateLimiter
from app.core.RequestContext import getClientIp
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.integrations.schemas.GithubIntegrationSchema import (
    GithubIntegrationCreateSchema,
    GithubIntegrationResponse,
)
from app.modules.integrations.service.GithubSyncService import GithubSyncService
from app.modules.metrics.schemas.AreaSnapshotSchema import AreaSnapshotResponse


class IntegrationRouter:

    def __init__(self) -> None:
        """Configures the GitHub integration management and webhook router."""
        self.router = APIRouter(prefix="/github-integrations", tags=["GitHub Integrations"])
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers integration registration, listing, manual sync, and webhook routes."""
        self.router.add_api_route(
            path="",
            endpoint=self.createIntegration,
            methods=["POST"],
            response_model=ResponseSchema[GithubIntegrationResponse],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            path="",
            endpoint=self.listIntegrations,
            methods=["GET"],
            response_model=PaginatedResponseSchema[GithubIntegrationResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/{integration_id}/syncs",
            endpoint=self.triggerSync,
            methods=["POST"],
            response_model=ResponseSchema[list[AreaSnapshotResponse]],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/{integration_id}/webhooks",
            endpoint=self.receiveWebhook,
            methods=["POST"],
            response_model=ResponseSchema[dict[str, str]],
            status_code=status.HTTP_202_ACCEPTED,
        )

    async def createIntegration(
        self,
        payload: GithubIntegrationCreateSchema,
        current_user: UserTableDto = Depends(getCurrentManager),
        github_sync_service: GithubSyncService = Depends(getGithubSyncService),
    ) -> ResponseSchema[GithubIntegrationResponse]:
        """Registers a GitHub repository integration for the authenticated tenant.

        Args:
            payload (GithubIntegrationCreateSchema): Repository and credential configuration.
            current_user (UserTableDto): Authenticated team leader or administrator.
            github_sync_service (GithubSyncService): Injected GitHub synchronization service.

        Returns:
            ResponseSchema[GithubIntegrationResponse]: Sanitized created integration.
        """
        integration = await github_sync_service.registerIntegration(
            organization_id=current_user.organization_id,
            payload=payload,
            actor_user_id=current_user.user_id,
        )
        return ResponseSchema(data=integration)

    async def listIntegrations(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        current_user: UserTableDto = Depends(getCurrentUser),
        github_sync_service: GithubSyncService = Depends(getGithubSyncService),
    ) -> PaginatedResponseSchema[GithubIntegrationResponse]:
        """Lists sanitized GitHub integrations for the authenticated tenant.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size. Defaults to 20.
            current_user (UserTableDto): Authenticated user.
            github_sync_service (GithubSyncService): Injected GitHub synchronization service.

        Returns:
            PaginatedResponseSchema[GithubIntegrationResponse]: Paginated integrations.
        """
        integrations, total = await github_sync_service.listIntegrations(
            organization_id=current_user.organization_id,
            page=page,
            limit=limit,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=integrations,
        )

    async def triggerSync(
        self,
        integration_id: int = Path(..., ge=1),
        current_user: UserTableDto = Depends(getCurrentManager),
        github_sync_service: GithubSyncService = Depends(getGithubSyncService),
    ) -> ResponseSchema[list[AreaSnapshotResponse]]:
        """Triggers an on-demand deterministic repository synchronization.

        Args:
            integration_id (int): Integration identifier.
            current_user (UserTableDto): Authenticated team leader or administrator.
            github_sync_service (GithubSyncService): Injected GitHub synchronization service.

        Returns:
            ResponseSchema[list[AreaSnapshotResponse]]: Persisted area snapshots.
        """
        snapshots = await github_sync_service.syncIntegrationMetrics(
            integration_id=integration_id,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.user_id,
        )
        return ResponseSchema(data=snapshots)

    async def receiveWebhook(
        self,
        request: Request,
        integration_id: int = Path(..., ge=1),
        signature_header: str | None = Header(default=None, alias="X-Hub-Signature-256"),
        delivery_id: str | None = Header(default=None, alias="X-GitHub-Delivery"),
        event_type: str | None = Header(default=None, alias="X-GitHub-Event"),
        github_sync_service: GithubSyncService = Depends(getGithubSyncService),
    ) -> ResponseSchema[dict[str, str]]:
        """Receives an HMAC-authenticated GitHub webhook and updates area snapshots.

        Args:
            request (Request): Incoming webhook request with the raw payload.
            integration_id (int): Integration identifier.
            signature_header (str | None, optional): GitHub HMAC signature header. Defaults to None.
            delivery_id (str | None, optional): GitHub delivery identifier. Defaults to None.
            event_type (str | None, optional): GitHub event type. Defaults to None.
            github_sync_service (GithubSyncService): Injected GitHub synchronization service.

        Returns:
            ResponseSchema[dict[str, str]]: Webhook processing status.
        """
        await RateLimiter.enforce(
            key=f"github-webhook:{integration_id}:{getClientIp() or 'unknown'}",
            limit=AppConfig.GITHUB_WEBHOOK_RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
        )
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > AppConfig.GITHUB_WEBHOOK_MAX_PAYLOAD_BYTES:
                    raise PayloadTooLargeException(
                        detail="GitHub webhook payload exceeds the allowed size."
                    )
            except ValueError:
                raise PayloadTooLargeException(detail="Invalid webhook Content-Length header.")
        raw_body = await request.body()
        result = await github_sync_service.processWebhookEvent(
            integration_id=integration_id,
            delivery_id=delivery_id or "",
            event_type=event_type or "",
            signature_header=signature_header or "",
            raw_body=raw_body,
        )
        return ResponseSchema(data=result)
