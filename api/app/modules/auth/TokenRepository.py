from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.AuthTokenTableDto import AuthTokenTableDto


class TokenRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def addToken(self, token: AuthTokenTableDto) -> AuthTokenTableDto:
        """Persists a new single-use authentication token.

        Args:
            token (AuthTokenTableDto): Token entity to insert.

        Returns:
            AuthTokenTableDto: Flushed token entity.
        """
        self.db_session.add(token)
        await self.db_session.flush()
        await self.db_session.refresh(token)
        return token

    async def getByHashAndPurpose(self, token_hash: str, purpose: str) -> AuthTokenTableDto | None:
        """Fetches a token by hash and purpose.

        Args:
            token_hash (str): SHA-256 digest of the raw token.
            purpose (str): Token purpose code.

        Returns:
            AuthTokenTableDto | None: Matching token or None.
        """
        query = select(AuthTokenTableDto).where(
            AuthTokenTableDto.token_hash == token_hash,
            AuthTokenTableDto.purpose == purpose,
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def markUsed(self, token: AuthTokenTableDto) -> None:
        """Marks a token as consumed.

        Args:
            token (AuthTokenTableDto): Token entity to mark.
        """
        token.used_at = datetime.now(timezone.utc)
        await self.db_session.flush()

    async def revokeActiveForUserPurpose(self, user_id: int, purpose: str) -> None:
        """Revokes all unused tokens of a purpose for a user.

        Args:
            user_id (int): Unique user identifier.
            purpose (str): Token purpose code.
        """
        now = datetime.now(timezone.utc)
        await self.db_session.execute(
            update(AuthTokenTableDto)
            .where(
                AuthTokenTableDto.user_id == user_id,
                AuthTokenTableDto.purpose == purpose,
                AuthTokenTableDto.used_at.is_(None),
                AuthTokenTableDto.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def revokeToken(self, token: AuthTokenTableDto) -> None:
        """Revokes a single token.

        Args:
            token (AuthTokenTableDto): Token entity to revoke.
        """
        token.revoked_at = datetime.now(timezone.utc)
        await self.db_session.flush()
