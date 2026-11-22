from fastapi import APIRouter, Depends, Query, status
from app.common.schemas.ApiResponseSchema import PaginatedResponseSchema, PaginationInfo, ResponseSchema
from app.core.DependencyContainer import getAdminAuthService, getCurrentAdmin
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.AuditSchema import AuditLogResponse
from app.modules.auth.schemas.AuthSchema import MessageResponseSchema, UserProfileResponse, UserStatusSchema
from app.modules.auth.schemas.SessionSchema import SessionResponse
from app.modules.auth.service.AdminAuthService import AdminAuthService


class AdminAuthRouter:

    def __init__(self) -> None:
        """Configures the administrative authentication and audit router."""
        self.router = APIRouter(prefix="/admin/auth", tags=["Administration"])
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers user administration, session control, and audit routes."""
        self.router.add_api_route(
            path="/users",
            endpoint=self.listUsers,
            methods=["GET"],
            response_model=PaginatedResponseSchema[UserProfileResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}",
            endpoint=self.getUser,
            methods=["GET"],
            response_model=ResponseSchema[UserProfileResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}/unlocks",
            endpoint=self.unlockUser,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}/status",
            endpoint=self.setUserStatus,
            methods=["PATCH"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}/password-resets",
            endpoint=self.forcePasswordReset,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/users/{user_id}/session-revocations",
            endpoint=self.revokeUserSessions,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}/mfa-resets",
            endpoint=self.resetUserMfa,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}/sessions",
            endpoint=self.listUserSessions,
            methods=["GET"],
            response_model=ResponseSchema[list[SessionResponse]],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/users/{user_id}",
            endpoint=self.softDeleteUser,
            methods=["DELETE"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/audit-logs",
            endpoint=self.listAuditLogs,
            methods=["GET"],
            response_model=PaginatedResponseSchema[AuditLogResponse],
            status_code=status.HTTP_200_OK,
        )

    async def listUsers(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        search: str | None = Query(default=None, max_length=120),
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> PaginatedResponseSchema[UserProfileResponse]:
        """Lists users in the administrator's organization.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size. Defaults to 20.
            search (str | None, optional): Name or email fragment. Defaults to None.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            PaginatedResponseSchema[UserProfileResponse]: Paginated users.
        """
        users, total = await admin_auth_service.listUsers(
            admin=admin,
            page=page,
            limit=limit,
            search=search,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=users,
        )

    async def getUser(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[UserProfileResponse]:
        """Returns a scoped user profile.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[UserProfileResponse]: Target user profile.
        """
        user = await admin_auth_service.getUser(admin=admin, user_id=user_id)
        return ResponseSchema(data=user)

    async def unlockUser(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Unlocks a user account after repeated failed sign-in attempts.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.unlockUser(admin=admin, user_id=user_id)
        return ResponseSchema(data=MessageResponseSchema(message="User account unlocked."))

    async def setUserStatus(
        self,
        user_id: int,
        payload: UserStatusSchema,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Activates or deactivates a user account.

        Args:
            user_id (int): Target user identifier.
            payload (UserStatusSchema): Desired account state.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.setUserActive(
            admin=admin,
            user_id=user_id,
            is_active=payload.is_active,
        )
        return ResponseSchema(data=MessageResponseSchema(message="User status updated."))

    async def forcePasswordReset(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Sends a reset link and forces a password change for a user.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.forcePasswordReset(admin=admin, user_id=user_id)
        return ResponseSchema(data=MessageResponseSchema(message="Password reset email sent."))

    async def revokeUserSessions(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Revokes all sessions for a user.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.revokeUserSessions(admin=admin, user_id=user_id)
        return ResponseSchema(data=MessageResponseSchema(message="User sessions revoked."))

    async def resetUserMfa(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Removes MFA settings for a user as part of assisted recovery.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.resetUserMfa(admin=admin, user_id=user_id)
        return ResponseSchema(data=MessageResponseSchema(message="User MFA settings reset."))

    async def listUserSessions(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[list[SessionResponse]]:
        """Lists active sessions for a scoped user.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[list[SessionResponse]]: Active sessions.
        """
        sessions = await admin_auth_service.listUserSessions(admin=admin, user_id=user_id)
        return ResponseSchema(data=sessions)

    async def softDeleteUser(
        self,
        user_id: int,
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Soft-deletes a user account.

        Args:
            user_id (int): Target user identifier.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await admin_auth_service.softDeleteUser(admin=admin, user_id=user_id)
        return ResponseSchema(data=MessageResponseSchema(message="User account deleted."))

    async def listAuditLogs(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        event_type: str | None = Query(default=None, max_length=64),
        admin: UserTableDto = Depends(getCurrentAdmin),
        admin_auth_service: AdminAuthService = Depends(getAdminAuthService),
    ) -> PaginatedResponseSchema[AuditLogResponse]:
        """Lists authentication audit events for the administrator's organization.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size. Defaults to 20.
            event_type (str | None, optional): Optional event type filter. Defaults to None.
            admin (UserTableDto): Authenticated administrator.
            admin_auth_service (AdminAuthService): Injected administrative service.

        Returns:
            PaginatedResponseSchema[AuditLogResponse]: Paginated audit entries.
        """
        logs, total = await admin_auth_service.listAuditLogs(
            admin=admin,
            page=page,
            limit=limit,
            event_type=event_type,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=logs,
        )
