from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.AuthContext import AuthContext
from app.core.dependencies import getAuthService, getCurrentAuth
from app.modules.auth.schemas.AuthSchema import MessageResponseSchema
from app.modules.auth.schemas.MfaSchema import (
    MfaConfirmSchema,
    MfaDisableSchema,
    MfaRecoveryCodesResponse,
    MfaSetupResponse,
)
from app.modules.auth.service.AuthService import AuthService


class MfaRouter:

    def __init__(self) -> None:
        """Configures the multi-factor authentication enrollment, verification, and recovery router."""
        self.router = APIRouter()
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers TOTP setup, confirmation, disablement, and code regeneration routes."""
        self.router.add_api_route(
            path="/me/mfa/setups",
            endpoint=self.setupMfa,
            methods=["POST"],
            response_model=ResponseSchema[MfaSetupResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/mfa/confirmations",
            endpoint=self.confirmMfa,
            methods=["POST"],
            response_model=ResponseSchema[MfaRecoveryCodesResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/mfa",
            endpoint=self.disableMfa,
            methods=["DELETE"],
            response_model=ResponseSchema[MessageResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/me/mfa/recovery-codes",
            endpoint=self.regenerateRecoveryCodes,
            methods=["POST"],
            response_model=ResponseSchema[MfaRecoveryCodesResponse],
            status_code=status.HTTP_200_OK,
        )

    async def setupMfa(
        self,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MfaSetupResponse]:
        """Starts TOTP enrollment for the authenticated user.

        Args:
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MfaSetupResponse]: Secret and provisioning URI.
        """
        setup = await auth_service.setupMfa(user=auth.user)
        return ResponseSchema(data=setup)

    async def confirmMfa(
        self,
        payload: MfaConfirmSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MfaRecoveryCodesResponse]:
        """Confirms TOTP enrollment and returns recovery codes.

        Args:
            payload (MfaConfirmSchema): TOTP code.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MfaRecoveryCodesResponse]: Plain-text recovery codes.
        """
        codes = await auth_service.confirmMfa(user=auth.user, code=payload.code)
        return ResponseSchema(data=MfaRecoveryCodesResponse(recovery_codes=codes))

    async def disableMfa(
        self,
        payload: MfaDisableSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MessageResponseSchema]:
        """Disables MFA for the authenticated user.

        Args:
            payload (MfaDisableSchema): Password and verification code.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MessageResponseSchema]: Confirmation message.
        """
        await auth_service.disableMfa(user=auth.user, payload=payload)
        return ResponseSchema(data=MessageResponseSchema(message="MFA has been disabled."))

    async def regenerateRecoveryCodes(
        self,
        payload: MfaConfirmSchema,
        auth: AuthContext = Depends(getCurrentAuth),
        auth_service: AuthService = Depends(getAuthService),
    ) -> ResponseSchema[MfaRecoveryCodesResponse]:
        """Regenerates MFA recovery codes after verifying a current code.

        Args:
            payload (MfaConfirmSchema): TOTP or recovery code.
            auth (AuthContext): Validated authentication context.
            auth_service (AuthService): Injected authentication service.

        Returns:
            ResponseSchema[MfaRecoveryCodesResponse]: New plain-text recovery codes.
        """
        codes = await auth_service.regenerateRecoveryCodes(user=auth.user, code=payload.code)
        return ResponseSchema(data=MfaRecoveryCodesResponse(recovery_codes=codes))
