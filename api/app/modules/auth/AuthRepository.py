from datetime import datetime
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.LoginAttemptTableDto import LoginAttemptTableDto
from app.modules.auth.dto.OrganizationInvitationTableDto import OrganizationInvitationTableDto
from app.modules.auth.dto.OrganizationTableDto import OrganizationTableDto
from app.modules.auth.dto.PasswordHistoryTableDto import PasswordHistoryTableDto
from app.modules.auth.dto.UserEmailTableDto import UserEmailTableDto
from app.modules.auth.dto.UserTableDto import UserTableDto


class AuthRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    @staticmethod
    def normalizeEmail(email: str) -> str:
        """Normalizes an email address for case-insensitive lookups.

        Args:
            email (str): Raw email address.

        Returns:
            str: Trimmed lowercase email.
        """
        return email.strip().lower()

    async def getByEmail(self, email: str, include_deleted: bool = False, for_update: bool = False) -> UserTableDto | None:
        """Fetches a user record by primary email address.

        Args:
            email (str): Email address to search for.
            include_deleted (bool, optional): Include soft-deleted users. Defaults to False.
            for_update (bool, optional): Lock the row for update. Defaults to False.

        Returns:
            UserTableDto | None: Matching user entity or None.
        """
        query = select(UserTableDto).where(func.lower(UserTableDto.email) == self.normalizeEmail(email))
        if not include_deleted:
            query = query.where(UserTableDto.deleted_at.is_(None))
        if for_update:
            query = query.with_for_update()
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getById(self, user_id: int, include_deleted: bool = False, for_update: bool = False) -> UserTableDto | None:
        """Fetches a user record by primary key.

        Args:
            user_id (int): Unique user identifier.
            include_deleted (bool, optional): Include soft-deleted users. Defaults to False.
            for_update (bool, optional): Lock the row for update. Defaults to False.

        Returns:
            UserTableDto | None: Matching user entity or None.
        """
        query = select(UserTableDto).where(UserTableDto.user_id == user_id)
        if not include_deleted:
            query = query.where(UserTableDto.deleted_at.is_(None))
        if for_update:
            query = query.with_for_update()
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getByAnyEmail(self, email: str) -> UserTableDto | None:
        """Fetches a user by primary or recovery email address.

        Args:
            email (str): Email address to search for.

        Returns:
            UserTableDto | None: Matching active user or None.
        """
        normalized = self.normalizeEmail(email)
        query = (
            select(UserTableDto)
            .join(UserEmailTableDto, UserTableDto.user_id == UserEmailTableDto.user_id)
            .where(
                func.lower(UserEmailTableDto.email) == normalized,
                UserEmailTableDto.deleted_at.is_(None),
                UserTableDto.deleted_at.is_(None),
            )
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getUserEmail(self, email: str, verified_only: bool = False) -> UserEmailTableDto | None:
        """Fetches an email record by address.

        Args:
            email (str): Email address to search for.
            verified_only (bool, optional): Only return verified addresses. Defaults to False.

        Returns:
            UserEmailTableDto | None: Matching email entity or None.
        """
        query = select(UserEmailTableDto).where(
            func.lower(UserEmailTableDto.email) == self.normalizeEmail(email),
            UserEmailTableDto.deleted_at.is_(None),
        )
        if verified_only:
            query = query.where(UserEmailTableDto.verified_at.is_not(None))
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getPrimaryEmail(self, user_id: int) -> UserEmailTableDto | None:
        """Fetches the primary email record for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            UserEmailTableDto | None: Primary email entity or None.
        """
        query = select(UserEmailTableDto).where(
            UserEmailTableDto.user_id == user_id,
            UserEmailTableDto.is_primary.is_(True),
            UserEmailTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getRecoveryEmail(self, user_id: int) -> UserEmailTableDto | None:
        """Fetches the recovery email record for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            UserEmailTableDto | None: Recovery email entity or None.
        """
        query = select(UserEmailTableDto).where(
            UserEmailTableDto.user_id == user_id,
            UserEmailTableDto.is_recovery.is_(True),
            UserEmailTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def emailExists(self, email: str) -> bool:
        """Checks whether an email address is already assigned to an active account.

        Args:
            email (str): Email address to inspect.

        Returns:
            bool: True when the email is already registered.
        """
        normalized = self.normalizeEmail(email)
        email_query = select(UserEmailTableDto.email_id).where(
            func.lower(UserEmailTableDto.email) == normalized,
            UserEmailTableDto.deleted_at.is_(None),
        )
        user_query = select(UserTableDto.user_id).where(
            func.lower(UserTableDto.email) == normalized,
            UserTableDto.deleted_at.is_(None),
        )
        email_result = await self.db_session.execute(email_query)
        if email_result.scalars().first() is not None:
            return True
        user_result = await self.db_session.execute(user_query)
        return user_result.scalars().first() is not None

    async def addUser(self, user: UserTableDto) -> UserTableDto:
        """Persists a new user entity.

        Args:
            user (UserTableDto): User entity to insert.

        Returns:
            UserTableDto: Flushed user entity with populated defaults.
        """
        self.db_session.add(user)
        await self.db_session.flush()
        await self.db_session.refresh(user)
        return user

    async def addUserEmail(self, user_email: UserEmailTableDto) -> UserEmailTableDto:
        """Persists an email address associated with a user.

        Args:
            user_email (UserEmailTableDto): Email entity to insert.

        Returns:
            UserEmailTableDto: Flushed email entity.
        """
        self.db_session.add(user_email)
        await self.db_session.flush()
        await self.db_session.refresh(user_email)
        return user_email

    async def addPasswordHistory(self, history: PasswordHistoryTableDto) -> PasswordHistoryTableDto:
        """Persists a password history entry.

        Args:
            history (PasswordHistoryTableDto): History entity to insert.

        Returns:
            PasswordHistoryTableDto: Flushed history entity.
        """
        self.db_session.add(history)
        await self.db_session.flush()
        return history

    async def getPasswordHistory(self, user_id: int, limit: int) -> list[PasswordHistoryTableDto]:
        """Fetches recent password history entries for a user.

        Args:
            user_id (int): Unique user identifier.
            limit (int): Maximum number of entries to return.

        Returns:
            list[PasswordHistoryTableDto]: Newest history entries first.
        """
        query = (
            select(PasswordHistoryTableDto)
            .where(PasswordHistoryTableDto.user_id == user_id)
            .order_by(PasswordHistoryTableDto.created_at.desc())
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def prunePasswordHistory(self, user_id: int, keep: int) -> None:
        """Deletes old password history entries beyond the configured retention count.

        Args:
            user_id (int): Unique user identifier.
            keep (int): Number of newest entries to preserve.
        """
        query = (
            select(PasswordHistoryTableDto.history_id)
            .where(PasswordHistoryTableDto.user_id == user_id)
            .order_by(PasswordHistoryTableDto.created_at.desc())
            .offset(keep)
        )
        result = await self.db_session.execute(query)
        stale_ids = list(result.scalars().all())
        if stale_ids:
            await self.db_session.execute(
                delete(PasswordHistoryTableDto).where(PasswordHistoryTableDto.history_id.in_(stale_ids))
            )

    async def listUsers(
        self,
        organization_id: int,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> list[UserTableDto]:
        """Lists active users within an organization with optional search.

        Args:
            organization_id (int): Organization identifier.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.
            search (str | None, optional): Case-insensitive name or email fragment. Defaults to None.

        Returns:
            list[UserTableDto]: User entities ordered by creation date.
        """
        query = select(UserTableDto).where(
            UserTableDto.organization_id == organization_id,
            UserTableDto.deleted_at.is_(None),
        )
        if search:
            pattern = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(UserTableDto.full_name).like(pattern),
                    func.lower(UserTableDto.email).like(pattern),
                )
            )
        query = query.order_by(UserTableDto.created_at.desc()).offset(offset).limit(limit)
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countUsers(self, organization_id: int, search: str | None = None) -> int:
        """Counts active users within an organization.

        Args:
            organization_id (int): Organization identifier.
            search (str | None, optional): Case-insensitive name or email fragment. Defaults to None.

        Returns:
            int: Total matching users.
        """
        query = select(func.count(UserTableDto.user_id)).where(
            UserTableDto.organization_id == organization_id,
            UserTableDto.deleted_at.is_(None),
        )
        if search:
            pattern = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(UserTableDto.full_name).like(pattern),
                    func.lower(UserTableDto.email).like(pattern),
                )
            )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())

    async def getOrganization(self, organization_id: int) -> OrganizationTableDto | None:
        """Fetches an active organization by primary key.

        Args:
            organization_id (int): Unique organization identifier.

        Returns:
            OrganizationTableDto | None: Matching organization or None.
        """
        query = select(OrganizationTableDto).where(
            OrganizationTableDto.organization_id == organization_id,
            OrganizationTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getOrganizationBySlug(self, slug: str) -> OrganizationTableDto | None:
        """Fetches an active organization by slug.

        Args:
            slug (str): Unique organization slug.

        Returns:
            OrganizationTableDto | None: Matching organization or None.
        """
        query = select(OrganizationTableDto).where(
            OrganizationTableDto.slug == slug,
            OrganizationTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def addOrganization(self, organization: OrganizationTableDto) -> OrganizationTableDto:
        """Persists a new organization.

        Args:
            organization (OrganizationTableDto): Organization entity to insert.

        Returns:
            OrganizationTableDto: Flushed organization entity.
        """
        self.db_session.add(organization)
        await self.db_session.flush()
        await self.db_session.refresh(organization)
        return organization

    async def getInvitationByTokenHash(self, token_hash: str) -> OrganizationInvitationTableDto | None:
        """Fetches an invitation by its hashed token.

        Args:
            token_hash (str): SHA-256 digest of the invitation token.

        Returns:
            OrganizationInvitationTableDto | None: Matching invitation or None.
        """
        query = select(OrganizationInvitationTableDto).where(
            OrganizationInvitationTableDto.token_hash == token_hash,
            OrganizationInvitationTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getPendingInvitation(self, organization_id: int, email: str) -> OrganizationInvitationTableDto | None:
        """Fetches a pending invitation for an email within an organization.

        Args:
            organization_id (int): Organization identifier.
            email (str): Invited email address.

        Returns:
            OrganizationInvitationTableDto | None: Pending invitation or None.
        """
        query = select(OrganizationInvitationTableDto).where(
            OrganizationInvitationTableDto.organization_id == organization_id,
            func.lower(OrganizationInvitationTableDto.email) == self.normalizeEmail(email),
            OrganizationInvitationTableDto.accepted_at.is_(None),
            OrganizationInvitationTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def addInvitation(self, invitation: OrganizationInvitationTableDto) -> OrganizationInvitationTableDto:
        """Persists an organization invitation.

        Args:
            invitation (OrganizationInvitationTableDto): Invitation entity to insert.

        Returns:
            OrganizationInvitationTableDto: Flushed invitation entity.
        """
        self.db_session.add(invitation)
        await self.db_session.flush()
        await self.db_session.refresh(invitation)
        return invitation

    async def listInvitations(self, organization_id: int, offset: int, limit: int) -> list[OrganizationInvitationTableDto]:
        """Lists invitations for an organization with pagination.

        Args:
            organization_id (int): Organization identifier.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.

        Returns:
            list[OrganizationInvitationTableDto]: Invitation entities.
        """
        query = (
            select(OrganizationInvitationTableDto)
            .where(
                OrganizationInvitationTableDto.organization_id == organization_id,
                OrganizationInvitationTableDto.deleted_at.is_(None),
            )
            .order_by(OrganizationInvitationTableDto.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countInvitations(self, organization_id: int) -> int:
        """Counts invitations for an organization.

        Args:
            organization_id (int): Organization identifier.

        Returns:
            int: Total invitation count.
        """
        query = select(func.count(OrganizationInvitationTableDto.invitation_id)).where(
            OrganizationInvitationTableDto.organization_id == organization_id,
            OrganizationInvitationTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())

    async def addLoginAttempt(self, attempt: LoginAttemptTableDto) -> LoginAttemptTableDto:
        """Persists a login attempt record.

        Args:
            attempt (LoginAttemptTableDto): Login attempt entity.

        Returns:
            LoginAttemptTableDto: Flushed login attempt entity.
        """
        self.db_session.add(attempt)
        await self.db_session.flush()
        return attempt
