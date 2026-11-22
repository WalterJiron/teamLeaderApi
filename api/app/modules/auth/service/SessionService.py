from datetime import datetime, timedelta, timezone
from app.core.AppConfig import AppConfig
from app.modules.auth.SessionRepository import SessionRepository
from app.modules.auth.dto.UserSessionTableDto import UserSessionTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.auth.utils.JwtHelper import JwtHelper
from app.modules.auth.utils.PasswordHelper import PasswordHelper
from app.modules.auth.utils.TokenHelper import TokenHelper


class SessionService:

    def __init__(self, session_repository: SessionRepository) -> None:
        """Initializes the session service with its repository.

        Args:
            session_repository (SessionRepository): Session persistence repository.
        """
        self.session_repository = session_repository

    async def createSession(
        self,
        user: UserTableDto,
        mfa_verified: bool,
        ip: str | None,
        user_agent: str | None,
        token_family_id: str | None = None,
    ) -> tuple[UserSessionTableDto, str, str]:
        """Creates a session and returns its refresh token and access token.

        Args:
            user (UserTableDto): Authenticated user entity.
            mfa_verified (bool): Whether MFA was completed for this session.
            ip (str | None): Client IP address.
            user_agent (str | None): Client User-Agent.
            token_family_id (str | None, optional): Existing refresh token family. Defaults to None.

        Returns:
            tuple[UserSessionTableDto, str, str]: Session, refresh token, access token.
        """
        refresh_token = PasswordHelper.generateOpaqueToken(48)
        session = UserSessionTableDto(
            session_id=TokenHelper.newId(),
            user_id=user.user_id,
            organization_id=user.organization_id,
            refresh_token_hash=PasswordHelper.hashOpaqueToken(refresh_token),
            token_family_id=token_family_id or TokenHelper.newId(),
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=AppConfig.JWT_REFRESH_EXPIRE_MINUTES),
            last_used_at=datetime.now(timezone.utc),
            ip=ip,
            user_agent=user_agent,
            mfa_verified=mfa_verified,
        )
        await self.session_repository.addSession(session)
        access_token = JwtHelper.createAccessToken(user=user, session_id=session.session_id)
        return session, refresh_token, access_token

    async def rotateSession(
        self,
        old_session: UserSessionTableDto,
        user: UserTableDto,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[UserSessionTableDto, str, str]:
        """Rotates a refresh token and revokes the previous session.

        Args:
            old_session (UserSessionTableDto): Session being refreshed.
            user (UserTableDto): Authenticated user entity.
            ip (str | None): Client IP address.
            user_agent (str | None): Client User-Agent.

        Returns:
            tuple[UserSessionTableDto, str, str]: New session, refresh token, access token.
        """
        new_session, refresh_token, access_token = await self.createSession(
            user=user,
            mfa_verified=old_session.mfa_verified,
            ip=ip,
            user_agent=user_agent,
            token_family_id=old_session.token_family_id,
        )
        await self.session_repository.revokeSession(
            session=old_session,
            reason="ROTATED",
            replaced_by_session_id=new_session.session_id,
        )
        return new_session, refresh_token, access_token

    async def revokeSession(self, session: UserSessionTableDto, reason: str) -> None:
        """Revokes a session.

        Args:
            session (UserSessionTableDto): Session entity.
            reason (str): Revocation reason code.
        """
        await self.session_repository.revokeSession(session=session, reason=reason)

    async def revokeAll(self, user_id: int, reason: str, except_session_id: str | None = None) -> None:
        """Revokes all sessions for a user.

        Args:
            user_id (int): Unique user identifier.
            reason (str): Revocation reason code.
            except_session_id (str | None, optional): Session to preserve. Defaults to None.
        """
        await self.session_repository.revokeAllForUser(
            user_id=user_id,
            reason=reason,
            except_session_id=except_session_id,
        )
