from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.dependencies import getAuthService
from app.core.RateLimiter import RateLimiter
from app.core.RequestContext import getClientIp
from app.modules.auth.schemas.AuthSchema import (
    LoginRequestSchema,
    LoginResponseSchema,
    MessageResponseSchema,
    RefreshTokenSchema,
    RegisterUserSchema,
    TokenPairResponse,
)
from app.modules.auth.schemas.MfaSchema import MfaVerifySchema
from app.modules.auth.service.AuthService import AuthService


class SessionRouter:

    def __init__(self) -> None:
        """Configures the session, registration, and token lifecycle router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers registration, login, mfa-completion, token refresh, and logout routes."""
        self.router.add_api_route(
            path="/registrations",
            endpoint=self.register,
            methods=["POST"],
            response_model=ResponseSchema[TokenPairResponse],
            status_code=status.HTTP_201_CREATED,
        )
        self.router.add_api_route(
            path="/sessions",
            endpoint=self.login,
            methods=["POST"],
            response_model=ResponseSchema[LoginResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/sessions/mfa",
            endpoint=self.completeMfaLogin,
            methods=["POST"],
            response_model=ResponseSchema[TokenPairResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/tokens",
            endpoint=self.refresh,
            methods=["POST"],
            response_model=ResponseSchema[TokenPairResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/logouts",
            endpoint=self.logout,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )

    async def register(
        self,
        payload: RegisterUserSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[TokenPairResponse]:
        """Registers a user through invitation or open registration.

        Args:
            payload (RegisterUserSchema): Registration payload.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[TokenPairResponse]: Initial token pair and profile.
        """
        await RateLimiter.enforce(
            key=f"rl:registration:ip:{getClientIp() or 'unknown'}",
            limit=5,
            window_seconds=3600,
        )
        tokens = await auth_service.registerUser(payload=payload)
        return ResponseSchema(data=tokens)

    async def login(
        self,
        payload: LoginRequestSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[LoginResponseSchema]:
        """Authenticates credentials and returns tokens or an MFA challenge.

        Args:
            payload (LoginRequestSchema): Login credentials.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[LoginResponseSchema]: Login result.
        """
        result = await auth_service.loginUser(payload=payload)
        return ResponseSchema(data=result)

    async def completeMfaLogin(
        self,
        payload: MfaVerifySchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[TokenPairResponse]:
        """Completes an MFA challenge and issues tokens.

        Args:
            payload (MfaVerifySchema): MFA challenge token and code.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[TokenPairResponse]: Token pair and profile.
        """
        tokens = await auth_service.completeMfaLogin(
            mfa_token=payload.mfa_token,
            code=payload.code,
        )
        return ResponseSchema(data=tokens)

    async def refresh(
        self,
        payload: RefreshTokenSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[TokenPairResponse]:
        """Rotates a refresh token into a new token pair.

        Args:
            payload (RefreshTokenSchema): Refresh token payload.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[TokenPairResponse]: Rotated token pair.
        """
        tokens = await auth_service.refreshAccessToken(refresh_token=payload.refresh_token)
        return ResponseSchema(data=tokens)

    async def logout(
        self,
        payload: RefreshTokenSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Revokes the session associated with a refresh token.

        Args:
            payload (RefreshTokenSchema): Refresh token payload.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.logout(refresh_token=payload.refresh_token)
        return ResponseSchema(data=MessageResponseSchema(message="Signed out."))
