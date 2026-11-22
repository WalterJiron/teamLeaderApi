from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.AuthAuditLogTableDto import AuthAuditLogTableDto


class AuditRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def addLog(self, log: AuthAuditLogTableDto) -> AuthAuditLogTableDto:
        """Persists an audit log entry.

        Args:
            log (AuthAuditLogTableDto): Audit entry to insert.

        Returns:
            AuthAuditLogTableDto: Flushed audit entry.
        """
        self.db_session.add(log)
        await self.db_session.flush()
        return log

    async def getLastHash(self) -> str | None:
        """Returns the most recent audit hash for the integrity chain.

        Returns:
            str | None: Last entry hash or None when the log is empty.
        """
        query = select(AuthAuditLogTableDto.entry_hash).order_by(
            AuthAuditLogTableDto.audit_id.desc()
        ).limit(1)
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def listLogs(
        self,
        organization_id: int,
        offset: int,
        limit: int,
        event_type: str | None = None,
    ) -> list[AuthAuditLogTableDto]:
        """Lists audit entries for an organization with pagination.

        Args:
            organization_id (int): Organization identifier.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.
            event_type (str | None, optional): Optional event type filter.

        Returns:
            list[AuthAuditLogTableDto]: Audit entries ordered newest first.
        """
        query = select(AuthAuditLogTableDto).where(
            AuthAuditLogTableDto.organization_id == organization_id
        )
        if event_type:
            query = query.where(AuthAuditLogTableDto.event_type == event_type)
        query = query.order_by(AuthAuditLogTableDto.audit_id.desc()).offset(offset).limit(limit)
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countLogs(self, organization_id: int, event_type: str | None = None) -> int:
        """Counts audit entries for an organization.

        Args:
            organization_id (int): Organization identifier.
            event_type (str | None, optional): Optional event type filter.

        Returns:
            int: Total matching audit entries.
        """
        query = select(func.count(AuthAuditLogTableDto.audit_id)).where(
            AuthAuditLogTableDto.organization_id == organization_id
        )
        if event_type:
            query = query.where(AuthAuditLogTableDto.event_type == event_type)
        result = await self.db_session.execute(query)
        return int(result.scalar_one())
