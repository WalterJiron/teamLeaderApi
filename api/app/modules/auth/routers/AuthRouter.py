from fastapi import APIRouter
from app.modules.auth.routers.MfaRouter import MfaRouter
from app.modules.auth.routers.OrganizationRouter import OrganizationRouter
from app.modules.auth.routers.PasswordRouter import PasswordRouter
from app.modules.auth.routers.ProfileRouter import ProfileRouter
from app.modules.auth.routers.RecoveryRouter import RecoveryRouter
from app.modules.auth.routers.SessionRouter import SessionRouter


class AuthRouter:

    def __init__(self) -> None:
        """Configures the public and self-service authentication router by aggregating modular sub-routers."""
        self.router = APIRouter(prefix="/auth", tags=["Authentication"])

        self.session_router = SessionRouter()
        self.password_router = PasswordRouter()
        self.recovery_router = RecoveryRouter()
        self.profile_router = ProfileRouter()
        self.mfa_router = MfaRouter()
        self.organization_router = OrganizationRouter()

        self._registerSubRouters()
        self._bindEndpoints()

    def _registerSubRouters(self) -> None:
        """Mounts specialized authentication sub-routers onto the main auth prefix."""
        self.router.include_router(self.session_router.router)
        self.router.include_router(self.password_router.router)
        self.router.include_router(self.recovery_router.router)
        self.router.include_router(self.profile_router.router)
        self.router.include_router(self.mfa_router.router)
        self.router.include_router(self.organization_router.router)

    def _bindEndpoints(self) -> None:
        """Exposes sub-router endpoint handlers directly for programmatic and test access."""
        # Session & token lifecycle
        self.register = self.session_router.register
        self.login = self.session_router.login
        self.completeMfaLogin = self.session_router.completeMfaLogin
        self.refresh = self.session_router.refresh
        self.logout = self.session_router.logout

        # Password reset & email verification
        self.requestPasswordReset = self.password_router.requestPasswordReset
        self.confirmPasswordReset = self.password_router.confirmPasswordReset
        self.resendEmailVerification = self.password_router.resendEmailVerification
        self.confirmEmailVerification = self.password_router.confirmEmailVerification
        self.requestEmailChange = self.password_router.requestEmailChange
        self.confirmEmailChange = self.password_router.confirmEmailChange

        # Recovery & emergency resets
        self.requestRecoveryEmail = self.recovery_router.requestRecoveryEmail
        self.confirmRecoveryEmail = self.recovery_router.confirmRecoveryEmail
        self.resetWithRecoveryCode = self.recovery_router.resetWithRecoveryCode
        self.requestAccountRecovery = self.recovery_router.requestAccountRecovery
        self.confirmAccountRecovery = self.recovery_router.confirmAccountRecovery

        # Profile, credentials & session management
        self.getMe = self.profile_router.getMe
        self.changePassword = self.profile_router.changePassword
        self.logoutAll = self.profile_router.logoutAll
        self.listSessions = self.profile_router.listSessions
        self.revokeSession = self.profile_router.revokeSession

        # Multi-factor authentication
        self.setupMfa = self.mfa_router.setupMfa
        self.confirmMfa = self.mfa_router.confirmMfa
        self.disableMfa = self.mfa_router.disableMfa
        self.regenerateRecoveryCodes = self.mfa_router.regenerateRecoveryCodes

        # Organization invitations & recovery reviews
        self.createInvitation = self.organization_router.createInvitation
        self.listInvitations = self.organization_router.listInvitations
        self.cancelInvitation = self.organization_router.cancelInvitation
        self.listRecoveryRequests = self.organization_router.listRecoveryRequests
        self.reviewRecoveryRequest = self.organization_router.reviewRecoveryRequest
