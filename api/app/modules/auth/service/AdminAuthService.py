from datetime import datetime, timezone
from app.common.exceptions.AppExceptions import BadRequestException, ForbiddenException
from app.modules.auth.AuditRepository import AuditRepository
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.MfaRepository import MfaRepository
from app.modules.auth.SessionRepository import SessionRepository
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.AuditSchema import AuditLogResponse
from app.modules.auth.schemas.AuthSchema import UserProfileResponse
from app.modules.auth.schemas.SessionSchema import SessionResponse
from app.modules.auth.service.AuditService import AuditService
from app.modules.auth.service.AuthService import AuthService
from app.modules.auth.service.SessionService import SessionService


class AdminAuthService:

    def __init__(
        self,
        auth_repository: AuthRepository,
        session_repository: SessionRepository,
        mfa_repository: MfaRepository,
        audit_repository: AuditRepository,
        audit_service: AuditService,
        session_service: SessionService,
        auth_service: AuthService,
    ) -> None:
        """Initializes the administrative authentication service.

        Args:
            auth_repository (AuthRepository): User persistence repository.
            session_repository (SessionRepository): Session persistence repository.
            mfa_repository (MfaRepository): MFA settings repository.
            audit_repository (AuditRepository): Audit log query repository.
            audit_service (AuditService): Security audit service.
            session_service (SessionService): Session revocation service.
            auth_service (AuthService): Core authentication service.
        """
        self.auth_repository = auth_repository
        self.session_repository = session_repository
        self.mfa_repository = mfa_repository
        self.audit_repository = audit_repository
        self.audit_service = audit_service
        self.session_service = session_service
        self.auth_service = auth_service

    @staticmethod
    def _requireAdmin(admin: UserTableDto) -> None:
        """Ensures the caller has the administrator role.

        Args:
            admin (UserTableDto): Authenticated caller.

        Raises:
            ForbiddenException: If the caller is not an administrator.
        """
        if admin.role != "ADMIN":
            raise ForbiddenException(detail="Administrator privileges are required.")

    async def listUsers(
        self,
        admin: UserTableDto,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[UserProfileResponse], int]:
        """Lists users in the administrator's organization.

        Args:
            admin (UserTableDto): Authenticated administrator.
            page (int): One-based page number.
            limit (int): Page size.
            search (str | None, optional): Name or email fragment. Defaults to None.

        Returns:
            tuple[list[UserProfileResponse], int]: Users and total count.
        """
        self._requireAdmin(admin)
        offset = max(page - 1, 0) * limit
        users = await self.auth_repository.listUsers(
            organization_id=admin.organization_id,
            offset=offset,
            limit=limit,
            search=search,
        )
        total = await self.auth_repository.countUsers(
            organization_id=admin.organization_id,
            search=search,
        )
        return [UserProfileResponse.model_validate(user) for user in users], total

    async def _getScopedUser(self, admin: UserTableDto, user_id: int) -> UserTableDto:
        """Fetches a user and enforces organization scoping.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.

        Returns:
            UserTableDto: Target user.

        Raises:
            BadRequestException: If the user does not exist in the organization.
        """
        user = await self.auth_repository.getById(user_id=user_id)
        if user is None or user.organization_id != admin.organization_id:
            raise BadRequestException(detail="User not found.")
        return user

    async def getUser(self, admin: UserTableDto, user_id: int) -> UserProfileResponse:
        """Returns a scoped user profile.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.

        Returns:
            UserProfileResponse: Target user profile.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        return UserProfileResponse.model_validate(user)

    async def unlockUser(self, admin: UserTableDto, user_id: int) -> None:
        """Clears failed login counters and any lockout for a user.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="ADMIN_USER_UNLOCKED",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="WARN",
        )

    async def setUserActive(self, admin: UserTableDto, user_id: int, is_active: bool) -> None:
        """Activates or deactivates a user account.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.
            is_active (bool): Desired account state.

        Raises:
            BadRequestException: If an administrator tries to deactivate their own account.
        """
        self._requireAdmin(admin)
        if admin.user_id == user_id and not is_active:
            raise BadRequestException(detail="Administrators cannot deactivate their own account.")
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        user.is_active = is_active
        if not is_active:
            await self.session_service.revokeAll(user_id=user.user_id, reason="ACCOUNT_DISABLED")
            user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="ADMIN_USER_ACTIVATED" if is_active else "ADMIN_USER_DEACTIVATED",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="WARN",
        )

    async def forcePasswordReset(self, admin: UserTableDto, user_id: int) -> None:
        """Sends a reset link and requires the user to choose a new password.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        user.must_change_password = True
        await self.auth_service.requestPasswordReset(email=user.email)
        await self.audit_service.record(
            event_type="ADMIN_PASSWORD_RESET_FORCED",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="WARN",
        )

    async def revokeUserSessions(self, admin: UserTableDto, user_id: int) -> None:
        """Revokes every active session for a user.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        await self.session_service.revokeAll(user_id=user.user_id, reason="ADMIN_REVOKED")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="ADMIN_SESSIONS_REVOKED",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="WARN",
        )

    async def resetUserMfa(self, admin: UserTableDto, user_id: int) -> None:
        """Removes MFA settings and recovery codes for a user.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        await self.mfa_repository.deleteSetting(user_id=user.user_id)
        await self.mfa_repository.deleteRecoveryCodes(user_id=user.user_id)
        user.mfa_enabled = False
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="ADMIN_MFA_RESET",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="CRITICAL",
        )

    async def listUserSessions(self, admin: UserTableDto, user_id: int) -> list[SessionResponse]:
        """Lists active sessions for a scoped user.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.

        Returns:
            list[SessionResponse]: Active sessions newest first.
        """
        self._requireAdmin(admin)
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        sessions = await self.session_repository.listActiveForUser(user_id=user.user_id)
        return [
            SessionResponse(
                session_id=item.session_id,
                ip=item.ip,
                user_agent=item.user_agent,
                issued_at=item.issued_at,
                expires_at=item.expires_at,
                last_used_at=item.last_used_at,
            )
            for item in sessions
        ]

    async def listAuditLogs(
        self,
        admin: UserTableDto,
        page: int,
        limit: int,
        event_type: str | None = None,
    ) -> tuple[list[AuditLogResponse], int]:
        """Lists audit events for the administrator's organization.

        Args:
            admin (UserTableDto): Authenticated administrator.
            page (int): One-based page number.
            limit (int): Page size.
            event_type (str | None, optional): Optional event type filter. Defaults to None.

        Returns:
            tuple[list[AuditLogResponse], int]: Audit entries and total count.
        """
        self._requireAdmin(admin)
        offset = max(page - 1, 0) * limit
        logs = await self.audit_repository.listLogs(
            organization_id=admin.organization_id,
            offset=offset,
            limit=limit,
            event_type=event_type,
        )
        total = await self.audit_repository.countLogs(
            organization_id=admin.organization_id,
            event_type=event_type,
        )
        return [
            AuditLogResponse(
                audit_id=item.audit_id,
                organization_id=item.organization_id,
                actor_user_id=item.actor_user_id,
                target_user_id=item.target_user_id,
                event_type=item.event_type,
                severity=item.severity,
                ip=item.ip,
                user_agent=item.user_agent,
                request_id=item.request_id,
                metadata_json=item.metadata_json,
                created_at=item.created_at,
                entry_hash=item.entry_hash,
            )
            for item in logs
        ], total

    async def softDeleteUser(self, admin: UserTableDto, user_id: int) -> None:
        """Soft-deletes a user account and revokes its sessions.

        Args:
            admin (UserTableDto): Authenticated administrator.
            user_id (int): Target user identifier.

        Raises:
            BadRequestException: If an administrator tries to delete their own account.
        """
        self._requireAdmin(admin)
        if admin.user_id == user_id:
            raise BadRequestException(detail="Administrators cannot delete their own account.")
        user = await self._getScopedUser(admin=admin, user_id=user_id)
        now = datetime.now(timezone.utc)
        user.deleted_at = now
        user.deleted_by = admin.user_id
        user.is_active = False
        await self.session_service.revokeAll(user_id=user.user_id, reason="ACCOUNT_DELETED")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="ADMIN_USER_DELETED",
            actor_user_id=admin.user_id,
            target_user_id=user.user_id,
            organization_id=admin.organization_id,
            severity="CRITICAL",
        )
