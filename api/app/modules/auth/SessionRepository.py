from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.UserSessionTableDto import UserSessionTableDto


class SessionRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def addSession(self, session: UserSessionTableDto) -> UserSessionTableDto:
        """Persists a new user session.

        Args:
            session (UserSessionTableDto): Session entity to insert.

        Returns:
            UserSessionTableDto: Flushed session entity.
        """
        self.db_session.add(session)
        await self.db_session.flush()
        await self.db_session.refresh(session)
        return session

    async def getByRefreshHash(self, refresh_token_hash: str) -> UserSessionTableDto | None:
        """Fetches a session by its hashed refresh token.

        Args:
            refresh_token_hash (str): SHA-256 digest of the refresh token.

        Returns:
            UserSessionTableDto | None: Matching session or None.
        """
        query = select(UserSessionTableDto).where(
            UserSessionTableDto.refresh_token_hash == refresh_token_hash
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getById(self, session_id: str) -> UserSessionTableDto | None:
        """Fetches a session by identifier.

        Args:
            session_id (str): Session identifier.

        Returns:
            UserSessionTableDto | None: Matching session or None.
        """
        query = select(UserSessionTableDto).where(UserSessionTableDto.session_id == session_id)
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def revokeSession(
        self,
        session: UserSessionTableDto,
        reason: str,
        replaced_by_session_id: str | None = None,
    ) -> None:
        """Revokes a single session.

        Args:
            session (UserSessionTableDto): Session entity to revoke.
            reason (str): Revocation reason code.
            replaced_by_session_id (str | None, optional): Rotation successor. Defaults to None.
        """
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason
        if replaced_by_session_id is not None:
            session.replaced_by_session_id = replaced_by_session_id
        await self.db_session.flush()

    async def revokeFamily(self, token_family_id: str, reason: str) -> None:
        """Revokes every session in a refresh token family.

        Args:
            token_family_id (str): Refresh token family identifier.
            reason (str): Revocation reason code.
        """
        now = datetime.now(timezone.utc)
        await self.db_session.execute(
            update(UserSessionTableDto)
            .where(
                UserSessionTableDto.token_family_id == token_family_id,
                UserSessionTableDto.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=reason)
        )

    async def revokeAllForUser(
        self,
        user_id: int,
        reason: str,
        except_session_id: str | None = None,
    ) -> None:
        """Revokes all active sessions for a user.

        Args:
            user_id (int): Unique user identifier.
            reason (str): Revocation reason code.
            except_session_id (str | None, optional): Session to preserve. Defaults to None.
        """
        now = datetime.now(timezone.utc)
        query = update(UserSessionTableDto).where(
            UserSessionTableDto.user_id == user_id,
            UserSessionTableDto.revoked_at.is_(None),
        )
        if except_session_id is not None:
            query = query.where(UserSessionTableDto.session_id != except_session_id)
        await self.db_session.execute(query.values(revoked_at=now, revoked_reason=reason))

    async def listActiveForUser(self, user_id: int) -> list[UserSessionTableDto]:
        """Lists active, non-expired sessions for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            list[UserSessionTableDto]: Active sessions ordered by issue date.
        """
        now = datetime.now(timezone.utc)
        query = (
            select(UserSessionTableDto)
            .where(
                UserSessionTableDto.user_id == user_id,
                UserSessionTableDto.revoked_at.is_(None),
                UserSessionTableDto.expires_at > now,
            )
            .order_by(UserSessionTableDto.issued_at.desc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countActiveForUser(self, user_id: int) -> int:
        """Counts active sessions for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            int: Active session count.
        """
        now = datetime.now(timezone.utc)
        query = select(func.count(UserSessionTableDto.session_id)).where(
            UserSessionTableDto.user_id == user_id,
            UserSessionTableDto.revoked_at.is_(None),
            UserSessionTableDto.expires_at > now,
        )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())
