from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.AuthContext import AuthContext
from app.core.DependencyContainer import getAuthService, getCurrentAuth
from app.modules.auth.schemas.AuthSchema import (
    MessageResponseSchema,
    PasswordChangeSchema,
    UserProfileResponse,
)
from app.modules.auth.schemas.SessionSchema import SessionResponse
from app.modules.auth.service.AuthService import AuthService


class ProfileRouter:

    def __init__(self) -> None:
        """Configures the current user profile, password change, and session control router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers authenticated profile management, credential change, and session revocation routes."""
        self.router.add_api_route(
            path="/me",
            endpoint=self.getMe,
            methods=["GET"],
            response_model=ResponseSchema[UserProfileResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/password",
            endpoint=self.changePassword,
            methods=["PATCH"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/logouts",
            endpoint=self.logoutAll,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/sessions",
            endpoint=self.listSessions,
            methods=["GET"],
            response_model=ResponseSchema[list[SessionResponse]],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/sessions/{session_id}",
            endpoint=self.revokeSession,
            methods=["DELETE"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )

    async def getMe(
        self,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[UserProfileResponse]:
        """Returns the authenticated user profile.

        Args:
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[UserProfileResponse]: Authenticated user profile.
        """
        return ResponseSchema(data=auth_service.getProfile(user=auth.user))

    async def changePassword(
        self,
        payload: PasswordChangeSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Changes the authenticated user's password.

        Args:
            payload (PasswordChangeSchema): Current and new passwords plus optional MFA code.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.changePassword(
            user=auth.user,
            payload=payload,
            current_session_id=auth.session_id,
        )
        return ResponseSchema(data=MessageResponseSchema(message="Password has been changed."))

    async def logoutAll(
        self,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Revokes every session for the authenticated user.

        Args:
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.logoutAll(user=auth.user, current_session_id=auth.session_id)
        return ResponseSchema(data=MessageResponseSchema(message="All sessions have been revoked."))

    async def listSessions(
        self,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[list[SessionResponse]]:
        """Lists the authenticated user's active sessions.

        Args:
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[list[SessionResponse]]: Active sessions.
        """
        sessions = await auth_service.listSessions(
            user=auth.user,
            current_session_id=auth.session_id,
        )
        return ResponseSchema(data=sessions)

    async def revokeSession(
        self,
        session_id: str,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Revokes one of the authenticated user's sessions.

        Args:
            session_id (str): Session identifier.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.revokeSession(
            user=auth.user,
            session_id=session_id,
            current_session_id=auth.session_id,
        )
        return ResponseSchema(data=MessageResponseSchema(message="Session has been revoked."))
