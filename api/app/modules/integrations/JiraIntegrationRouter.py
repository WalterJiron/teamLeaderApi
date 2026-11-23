from fastapi import APIRouter, Depends, Path, Query, status

from app.common.schemas.ApiResponseSchema import (
    PaginatedResponseSchema,
    PaginationInfo,
    ResponseSchema,
)
from app.core.dependencies import (
    getCurrentManager,
    getCurrentUser,
    getJiraSyncService,
)
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.integrations.schemas.JiraIntegrationSchema import (
    JiraIntegrationCreateSchema,
    JiraIntegrationResponseSchema,
    JiraSyncResponseSchema,
)
from app.modules.integrations.service.JiraSyncService import JiraSyncService


class JiraIntegrationRouter:

    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/jira-integrations",
            tags=["Jira Integrations"],
        )
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        self.router.add_api_route(
            path="",
            endpoint=self.createIntegration,
            methods=["POST"],
            response_model=ResponseSchema[JiraIntegrationResponseSchema],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            path="",
            endpoint=self.listIntegrations,
            methods=["GET"],
            response_model=PaginatedResponseSchema[JiraIntegrationResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/{integration_id}/syncs",
            endpoint=self.syncIntegration,
            methods=["POST"],
            response_model=ResponseSchema[JiraSyncResponseSchema],
            status_code=status.HTTP_200_OK,
        )

    async def createIntegration(
        self,
        payload: JiraIntegrationCreateSchema,
        current_user: UserTableDto = Depends(getCurrentManager),
        jira_sync_service: JiraSyncService = Depends(getJiraSyncService),
    ) -> ResponseSchema[JiraIntegrationResponseSchema]:
        integration = await jira_sync_service.registerIntegration(
            organization_id=current_user.organization_id,
            payload=payload,
        )
        return ResponseSchema(data=integration)

    async def listIntegrations(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        current_user: UserTableDto = Depends(getCurrentUser),
        jira_sync_service: JiraSyncService = Depends(getJiraSyncService),
    ) -> PaginatedResponseSchema[JiraIntegrationResponseSchema]:
        integrations, total = await jira_sync_service.listIntegrations(
            organization_id=current_user.organization_id,
            page=page,
            limit=limit,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=integrations,
        )

    async def syncIntegration(
        self,
        integration_id: int = Path(..., ge=1),
        current_user: UserTableDto = Depends(getCurrentManager),
        jira_sync_service: JiraSyncService = Depends(getJiraSyncService),
    ) -> ResponseSchema[JiraSyncResponseSchema]:
        result = await jira_sync_service.syncIntegration(
            integration_id=integration_id,
            organization_id=current_user.organization_id,
        )
        return ResponseSchema(data=result)
