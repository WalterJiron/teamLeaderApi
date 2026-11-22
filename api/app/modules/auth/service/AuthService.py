import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from app.common.exceptions.AppExceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    TooManyRequestsException,
    UnauthorizedException,
)
from app.core.AppConfig import AppConfig
from app.core.RateLimiter import RateLimiter
from app.core.RequestContext import getClientIp, getUserAgent
from app.modules.auth.AuthRepository import AuthRepository
from app.modules.auth.OutboxRepository import OutboxRepository
from app.modules.auth.SessionRepository import SessionRepository
from app.modules.auth.TokenRepository import TokenRepository
from app.modules.auth.dto.AuthTokenTableDto import AuthTokenTableDto
from app.modules.auth.dto.LoginAttemptTableDto import LoginAttemptTableDto
from app.modules.auth.dto.OrganizationTableDto import OrganizationTableDto
from app.modules.auth.dto.UserEmailTableDto import UserEmailTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.schemas.AuthSchema import (
    EmailChangeRequestSchema,
    LoginRequestSchema,
    LoginResponseSchema,
    PasswordChangeSchema,
    RecoveryEmailRequestSchema,
    RegisterUserSchema,
    TokenPairResponse,
    UserProfileResponse,
)
from app.modules.auth.schemas.MfaSchema import MfaDisableSchema, MfaSetupResponse
from app.modules.auth.schemas.SessionSchema import SessionResponse
from app.modules.auth.service.AuditService import AuditService
from app.modules.auth.service.EmailService import EmailService
from app.modules.auth.service.MfaService import MfaService
from app.modules.auth.service.PasswordService import PasswordService
from app.modules.auth.service.SessionService import SessionService
from app.modules.auth.utils.PasswordHelper import PasswordHelper
from app.modules.auth.utils.TokenHelper import TokenHelper


class AuthService:

    PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"
    PURPOSE_EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PURPOSE_EMAIL_CHANGE = "EMAIL_CHANGE"
    PURPOSE_RECOVERY_EMAIL = "RECOVERY_EMAIL_VERIFICATION"
    PURPOSE_MFA_CHALLENGE = "MFA_CHALLENGE"
    PURPOSE_ACCOUNT_RECOVERY = "ACCOUNT_RECOVERY"

    def __init__(
        self,
        auth_repository: AuthRepository,
        session_repository: SessionRepository,
        token_repository: TokenRepository,
        outbox_repository: OutboxRepository,
        password_service: PasswordService,
        session_service: SessionService,
        mfa_service: MfaService,
        audit_service: AuditService,
    ) -> None:
        """Initializes the authentication service with its collaborators.

        Args:
            auth_repository (AuthRepository): User, email, organization, and login attempt repository.
            session_repository (SessionRepository): Refresh session repository.
            token_repository (TokenRepository): Single-use token repository.
            outbox_repository (OutboxRepository): Transactional email outbox repository.
            password_service (PasswordService): Password policy and history service.
            session_service (SessionService): Session issuance and rotation service.
            mfa_service (MfaService): Multi-factor authentication service.
            audit_service (AuditService): Security audit service.
        """
        self.auth_repository = auth_repository
        self.session_repository = session_repository
        self.token_repository = token_repository
        self.outbox_repository = outbox_repository
        self.password_service = password_service
        self.session_service = session_service
        self.mfa_service = mfa_service
        self.audit_service = audit_service

    @staticmethod
    def _now() -> datetime:
        """Returns the current timezone-aware UTC timestamp.

        Returns:
            datetime: Current UTC datetime.
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def _slugify(value: str) -> str:
        """Converts an organization name into a URL-safe slug.

        Args:
            value (str): Raw organization name.

        Returns:
            str: Lowercase hyphenated slug.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:60] or "organization"

    @staticmethod
    def _profile(user: UserTableDto) -> UserProfileResponse:
        """Serializes a user entity into the public profile contract.

        Args:
            user (UserTableDto): User entity.

        Returns:
            UserProfileResponse: Public user profile.
        """
        return UserProfileResponse.model_validate(user)

    @staticmethod
    def _pair(
        user: UserTableDto,
        access_token: str,
        refresh_token: str,
    ) -> TokenPairResponse:
        """Builds a token pair response.

        Args:
            user (UserTableDto): Authenticated user entity.
            access_token (str): Signed access JWT.
            refresh_token (str): Opaque refresh token.

        Returns:
            TokenPairResponse: Token pair and user profile.
        """
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=AuthService._profile(user),
        )

    async def _commit(self) -> None:
        """Commits security-relevant state before raising a controlled error."""
        await self.auth_repository.db_session.commit()

    async def _issueTokens(
        self,
        user: UserTableDto,
        mfa_verified: bool,
        ip: str | None,
        user_agent: str | None,
    ) -> TokenPairResponse:
        """Creates a new session and signs its access token.

        Args:
            user (UserTableDto): Authenticated user entity.
            mfa_verified (bool): Whether MFA was completed for the session.
            ip (str | None): Client IP address.
            user_agent (str | None): Client User-Agent.

        Returns:
            TokenPairResponse: Token pair and user profile.
        """
        _, refresh_token, access_token = await self.session_service.createSession(
            user=user,
            mfa_verified=mfa_verified,
            ip=ip,
            user_agent=user_agent,
        )
        return self._pair(user=user, access_token=access_token, refresh_token=refresh_token)

    async def _createToken(
        self,
        user: UserTableDto,
        purpose: str,
        expires_delta: timedelta,
        metadata: dict | None = None,
    ) -> str:
        """Creates a hashed single-use token and returns its raw value.

        Args:
            user (UserTableDto): User the token belongs to.
            purpose (str): Token purpose code.
            expires_delta (timedelta): Token lifetime.
            metadata (dict | None, optional): Non-secret token context. Defaults to None.

        Returns:
            str: Raw token to deliver out of band.
        """
        raw_token = TokenHelper.generateToken(48)
        token = AuthTokenTableDto(
            token_id=TokenHelper.newId(),
            user_id=user.user_id,
            organization_id=user.organization_id,
            purpose=purpose,
            token_hash=TokenHelper.hashToken(raw_token),
            expires_at=self._now() + expires_delta,
            created_ip=getClientIp(),
            created_user_agent=getUserAgent(),
            metadata_json=metadata,
        )
        await self.token_repository.addToken(token=token)
        return raw_token

    async def _getValidToken(self, raw_token: str, purpose: str) -> AuthTokenTableDto:
        """Validates a single-use token by hash, purpose, expiry, and state.

        Args:
            raw_token (str): Raw token supplied by the client.
            purpose (str): Expected token purpose.

        Returns:
            AuthTokenTableDto: Valid token entity.

        Raises:
            BadRequestException: If the token is unknown, consumed, revoked, or expired.
        """
        token = await self.token_repository.getByHashAndPurpose(
            token_hash=TokenHelper.hashToken(raw_token),
            purpose=purpose,
        )
        if (
            token is None
            or token.used_at is not None
            or token.revoked_at is not None
            or token.expires_at <= self._now()
        ):
            raise BadRequestException(detail="Token is invalid or has expired.")
        return token

    async def _enqueue(
        self,
        template: str,
        recipient: str,
        full_name: str,
        action_url: str,
        expires_in: str,
        organization_id: int | None = None,
        extra: str = "",
    ) -> None:
        """Queues a transactional email through the outbox.

        Args:
            template (str): Email template identifier.
            recipient (str): Destination address.
            full_name (str): Recipient display name.
            action_url (str): Call-to-action URL, empty when not applicable.
            expires_in (str): Human-readable expiry description.
            organization_id (int | None, optional): Tenant identifier. Defaults to None.
            extra (str, optional): Additional plain-text context. Defaults to "".
        """
        await EmailService.enqueueEmail(
            outbox_repository=self.outbox_repository,
            recipient=recipient,
            template=template,
            organization_id=organization_id,
            payload={
                "full_name": full_name,
                "action_url": action_url,
                "expires_in": expires_in,
                "extra": extra,
            },
        )

    @staticmethod
    def _actionUrl(base_url: str, token: str) -> str:
        """Appends an encoded token to a configured frontend URL.

        Args:
            base_url (str): Frontend action URL.
            token (str): Raw single-use token.

        Returns:
            str: Complete action URL.
        """
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}token={quote(token)}"

    async def _recordLoginAttempt(
        self,
        email: str,
        user_id: int | None,
        success: bool,
        failure_reason: str | None,
    ) -> None:
        """Persists an authentication attempt for security monitoring.

        Args:
            email (str): Attempted email address.
            user_id (int | None): Resolved user identifier.
            success (bool): Whether the attempt succeeded.
            failure_reason (str | None): Failure code.
        """
        await self.auth_repository.addLoginAttempt(
            LoginAttemptTableDto(
                email_hash=TokenHelper.hashEmail(email),
                user_id=user_id,
                ip=getClientIp(),
                user_agent=getUserAgent(),
                success=success,
                failure_reason=failure_reason,
            )
        )

    async def registerUser(self, payload: RegisterUserSchema) -> TokenPairResponse:
        """Registers a user through an invitation or open registration and issues tokens.

        Args:
            payload (RegisterUserSchema): Registration payload.

        Returns:
            TokenPairResponse: Initial token pair and user profile.

        Raises:
            BadRequestException: If the invitation is invalid, the email is taken, or the password is weak.
            ConflictException: If the email is already registered.
            ForbiddenException: If open registration is disabled and no invitation is supplied.
        """
        email = AuthRepository.normalizeEmail(payload.email)
        invitation = None
        organization_id = payload.organization_id
        role = "TEAM_LEADER"

        if payload.invitation_token:
            invitation = await self.auth_repository.getInvitationByTokenHash(
                token_hash=TokenHelper.hashToken(payload.invitation_token)
            )
            if (
                invitation is None
                or invitation.accepted_at is not None
                or invitation.expires_at <= self._now()
            ):
                raise BadRequestException(detail="Invitation is invalid or has expired.")
            if AuthRepository.normalizeEmail(invitation.email) != email:
                raise BadRequestException(detail="Invitation does not match the supplied email.")
            organization_id = invitation.organization_id
            role = invitation.role
        else:
            if not AppConfig.ALLOW_OPEN_REGISTRATION:
                raise ForbiddenException(detail="Open registration is disabled. An invitation is required.")
            if organization_id is not None:
                organization = await self.auth_repository.getOrganization(organization_id=organization_id)
                if organization is None:
                    raise BadRequestException(detail="Organization does not exist.")
            else:
                organization = await self._createPersonalOrganization(payload.full_name)
                organization_id = organization.organization_id
                role = "ADMIN"

        if await self.auth_repository.emailExists(email=email):
            raise ConflictException(detail="Email address is already registered.")

        await self.password_service.validatePolicy(password=payload.password, email=email)
        hashed_password = PasswordHelper.hashPassword(payload.password)

        user = UserTableDto(
            organization_id=organization_id,
            full_name=payload.full_name.strip(),
            email=email,
            hashed_password=hashed_password,
            password_algorithm=PasswordHelper.getAlgorithm(hashed_password),
            password_changed_at=self._now(),
            role=role,
            is_active=True,
        )
        user = await self.auth_repository.addUser(user=user)
        await self.auth_repository.addUserEmail(
            UserEmailTableDto(
                user_id=user.user_id,
                email=email,
                is_primary=True,
                verified_at=None,
            )
        )

        if payload.recovery_email:
            recovery_email = AuthRepository.normalizeEmail(payload.recovery_email)
            if recovery_email != email and not await self.auth_repository.emailExists(email=recovery_email):
                await self.auth_repository.addUserEmail(
                    UserEmailTableDto(
                        user_id=user.user_id,
                        email=recovery_email,
                        is_recovery=True,
                        verified_at=None,
                    )
                )

        if invitation is not None:
            invitation.accepted_at = self._now()
            await self.auth_repository.db_session.flush()

        await self._sendVerificationEmail(user=user)
        await self.audit_service.record(
            event_type="USER_REGISTERED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"role": role, "invitation": invitation is not None},
        )
        return await self._issueTokens(
            user=user,
            mfa_verified=False,
            ip=getClientIp(),
            user_agent=getUserAgent(),
        )

    async def _createPersonalOrganization(self, full_name: str) -> OrganizationTableDto:
        """Creates a personal organization for a self-registered user.

        Args:
            full_name (str): User display name.

        Returns:
            OrganizationTableDto: Persisted organization.
        """
        base_slug = self._slugify(f"{full_name}-team")
        slug = base_slug
        for _ in range(5):
            existing = await self.auth_repository.getOrganizationBySlug(slug=slug)
            if existing is None:
                break
            slug = f"{base_slug}-{secrets.token_hex(3)}"
        return await self.auth_repository.addOrganization(
            OrganizationTableDto(
                name=f"{full_name.strip()}'s Team",
                slug=slug,
                status="ACTIVE",
            )
        )

    async def loginUser(self, payload: LoginRequestSchema) -> LoginResponseSchema:
        """Authenticates credentials and either issues tokens or starts an MFA challenge.

        Args:
            payload (LoginRequestSchema): Email and password credentials.

        Returns:
            LoginResponseSchema: Token pair or MFA challenge token.

        Raises:
            UnauthorizedException: If the credentials are invalid.
            ForbiddenException: If the account is inactive or email verification is required.
            TooManyRequestsException: If the account is temporarily locked.
        """
        email = AuthRepository.normalizeEmail(payload.email)
        ip = getClientIp() or "unknown"
        email_hash = TokenHelper.hashEmail(email)
        await RateLimiter.enforce(key=f"rl:login:ip:{ip}", limit=20, window_seconds=60)
        await RateLimiter.enforce(key=f"rl:login:email:{email_hash}", limit=10, window_seconds=60)

        user = await self.auth_repository.getByEmail(email=email, for_update=True)
        if user is None:
            await self._recordLoginAttempt(email=email, user_id=None, success=False, failure_reason="UNKNOWN_USER")
            await self.audit_service.record(
                event_type="LOGIN_FAILED",
                severity="WARN",
                metadata={"email_hash": email_hash, "reason": "UNKNOWN_USER"},
            )
            await self._commit()
            raise UnauthorizedException(detail="Invalid email or password.")

        now = self._now()
        if user.locked_until is not None and user.locked_until > now:
            retry_after = int((user.locked_until - now).total_seconds()) + 1
            await self.audit_service.record(
                event_type="LOGIN_BLOCKED",
                target_user_id=user.user_id,
                organization_id=user.organization_id,
                severity="WARN",
            )
            await self._commit()
            raise TooManyRequestsException(
                detail="Account is temporarily locked. Try again later.",
                retry_after=retry_after,
            )

        if not PasswordHelper.verifyPassword(payload.password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= AppConfig.LOGIN_MAX_ATTEMPTS:
                user.failed_login_attempts = 0
                user.locked_until = now + timedelta(minutes=AppConfig.LOGIN_LOCKOUT_MINUTES)
                await self._enqueue(
                    template="ACCOUNT_LOCKED_NOTICE",
                    recipient=user.email,
                    full_name=user.full_name,
                    action_url="",
                    expires_in=f"{AppConfig.LOGIN_LOCKOUT_MINUTES} minutes",
                    organization_id=user.organization_id,
                )
                await self.audit_service.record(
                    event_type="ACCOUNT_LOCKED",
                    target_user_id=user.user_id,
                    organization_id=user.organization_id,
                    severity="WARN",
                )
            await self._recordLoginAttempt(
                email=email,
                user_id=user.user_id,
                success=False,
                failure_reason="INVALID_PASSWORD",
            )
            await self.audit_service.record(
                event_type="LOGIN_FAILED",
                target_user_id=user.user_id,
                organization_id=user.organization_id,
                severity="WARN",
                metadata={"reason": "INVALID_PASSWORD"},
            )
            await self._commit()
            raise UnauthorizedException(detail="Invalid email or password.")

        if not user.is_active:
            raise ForbiddenException(detail="User account is inactive.")
        if AppConfig.REQUIRE_EMAIL_VERIFICATION_FOR_LOGIN and user.email_verified_at is None:
            raise ForbiddenException(detail="Email address must be verified before signing in.")

        if PasswordHelper.needsRehash(user.hashed_password):
            rehashed = PasswordHelper.hashPassword(payload.password)
            user.hashed_password = rehashed
            user.password_algorithm = PasswordHelper.getAlgorithm(rehashed)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        await self._recordLoginAttempt(
            email=email,
            user_id=user.user_id,
            success=True,
            failure_reason=None,
        )

        if user.mfa_enabled:
            await self.token_repository.revokeActiveForUserPurpose(
                user_id=user.user_id,
                purpose=self.PURPOSE_MFA_CHALLENGE,
            )
            mfa_token = await self._createToken(
                user=user,
                purpose=self.PURPOSE_MFA_CHALLENGE,
                expires_delta=timedelta(minutes=AppConfig.MFA_CHALLENGE_EXPIRE_MINUTES),
            )
            await self.audit_service.record(
                event_type="MFA_CHALLENGE_ISSUED",
                actor_user_id=user.user_id,
                target_user_id=user.user_id,
                organization_id=user.organization_id,
            )
            return LoginResponseSchema(mfa_required=True, mfa_token=mfa_token)

        tokens = await self._issueTokens(
            user=user,
            mfa_verified=False,
            ip=getClientIp(),
            user_agent=getUserAgent(),
        )
        await self.audit_service.record(
            event_type="LOGIN_SUCCEEDED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
        )
        return LoginResponseSchema(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            user=tokens.user,
        )

    async def completeMfaLogin(self, mfa_token: str, code: str) -> TokenPairResponse:
        """Completes a pending MFA challenge and issues a token pair.

        Args:
            mfa_token (str): Raw MFA challenge token returned by login.
            code (str): TOTP or recovery code.

        Returns:
            TokenPairResponse: Token pair and user profile.

        Raises:
            UnauthorizedException: If the challenge or code is invalid.
        """
        token = await self.token_repository.getByHashAndPurpose(
            token_hash=TokenHelper.hashToken(mfa_token),
            purpose=self.PURPOSE_MFA_CHALLENGE,
        )
        if (
            token is None
            or token.used_at is not None
            or token.revoked_at is not None
            or token.expires_at <= self._now()
        ):
            raise UnauthorizedException(detail="MFA challenge is invalid or has expired.")

        user = await self.auth_repository.getById(user_id=token.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException(detail="User account not found or inactive.")

        if not await self.mfa_service.verify(user=user, code=code):
            await self.audit_service.record(
                event_type="MFA_FAILED",
                target_user_id=user.user_id,
                organization_id=user.organization_id,
                severity="WARN",
            )
            await self._commit()
            raise UnauthorizedException(detail="Invalid verification code.")

        await self.token_repository.markUsed(token=token)
        user.last_login_at = self._now()
        user.failed_login_attempts = 0
        tokens = await self._issueTokens(
            user=user,
            mfa_verified=True,
            ip=getClientIp(),
            user_agent=getUserAgent(),
        )
        await self.audit_service.record(
            event_type="MFA_SUCCEEDED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="LOGIN_SUCCEEDED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"mfa": True},
        )
        return tokens

    async def refreshAccessToken(self, refresh_token: str) -> TokenPairResponse:
        """Rotates a refresh token and detects replay of revoked tokens.

        Args:
            refresh_token (str): Opaque refresh token.

        Returns:
            TokenPairResponse: Rotated token pair.

        Raises:
            UnauthorizedException: If the token is unknown, expired, revoked, or replayed.
        """
        session = await self.session_repository.getByRefreshHash(
            refresh_token_hash=TokenHelper.hashToken(refresh_token)
        )
        if session is None:
            raise UnauthorizedException(detail="Invalid refresh token.")

        if session.revoked_at is not None:
            await self.session_repository.revokeFamily(
                token_family_id=session.token_family_id,
                reason="REUSE_DETECTED",
            )
            await self.audit_service.record(
                event_type="REFRESH_TOKEN_REUSE",
                target_user_id=session.user_id,
                organization_id=session.organization_id,
                severity="CRITICAL",
                metadata={"session_id": session.session_id},
            )
            await self._commit()
            raise UnauthorizedException(detail="Refresh token has already been used.")

        if session.expires_at <= self._now():
            await self.session_service.revokeSession(session=session, reason="EXPIRED")
            await self._commit()
            raise UnauthorizedException(detail="Refresh token has expired.")

        user = await self.auth_repository.getById(user_id=session.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException(detail="User account not found or inactive.")

        new_session, new_refresh, new_access = await self.session_service.rotateSession(
            old_session=session,
            user=user,
            ip=getClientIp(),
            user_agent=getUserAgent(),
        )
        await self.audit_service.record(
            event_type="TOKEN_REFRESHED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"session_id": new_session.session_id},
        )
        return self._pair(user=user, access_token=new_access, refresh_token=new_refresh)

    async def logout(self, refresh_token: str) -> None:
        """Revokes the session associated with a refresh token.

        Args:
            refresh_token (str): Opaque refresh token.
        """
        session = await self.session_repository.getByRefreshHash(
            refresh_token_hash=TokenHelper.hashToken(refresh_token)
        )
        if session is not None and session.revoked_at is None:
            await self.session_service.revokeSession(session=session, reason="LOGOUT")
            await self.audit_service.record(
                event_type="LOGOUT",
                actor_user_id=session.user_id,
                target_user_id=session.user_id,
                organization_id=session.organization_id,
                metadata={"session_id": session.session_id},
            )

    async def logoutAll(self, user: UserTableDto, current_session_id: str | None) -> None:
        """Revokes every session and invalidates outstanding access tokens.

        Args:
            user (UserTableDto): Authenticated user entity.
            current_session_id (str | None): Current session identifier.
        """
        await self.session_service.revokeAll(user_id=user.user_id, reason="LOGOUT_ALL")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self.audit_service.record(
            event_type="LOGOUT_ALL",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"session_id": current_session_id},
        )

    def getProfile(self, user: UserTableDto) -> UserProfileResponse:
        """Returns the public profile for an authenticated user.

        Args:
            user (UserTableDto): Authenticated user entity.

        Returns:
            UserProfileResponse: Public user profile.
        """
        return self._profile(user)

    async def changePassword(
        self,
        user: UserTableDto,
        payload: PasswordChangeSchema,
        current_session_id: str | None,
    ) -> None:
        """Changes a password after verifying the current password and MFA.

        Args:
            user (UserTableDto): Authenticated user entity.
            payload (PasswordChangeSchema): Current and new password plus optional MFA code.
            current_session_id (str | None): Session to preserve.

        Raises:
            BadRequestException: If the current password is wrong or the new password is weak or reused.
        """
        if not PasswordHelper.verifyPassword(payload.current_password, user.hashed_password):
            raise BadRequestException(detail="Current password is incorrect.")
        await self.mfa_service.verifyOrRaise(user=user, code=payload.mfa_code)
        await self.password_service.validatePolicy(password=payload.new_password, user=user)
        if await self.password_service.isReused(user=user, new_password=payload.new_password):
            raise BadRequestException(detail="Password was used recently. Choose a different password.")

        await self.password_service.setPassword(
            user=user,
            new_password=payload.new_password,
            reason="PASSWORD_CHANGE",
            actor_id=user.user_id,
        )
        await self.session_service.revokeAll(
            user_id=user.user_id,
            reason="PASSWORD_CHANGED",
            except_session_id=current_session_id,
        )
        await self._enqueue(
            template="PASSWORD_CHANGED_NOTICE",
            recipient=user.email,
            full_name=user.full_name,
            action_url="",
            expires_in="not applicable",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="PASSWORD_CHANGED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )

    async def requestPasswordReset(self, email: str) -> None:
        """Queues a password reset link when the account exists, without revealing existence.

        Args:
            email (str): Email address to reset.
        """
        normalized = AuthRepository.normalizeEmail(email)
        await RateLimiter.enforce(
            key=f"rl:password-reset:ip:{getClientIp() or 'unknown'}",
            limit=5,
            window_seconds=3600,
        )
        user = await self.auth_repository.getByAnyEmail(email=normalized)
        if user is None:
            await self.audit_service.record(
                event_type="PASSWORD_RESET_REQUESTED",
                severity="WARN",
                metadata={"email_hash": TokenHelper.hashEmail(normalized), "found": False},
            )
            return

        await self.token_repository.revokeActiveForUserPurpose(
            user_id=user.user_id,
            purpose=self.PURPOSE_PASSWORD_RESET,
        )
        raw_token = await self._createToken(
            user=user,
            purpose=self.PURPOSE_PASSWORD_RESET,
            expires_delta=timedelta(minutes=AppConfig.PASSWORD_RESET_EXPIRE_MINUTES),
        )
        await self._enqueue(
            template="PASSWORD_RESET",
            recipient=normalized,
            full_name=user.full_name,
            action_url=self._actionUrl(AppConfig.PASSWORD_RESET_URL, raw_token),
            expires_in=f"{AppConfig.PASSWORD_RESET_EXPIRE_MINUTES} minutes",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="PASSWORD_RESET_REQUESTED",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"email_hash": TokenHelper.hashEmail(normalized), "found": True},
        )

    async def confirmPasswordReset(self, token: str, new_password: str) -> None:
        """Consumes a reset token and sets a new password.

        Args:
            token (str): Raw password reset token.
            new_password (str): New plain-text password.

        Raises:
            BadRequestException: If the token is invalid or the password is weak or reused.
        """
        token_entity = await self._getValidToken(token, self.PURPOSE_PASSWORD_RESET)
        user = await self.auth_repository.getById(user_id=token_entity.user_id)
        if user is None:
            raise BadRequestException(detail="Token is invalid or has expired.")

        await self.password_service.validatePolicy(password=new_password, user=user)
        if await self.password_service.isReused(user=user, new_password=new_password):
            raise BadRequestException(detail="Password was used recently. Choose a different password.")

        await self.password_service.setPassword(
            user=user,
            new_password=new_password,
            reason="PASSWORD_RESET",
            actor_id=user.user_id,
        )
        await self.token_repository.markUsed(token=token_entity)
        await self.session_service.revokeAll(user_id=user.user_id, reason="PASSWORD_RESET")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self._enqueue(
            template="PASSWORD_CHANGED_NOTICE",
            recipient=user.email,
            full_name=user.full_name,
            action_url="",
            expires_in="not applicable",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="PASSWORD_RESET_COMPLETED",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )

    async def sendEmailVerification(self, user: UserTableDto) -> None:
        """Queues a new primary-email verification link.

        Args:
            user (UserTableDto): Authenticated user entity.

        Raises:
            BadRequestException: If the primary email is already verified.
        """
        if user.email_verified_at is not None:
            raise BadRequestException(detail="Email address is already verified.")
        await self.token_repository.revokeActiveForUserPurpose(
            user_id=user.user_id,
            purpose=self.PURPOSE_EMAIL_VERIFICATION,
        )
        await self._sendVerificationEmail(user=user)

    async def _sendVerificationEmail(self, user: UserTableDto) -> None:
        """Creates and queues a primary-email verification message.

        Args:
            user (UserTableDto): User entity.
        """
        raw_token = await self._createToken(
            user=user,
            purpose=self.PURPOSE_EMAIL_VERIFICATION,
            expires_delta=timedelta(hours=AppConfig.EMAIL_VERIFICATION_EXPIRE_HOURS),
        )
        await self._enqueue(
            template="EMAIL_VERIFICATION",
            recipient=user.email,
            full_name=user.full_name,
            action_url=self._actionUrl(AppConfig.EMAIL_VERIFICATION_URL, raw_token),
            expires_in=f"{AppConfig.EMAIL_VERIFICATION_EXPIRE_HOURS} hours",
            organization_id=user.organization_id,
        )

    async def confirmEmailVerification(self, token: str) -> None:
        """Marks a primary email address as verified.

        Args:
            token (str): Raw verification token.

        Raises:
            BadRequestException: If the token is invalid or expired.
        """
        token_entity = await self._getValidToken(token, self.PURPOSE_EMAIL_VERIFICATION)
        user = await self.auth_repository.getById(user_id=token_entity.user_id)
        if user is None:
            raise BadRequestException(detail="Token is invalid or has expired.")

        now = self._now()
        user.email_verified_at = now
        primary = await self.auth_repository.getPrimaryEmail(user_id=user.user_id)
        if primary is not None:
            primary.verified_at = now
        await self.token_repository.markUsed(token=token_entity)
        await self.audit_service.record(
            event_type="EMAIL_VERIFIED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
        )

    async def requestEmailChange(self, user: UserTableDto, payload: EmailChangeRequestSchema) -> None:
        """Queues confirmation for a primary email change.

        Args:
            user (UserTableDto): Authenticated user entity.
            payload (EmailChangeRequestSchema): New email, password, and optional MFA code.

        Raises:
            BadRequestException: If the password is wrong or the email is unchanged.
            ConflictException: If the new email is already registered.
        """
        if not PasswordHelper.verifyPassword(payload.password, user.hashed_password):
            raise BadRequestException(detail="Current password is incorrect.")
        await self.mfa_service.verifyOrRaise(user=user, code=payload.mfa_code)

        new_email = AuthRepository.normalizeEmail(payload.new_email)
        if new_email == AuthRepository.normalizeEmail(user.email):
            raise BadRequestException(detail="New email address must differ from the current one.")
        if await self.auth_repository.emailExists(email=new_email):
            raise ConflictException(detail="Email address is already registered.")

        await self.token_repository.revokeActiveForUserPurpose(
            user_id=user.user_id,
            purpose=self.PURPOSE_EMAIL_CHANGE,
        )
        raw_token = await self._createToken(
            user=user,
            purpose=self.PURPOSE_EMAIL_CHANGE,
            expires_delta=timedelta(hours=AppConfig.EMAIL_CHANGE_EXPIRE_HOURS),
            metadata={"new_email": new_email},
        )
        await self._enqueue(
            template="EMAIL_CHANGE",
            recipient=new_email,
            full_name=user.full_name,
            action_url=self._actionUrl(AppConfig.EMAIL_CHANGE_URL, raw_token),
            expires_in=f"{AppConfig.EMAIL_CHANGE_EXPIRE_HOURS} hours",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="EMAIL_CHANGE_REQUESTED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
            metadata={"new_email_hash": TokenHelper.hashEmail(new_email)},
        )

    async def confirmEmailChange(self, token: str) -> UserProfileResponse:
        """Applies a confirmed primary email change.

        Args:
            token (str): Raw email change token.

        Returns:
            UserProfileResponse: Updated user profile.

        Raises:
            BadRequestException: If the token is invalid or its payload is missing.
            ConflictException: If the new email was registered in the meantime.
        """
        token_entity = await self._getValidToken(token, self.PURPOSE_EMAIL_CHANGE)
        metadata = token_entity.metadata_json or {}
        new_email = AuthRepository.normalizeEmail(str(metadata.get("new_email", "")))
        if not new_email:
            raise BadRequestException(detail="Token payload is invalid.")

        user = await self.auth_repository.getById(user_id=token_entity.user_id)
        if user is None:
            raise BadRequestException(detail="Token is invalid or has expired.")
        if await self.auth_repository.emailExists(email=new_email):
            raise ConflictException(detail="Email address is already registered.")

        old_email = user.email
        now = self._now()
        user.email = new_email
        user.email_verified_at = now
        primary = await self.auth_repository.getPrimaryEmail(user_id=user.user_id)
        if primary is not None:
            primary.email = new_email
            primary.verified_at = now
        await self.token_repository.markUsed(token=token_entity)
        await self.session_service.revokeAll(user_id=user.user_id, reason="EMAIL_CHANGED")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self._enqueue(
            template="EMAIL_CHANGED_NOTICE",
            recipient=old_email,
            full_name=user.full_name,
            action_url="",
            expires_in="not applicable",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="EMAIL_CHANGED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )
        return self._profile(user=user)

    async def requestRecoveryEmail(self, user: UserTableDto, payload: RecoveryEmailRequestSchema) -> None:
        """Queues verification for a recovery email address.

        Args:
            user (UserTableDto): Authenticated user entity.
            payload (RecoveryEmailRequestSchema): Recovery email and current password.

        Raises:
            BadRequestException: If the password is wrong or the address equals the primary email.
            ConflictException: If the address belongs to another account.
        """
        if not PasswordHelper.verifyPassword(payload.password, user.hashed_password):
            raise BadRequestException(detail="Current password is incorrect.")

        recovery_email = AuthRepository.normalizeEmail(payload.recovery_email)
        if recovery_email == AuthRepository.normalizeEmail(user.email):
            raise BadRequestException(detail="Recovery email must differ from the primary email.")
        if await self.auth_repository.emailExists(email=recovery_email):
            raise ConflictException(detail="Email address is already registered.")

        existing = await self.auth_repository.getRecoveryEmail(user_id=user.user_id)
        if existing is None:
            await self.auth_repository.addUserEmail(
                UserEmailTableDto(
                    user_id=user.user_id,
                    email=recovery_email,
                    is_recovery=True,
                    verified_at=None,
                )
            )
        else:
            existing.email = recovery_email
            existing.verified_at = None
            await self.auth_repository.db_session.flush()

        await self.token_repository.revokeActiveForUserPurpose(
            user_id=user.user_id,
            purpose=self.PURPOSE_RECOVERY_EMAIL,
        )
        raw_token = await self._createToken(
            user=user,
            purpose=self.PURPOSE_RECOVERY_EMAIL,
            expires_delta=timedelta(hours=AppConfig.RECOVERY_EMAIL_EXPIRE_HOURS),
            metadata={"recovery_email": recovery_email},
        )
        await self._enqueue(
            template="RECOVERY_EMAIL_VERIFICATION",
            recipient=recovery_email,
            full_name=user.full_name,
            action_url=self._actionUrl(AppConfig.RECOVERY_EMAIL_URL, raw_token),
            expires_in=f"{AppConfig.RECOVERY_EMAIL_EXPIRE_HOURS} hours",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="RECOVERY_EMAIL_REQUESTED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"recovery_email_hash": TokenHelper.hashEmail(recovery_email)},
        )

    async def confirmRecoveryEmail(self, token: str) -> None:
        """Marks a recovery email address as verified.

        Args:
            token (str): Raw recovery email verification token.

        Raises:
            BadRequestException: If the token is invalid or the address no longer matches.
        """
        token_entity = await self._getValidToken(token, self.PURPOSE_RECOVERY_EMAIL)
        metadata = token_entity.metadata_json or {}
        recovery_email = AuthRepository.normalizeEmail(str(metadata.get("recovery_email", "")))
        recovery = await self.auth_repository.getRecoveryEmail(user_id=token_entity.user_id)
        if recovery is None or AuthRepository.normalizeEmail(recovery.email) != recovery_email:
            raise BadRequestException(detail="Token payload is invalid.")

        recovery.verified_at = self._now()
        await self.token_repository.markUsed(token=token_entity)
        await self.audit_service.record(
            event_type="RECOVERY_EMAIL_VERIFIED",
            actor_user_id=token_entity.user_id,
            target_user_id=token_entity.user_id,
            organization_id=token_entity.organization_id,
        )

    async def resetPasswordWithRecoveryCode(self, email: str, recovery_code: str, new_password: str) -> None:
        """Resets a password using an MFA recovery code sent to a known email address.

        Args:
            email (str): Primary or recovery email address.
            recovery_code (str): One-time MFA recovery code.
            new_password (str): New plain-text password.

        Raises:
            UnauthorizedException: If the account or recovery code is invalid.
            BadRequestException: If the password is weak or reused.
        """
        normalized = AuthRepository.normalizeEmail(email)
        await RateLimiter.enforce(
            key=f"rl:recovery-code:ip:{getClientIp() or 'unknown'}",
            limit=10,
            window_seconds=3600,
        )
        user = await self.auth_repository.getByAnyEmail(email=normalized)
        if user is None or not user.mfa_enabled:
            await self.audit_service.record(
                event_type="RECOVERY_CODE_FAILED",
                severity="WARN",
                metadata={"email_hash": TokenHelper.hashEmail(normalized)},
            )
            await self._commit()
            raise UnauthorizedException(detail="Invalid recovery code.")

        if not await self.mfa_service.verify(user=user, code=recovery_code):
            await self.audit_service.record(
                event_type="RECOVERY_CODE_FAILED",
                target_user_id=user.user_id,
                organization_id=user.organization_id,
                severity="WARN",
            )
            await self._commit()
            raise UnauthorizedException(detail="Invalid recovery code.")

        await self.password_service.validatePolicy(password=new_password, user=user)
        if await self.password_service.isReused(user=user, new_password=new_password):
            raise BadRequestException(detail="Password was used recently. Choose a different password.")

        await self.password_service.setPassword(
            user=user,
            new_password=new_password,
            reason="RECOVERY_CODE_RESET",
            actor_id=user.user_id,
        )
        await self.session_service.revokeAll(user_id=user.user_id, reason="RECOVERY_CODE_RESET")
        user.token_version += 1
        await self.auth_repository.db_session.flush()
        await self._enqueue(
            template="PASSWORD_CHANGED_NOTICE",
            recipient=user.email,
            full_name=user.full_name,
            action_url="",
            expires_in="not applicable",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="PASSWORD_RESET_WITH_RECOVERY_CODE",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )

    async def issueAccountRecoveryToken(self, user: UserTableDto) -> str:
        """Issues an out-of-band token that lets a user regain account access.

        Args:
            user (UserTableDto): User whose account is being recovered.

        Returns:
            str: Raw recovery token to deliver through a verified channel.
        """
        await self.token_repository.revokeActiveForUserPurpose(
            user_id=user.user_id,
            purpose=self.PURPOSE_ACCOUNT_RECOVERY,
        )
        raw_token = await self._createToken(
            user=user,
            purpose=self.PURPOSE_ACCOUNT_RECOVERY,
            expires_delta=timedelta(days=AppConfig.ACCOUNT_RECOVERY_EXPIRE_DAYS),
        )
        recovery = await self.auth_repository.getRecoveryEmail(user_id=user.user_id)
        recipient = (
            recovery.email
            if recovery is not None and recovery.verified_at is not None
            else user.email
        )
        await self._enqueue(
            template="RECOVERY_APPROVED",
            recipient=recipient,
            full_name=user.full_name,
            action_url=self._actionUrl(AppConfig.PASSWORD_RESET_URL, raw_token),
            expires_in=f"{AppConfig.ACCOUNT_RECOVERY_EXPIRE_DAYS} days",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="ACCOUNT_RECOVERY_TOKEN_ISSUED",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="CRITICAL",
            metadata={"recipient_hash": TokenHelper.hashEmail(recipient)},
        )
        return raw_token

    async def confirmAccountRecovery(self, token: str, new_password: str) -> None:
        """Consumes an account recovery token and sets a new password.

        Args:
            token (str): Raw account recovery token.
            new_password (str): New plain-text password.

        Raises:
            BadRequestException: If the token is invalid or the password is weak or reused.
        """
        token_entity = await self._getValidToken(token, self.PURPOSE_ACCOUNT_RECOVERY)
        user = await self.auth_repository.getById(user_id=token_entity.user_id)
        if user is None:
            raise BadRequestException(detail="Token is invalid or has expired.")

        await self.password_service.validatePolicy(password=new_password, user=user)
        if await self.password_service.isReused(user=user, new_password=new_password):
            raise BadRequestException(detail="Password was used recently. Choose a different password.")

        await self.password_service.setPassword(
            user=user,
            new_password=new_password,
            reason="ACCOUNT_RECOVERY",
            actor_id=user.user_id,
        )
        await self.token_repository.markUsed(token=token_entity)
        await self.session_service.revokeAll(user_id=user.user_id, reason="ACCOUNT_RECOVERY")
        user.token_version += 1
        user.is_active = True
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.auth_repository.db_session.flush()
        await self._enqueue(
            template="PASSWORD_CHANGED_NOTICE",
            recipient=user.email,
            full_name=user.full_name,
            action_url="",
            expires_in="not applicable",
            organization_id=user.organization_id,
        )
        await self.audit_service.record(
            event_type="ACCOUNT_RECOVERY_COMPLETED",
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="CRITICAL",
        )

    async def setupMfa(self, user: UserTableDto) -> MfaSetupResponse:
        """Starts TOTP enrollment for an authenticated user.

        Args:
            user (UserTableDto): Authenticated user entity.

        Returns:
            MfaSetupResponse: Secret and provisioning URI.
        """
        if user.mfa_enabled:
            raise BadRequestException(detail="MFA is already enabled.")
        return await self.mfa_service.beginSetup(user=user)

    async def confirmMfa(self, user: UserTableDto, code: str) -> list[str]:
        """Confirms TOTP enrollment and returns recovery codes.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): Six-digit TOTP code.

        Returns:
            list[str]: Plain-text recovery codes.
        """
        codes = await self.mfa_service.confirmSetup(user=user, code=code)
        await self.audit_service.record(
            event_type="MFA_ENABLED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )
        return codes

    async def disableMfa(self, user: UserTableDto, payload: MfaDisableSchema) -> None:
        """Disables MFA after verifying the password and a current code.

        Args:
            user (UserTableDto): Authenticated user entity.
            payload (MfaDisableSchema): Password and TOTP or recovery code.

        Raises:
            BadRequestException: If the password is wrong.
        """
        if not PasswordHelper.verifyPassword(payload.password, user.hashed_password):
            raise BadRequestException(detail="Current password is incorrect.")
        await self.mfa_service.disable(user=user, code=payload.code)
        await self.audit_service.record(
            event_type="MFA_DISABLED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )

    async def regenerateRecoveryCodes(self, user: UserTableDto, code: str) -> list[str]:
        """Replaces MFA recovery codes after verifying a current code.

        Args:
            user (UserTableDto): Authenticated user entity.
            code (str): TOTP or recovery code.

        Returns:
            list[str]: New plain-text recovery codes.

        Raises:
            UnauthorizedException: If MFA is disabled or the code is invalid.
        """
        if not user.mfa_enabled:
            raise BadRequestException(detail="MFA is not enabled for this account.")
        if not await self.mfa_service.verify(user=user, code=code):
            await self._commit()
            raise UnauthorizedException(detail="Invalid verification code.")
        codes = await self.mfa_service.regenerateRecoveryCodes(user=user)
        await self.audit_service.record(
            event_type="MFA_RECOVERY_CODES_REGENERATED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            severity="WARN",
        )
        return codes

    async def listSessions(self, user: UserTableDto, current_session_id: str | None) -> list[SessionResponse]:
        """Lists active sessions for the authenticated user.

        Args:
            user (UserTableDto): Authenticated user entity.
            current_session_id (str | None): Current session identifier.

        Returns:
            list[SessionResponse]: Active sessions newest first.
        """
        sessions = await self.session_repository.listActiveForUser(user_id=user.user_id)
        return [
            SessionResponse(
                session_id=item.session_id,
                ip=item.ip,
                user_agent=item.user_agent,
                issued_at=item.issued_at,
                expires_at=item.expires_at,
                last_used_at=item.last_used_at,
                current=item.session_id == current_session_id,
            )
            for item in sessions
        ]

    async def revokeSession(self, user: UserTableDto, session_id: str, current_session_id: str | None) -> None:
        """Revokes one session owned by the authenticated user.

        Args:
            user (UserTableDto): Authenticated user entity.
            session_id (str): Session identifier to revoke.
            current_session_id (str | None): Current session identifier.

        Raises:
            BadRequestException: If the session does not belong to the user.
        """
        session = await self.session_repository.getById(session_id=session_id)
        if session is None or session.user_id != user.user_id:
            raise BadRequestException(detail="Session not found.")
        await self.session_service.revokeSession(session=session, reason="USER_REVOKED")
        await self.audit_service.record(
            event_type="SESSION_REVOKED",
            actor_user_id=user.user_id,
            target_user_id=user.user_id,
            organization_id=user.organization_id,
            metadata={"session_id": session_id, "current": session_id == current_session_id},
        )
