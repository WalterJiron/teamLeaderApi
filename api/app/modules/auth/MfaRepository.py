from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.UserMfaSettingTableDto import UserMfaSettingTableDto
from app.modules.auth.dto.UserRecoveryCodeTableDto import UserRecoveryCodeTableDto


class MfaRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def getByUserId(self, user_id: int) -> UserMfaSettingTableDto | None:
        """Fetches the MFA settings for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            UserMfaSettingTableDto | None: MFA settings or None.
        """
        query = select(UserMfaSettingTableDto).where(UserMfaSettingTableDto.user_id == user_id)
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def upsertSetting(self, setting: UserMfaSettingTableDto) -> UserMfaSettingTableDto:
        """Creates or updates the MFA settings for a user.

        Args:
            setting (UserMfaSettingTableDto): MFA settings entity.

        Returns:
            UserMfaSettingTableDto: Flushed MFA settings.
        """
        existing = await self.getByUserId(setting.user_id)
        if existing is None:
            self.db_session.add(setting)
            await self.db_session.flush()
            await self.db_session.refresh(setting)
            return setting
        existing.totp_secret_encrypted = setting.totp_secret_encrypted
        existing.totp_enabled = setting.totp_enabled
        existing.confirmed_at = setting.confirmed_at
        existing.failed_attempts = setting.failed_attempts
        existing.locked_until = setting.locked_until
        await self.db_session.flush()
        return existing

    async def deleteSetting(self, user_id: int) -> None:
        """Deletes MFA settings for a user.

        Args:
            user_id (int): Unique user identifier.
        """
        await self.db_session.execute(
            delete(UserMfaSettingTableDto).where(UserMfaSettingTableDto.user_id == user_id)
        )

    async def addRecoveryCodes(self, codes: list[UserRecoveryCodeTableDto]) -> None:
        """Persists a batch of recovery codes.

        Args:
            codes (list[UserRecoveryCodeTableDto]): Recovery code entities.
        """
        self.db_session.add_all(codes)
        await self.db_session.flush()

    async def deleteRecoveryCodes(self, user_id: int) -> None:
        """Deletes all recovery codes for a user.

        Args:
            user_id (int): Unique user identifier.
        """
        await self.db_session.execute(
            delete(UserRecoveryCodeTableDto).where(UserRecoveryCodeTableDto.user_id == user_id)
        )

    async def getUnusedRecoveryCodes(self, user_id: int) -> list[UserRecoveryCodeTableDto]:
        """Fetches unused recovery codes for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            list[UserRecoveryCodeTableDto]: Unused recovery code entities.
        """
        query = select(UserRecoveryCodeTableDto).where(
            UserRecoveryCodeTableDto.user_id == user_id,
            UserRecoveryCodeTableDto.used_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())
