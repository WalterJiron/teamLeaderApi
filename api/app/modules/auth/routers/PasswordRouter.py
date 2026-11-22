from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.AuthContext import AuthContext
from app.core.DependencyContainer import getAuthService, getCurrentAuth
from app.modules.auth.schemas.AuthSchema import (
    EmailChangeConfirmSchema,
    EmailChangeRequestSchema,
    EmailVerificationConfirmSchema,
    MessageResponseSchema,
    PasswordResetRequestSchema,
    PasswordResetSchema,
    UserProfileResponse,
)
from app.modules.auth.service.AuthService import AuthService


class PasswordRouter:

    def __init__(self) -> None:
        """Configures the password reset, email verification, and email change router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers password recovery and email lifecycle confirmation routes."""
        self.router.add_api_route(
            path="/password-resets",
            endpoint=self.requestPasswordReset,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/password-resets/confirmations",
            endpoint=self.confirmPasswordReset,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/email-verifications",
            endpoint=self.resendEmailVerification,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/email-verifications/confirmations",
            endpoint=self.confirmEmailVerification,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/email-changes",
            endpoint=self.requestEmailChange,
            methods=["POST"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_202_ACCEPTED,
        )
        self.router.add_api_route(
            path="/email-changes/confirmations",
            endpoint=self.confirmEmailChange,
            methods=["POST"],
            response_model=ResponseSchema[UserProfileResponse],
            status_code=status.HTTP_200_OK,
        )

    async def requestPasswordReset(
        self,
        payload: PasswordResetRequestSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Requests a password reset email without revealing account existence.

        Args:
            payload (PasswordResetRequestSchema): Account email.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Generic confirmation message.
        """
        await auth_service.requestPasswordReset(email=payload.email)
        return ResponseSchema(
            data=MessageResponseSchema(
                message="If the account exists, a password reset email has been sent."
            )
        )

    async def confirmPasswordReset(
        self,
        payload: PasswordResetSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Completes a password reset with a single-use token.

        Args:
            payload (PasswordResetSchema): Reset token and new password.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.confirmPasswordReset(token=payload.token, new_password=payload.new_password)
        return ResponseSchema(data=MessageResponseSchema(message="Password has been reset."))

    async def resendEmailVerification(
        self,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Sends a new verification email to the authenticated user.

        Args:
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.sendEmailVerification(user=auth.user)
        return ResponseSchema(data=MessageResponseSchema(message="Verification email sent."))

    async def confirmEmailVerification(
        self,
        payload: EmailVerificationConfirmSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Confirms a primary email address with a single-use token.

        Args:
            payload (EmailVerificationConfirmSchema): Verification token.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.confirmEmailVerification(token=payload.token)
        return ResponseSchema(data=MessageResponseSchema(message="Email address verified."))

    async def requestEmailChange(
        self,
        payload: EmailChangeRequestSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Requests a primary email change confirmation.

        Args:
            payload (EmailChangeRequestSchema): New email, password, and optional MFA code.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.requestEmailChange(user=auth.user, payload=payload)
        return ResponseSchema(data=MessageResponseSchema(message="Confirmation email sent."))

    async def confirmEmailChange(
        self,
        payload: EmailChangeConfirmSchema,
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[UserProfileResponse]:
        """Confirms a primary email change.

        Args:
            payload (EmailChangeConfirmSchema): Email change token.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[UserProfileResponse]: Updated user profile.
        """
        profile = await auth_service.confirmEmailChange(token=payload.token)
        return ResponseSchema(data=profile)
