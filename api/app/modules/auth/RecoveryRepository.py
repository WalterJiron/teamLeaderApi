from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.AccountRecoveryRequestTableDto import AccountRecoveryRequestTableDto


class RecoveryRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def addRequest(self, request: AccountRecoveryRequestTableDto) -> AccountRecoveryRequestTableDto:
        """Persists an account recovery request.

        Args:
            request (AccountRecoveryRequestTableDto): Recovery request entity.

        Returns:
            AccountRecoveryRequestTableDto: Flushed recovery request.
        """
        self.db_session.add(request)
        await self.db_session.flush()
        await self.db_session.refresh(request)
        return request

    async def getById(self, request_id: str) -> AccountRecoveryRequestTableDto | None:
        """Fetches an account recovery request by identifier.

        Args:
            request_id (str): Recovery request identifier.

        Returns:
            AccountRecoveryRequestTableDto | None: Matching request or None.
        """
        query = select(AccountRecoveryRequestTableDto).where(
            AccountRecoveryRequestTableDto.request_id == request_id
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def getPendingByUser(self, user_id: int) -> AccountRecoveryRequestTableDto | None:
        """Fetches an active pending recovery request for a user.

        Args:
            user_id (int): Unique user identifier.

        Returns:
            AccountRecoveryRequestTableDto | None: Pending request or None.
        """
        query = select(AccountRecoveryRequestTableDto).where(
            AccountRecoveryRequestTableDto.user_id == user_id,
            AccountRecoveryRequestTableDto.status == "PENDING",
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def listRequests(
        self,
        organization_id: int,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> list[AccountRecoveryRequestTableDto]:
        """Lists recovery requests for an organization.

        Args:
            organization_id (int): Organization identifier.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.
            status (str | None, optional): Optional status filter.

        Returns:
            list[AccountRecoveryRequestTableDto]: Recovery requests newest first.
        """
        query = select(AccountRecoveryRequestTableDto).where(
            AccountRecoveryRequestTableDto.organization_id == organization_id
        )
        if status:
            query = query.where(AccountRecoveryRequestTableDto.status == status)
        query = query.order_by(AccountRecoveryRequestTableDto.created_at.desc()).offset(offset).limit(limit)
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countRequests(self, organization_id: int, status: str | None = None) -> int:
        """Counts recovery requests for an organization.

        Args:
            organization_id (int): Organization identifier.
            status (str | None, optional): Optional status filter.

        Returns:
            int: Total matching recovery requests.
        """
        query = select(func.count(AccountRecoveryRequestTableDto.request_id)).where(
            AccountRecoveryRequestTableDto.organization_id == organization_id
        )
        if status:
            query = query.where(AccountRecoveryRequestTableDto.status == status)
        result = await self.db_session.execute(query)
        return int(result.scalar_one())
