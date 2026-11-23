from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.AuthContext import AuthContext
from app.core.dependencies import getAuthService, getCurrentAuth, getRecoveryService
from app.core.RateLimiter import RateLimiter
from app.core.RequestContext import getClientIp
from app.modules.auth.schemas.AuthSchema import (
    MessageResponseSchema,
    PasswordResetSchema,
    RecoveryEmailConfirmSchema,
    RecoveryEmailRequestSchema,
)
from app.modules.auth.schemas.RecoverySchema import (
    AccountRecoveryRequestSchema,
    RecoveryWithCodeSchema,
)
from app.modules.auth.service.AuthService import AuthService
from app.modules.auth.service.RecoveryService import RecoveryService


class RecoveryRouter:

    def __init__(self) -> None:
        """Configures the account recovery, recovery email, and emergency reset router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers recovery email, recovery code, and administrative recovery routes."""
        self.router.add_api_route(
            path="/recovery-emails",
            endpoint=self.requestRecoveryEmail,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/recovery-emails/confirmations",
            endpoint=self.confirmRecoveryEmail,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/recovery-code-resets",
            endpoint=self.resetWithRecoveryCode,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/recovery-requests",
            endpoint=self.requestAccountRecovery,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/recovery-requests/confirmations",
            endpoint=self.confirmAccountRecovery,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )

    async def requestRecoveryEmail(
        self,
        payload: RecoveryEmailRequestSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Requests verification for a recovery email address.

        Args:
            payload (RecoveryEmailRequestSchema): Recovery email and password.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.requestRecoveryEmail(user=auth.user, payload=payload)
        return ResponseSchema(data=MessageResponseSchema(message="Recovery email verification sent."))

    async def confirmRecoveryEmail(
        self,
        payload: RecoveryEmailConfirmSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Confirms a recovery email address.

        Args:
            payload (RecoveryEmailConfirmSchema): Recovery email verification token.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.confirmRecoveryEmail(token=payload.token)
        return ResponseSchema(data=MessageResponseSchema(message="Recovery email verified."))

    async def resetWithRecoveryCode(
        self,
        payload: RecoveryWithCodeSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Resets a password using an MFA recovery code.

        Args:
            payload (RecoveryWithCodeSchema): Email, recovery code, and new password.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.resetPasswordWithRecoveryCode(
            email=payload.email,
            recovery_code=payload.recovery_code,
            new_password=payload.new_password,
        )
        return ResponseSchema(data=MessageResponseSchema(message="Password has been reset."))

    async def requestAccountRecovery(
        self,
        payload: AccountRecoveryRequestSchema,
        recovery_service: RecoveryService = Depends(getRecoveryService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Files an administrator-assisted account recovery request.

        Args:
            payload (AccountRecoveryRequestSchema): Account email and reason.
            recovery_service (RecoveryService): Injected recovery service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Generic confirmation message.
        """
        await RateLimiter.enforce(
            key=f"rl:recovery-request:ip:{getClientIp() or 'unknown'}",
            limit=5,
            window_seconds=3600,
        )
        await recovery_service.requestRecovery(email=payload.email, reason=payload.reason)
        return ResponseSchema(
            data=MessageResponseSchema(
                message="If the account exists, an administrator will review the recovery request."
            )
        )

    async def confirmAccountRecovery(
        self,
        payload: PasswordResetSchema,
        recovery_service: RecoveryService = Depends(getRecoveryService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Completes an administrator-approved account recovery.

        Args:
            payload (PasswordResetSchema): Recovery token and new password.
            recovery_service (RecoveryService): Injected recovery service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await recovery_service.confirmRecovery(token=payload.token, new_password=payload.new_password)
        return ResponseSchema(data=MessageResponseSchema(message="Account access has been restored."))
