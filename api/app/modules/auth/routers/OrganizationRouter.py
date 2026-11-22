from fastapi import APIRouter, Depends, Query, status
from app.common.schemas.ApiResponseSchema import PaginatedResponseSchema, PaginationInfo, ResponseSchema
from app.core.AuthContext import AuthContext
from app.core.DependencyContainer import (
    getCurrentAuth,
    getOrganizationService,
    getRecoveryService,
)
from app.modules.auth.schemas.AuthSchema import MessageResponseSchema
from app.modules.auth.schemas.OrganizationSchema import (
    InvitationCreateSchema,
    InvitationResponse,
)
from app.modules.auth.schemas.RecoverySchema import (
    RecoveryApprovalRequest,
    RecoveryApprovalResponse,
    RecoveryRequestResponse,
)
from app.modules.auth.service.OrganizationService import OrganizationService
from app.modules.auth.service.RecoveryService import RecoveryService


class OrganizationRouter:

    def __init__(self) -> None:
        """Configures the organization invitations and recovery requests router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers organization invitation and member account recovery review routes."""
        self.router.add_api_route(
            path="/organizations/invitations",
            endpoint=self.createInvitation,
            methods=["POST"],
            response_model=ResponseSchema[InvitationResponse],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            path="/organizations/invitations",
            endpoint=self.listInvitations,
            methods=["GET"],
            response_model=PaginatedResponseSchema[InvitationResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/organizations/invitations/{invitation_id}",
            endpoint=self.cancelInvitation,
            methods=["DELETE"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/organizations/recovery-requests",
            endpoint=self.listRecoveryRequests,
            methods=["GET"],
            response_model=PaginatedResponseSchema[RecoveryRequestResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/organizations/recovery-requests/{request_id}",
            endpoint=self.reviewRecoveryRequest,
            methods=["PATCH"],
            response_model=ResponseSchema[RecoveryApprovalResponse],
            status_code=status.HTTP_200_OK,
        )

    async def createInvitation(
        self,
        payload: InvitationCreateSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        organization_service: OrganizationService = Depends(getOrganizationService),
    ) -> ResponseSchema[InvitationResponse]:
        """Invites an email address to the authenticated administrator's organization.

        Args:
            payload (InvitationCreateSchema): Invitation email and role.
            auth (AuthContext): Validated authentication context.
            organization_service (OrganizationService): Injected organization service.

        Returns:
            ResponseSchema[InvitationResponse]: Created invitation.
        """
        invitation = await organization_service.createInvitation(admin=auth.user, payload=payload)
        return ResponseSchema(data=invitation)

    async def listInvitations(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        auth: AuthContext = Depends(getCurrentAuth),
        organization_service: OrganizationService = Depends(getOrganizationService),
    ) -> PaginatedResponseSchema[InvitationResponse]:
        """Lists invitations for the authenticated administrator's organization.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size. Defaults to 20.
            auth (AuthContext): Validated authentication context.
            organization_service (OrganizationService): Injected organization service.

        Returns:
            PaginatedResponseSchema[InvitationResponse]: Paginated invitations.
        """
        items, total = await organization_service.listInvitations(
            admin=auth.user,
            page=page,
            limit=limit,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=items,
        )

    async def cancelInvitation(
        self,
        invitation_id: int,
        auth: AuthContext = Depends(getCurrentAuth),
        organization_service: OrganizationService = Depends(getOrganizationService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Cancels a pending invitation.

        Args:
            invitation_id (int): Invitation identifier.
            auth (AuthContext): Validated authentication context.
            organization_service (OrganizationService): Injected organization service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await organization_service.cancelInvitation(admin=auth.user, invitation_id=invitation_id)
        return ResponseSchema(data=MessageResponseSchema(message="Invitation has been cancelled."))

    async def listRecoveryRequests(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        request_status: str | None = Query(default=None, alias="status"),
        auth: AuthContext = Depends(getCurrentAuth),
        recovery_service: RecoveryService = Depends(getRecoveryService),
    ) -> PaginatedResponseSchema[RecoveryRequestResponse]:
        """Lists account recovery requests for the authenticated administrator.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size. Defaults to 20.
            request_status (str | None, optional): Optional status filter. Defaults to None.
            auth (AuthContext): Validated authentication context.
            recovery_service (RecoveryService): Injected recovery service.

        Returns:
            PaginatedResponseSchema[RecoveryRequestResponse]: Paginated recovery requests.
        """
        items, total = await recovery_service.listRequests(
            admin=auth.user,
            page=page,
            limit=limit,
            status=request_status,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=items,
        )

    async def reviewRecoveryRequest(
        self,
        request_id: str,
        payload: RecoveryApprovalRequest,
        auth: AuthContext = Depends(getCurrentAuth),
        recovery_service: RecoveryService = Depends(getRecoveryService),
    ) -> ResponseSchema[RecoveryApprovalResponse]:
        """Approves or rejects an account recovery request.

        Args:
            request_id (str): Recovery request identifier.
            payload (RecoveryApprovalRequest): Decision and evidence reference.
            auth (AuthContext): Validated authentication context.
            recovery_service (RecoveryService): Injected recovery service.

        Returns:
            ResponseSchema[RecoveryApprovalResponse]: Decision and optional recovery token.
        """
        result = await recovery_service.reviewRequest(
            admin=auth.user,
            request_id=request_id,
            payload=payload,
        )
        return ResponseSchema(data=result)
