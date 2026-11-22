from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auth.dto.EmailOutboxTableDto import EmailOutboxTableDto


class OutboxRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def addEmail(self, email: EmailOutboxTableDto) -> EmailOutboxTableDto:
        """Persists an email outbox entry.

        Args:
            email (EmailOutboxTableDto): Outbox entity to insert.

        Returns:
            EmailOutboxTableDto: Flushed outbox entity.
        """
        self.db_session.add(email)
        await self.db_session.flush()
        await self.db_session.refresh(email)
        return email

    async def getPending(self, limit: int) -> list[EmailOutboxTableDto]:
        """Fetches pending emails that are due for delivery.

        Args:
            limit (int): Maximum number of emails to return.

        Returns:
            list[EmailOutboxTableDto]: Due outbox entries.
        """
        now = datetime.now(timezone.utc)
        query = (
            select(EmailOutboxTableDto)
            .where(
                EmailOutboxTableDto.status == "PENDING",
                (EmailOutboxTableDto.next_attempt_at.is_(None))
                | (EmailOutboxTableDto.next_attempt_at <= now),
            )
            .order_by(EmailOutboxTableDto.created_at.asc())
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def markSent(self, email: EmailOutboxTableDto) -> None:
        """Marks an outbox email as delivered.

        Args:
            email (EmailOutboxTableDto): Outbox entity.
        """
        email.status = "SENT"
        email.sent_at = datetime.now(timezone.utc)
        email.last_error = None
        await self.db_session.flush()

    async def markFailed(self, email: EmailOutboxTableDto, error: str) -> None:
        """Marks an outbox email as failed and schedules a retry.

        Args:
            email (EmailOutboxTableDto): Outbox entity.
            error (str): Failure description.
        """
        email.attempts += 1
        email.last_error = error[:2000]
        if email.attempts >= 10:
            email.status = "FAILED"
        else:
            delay_seconds = min(60 * (2 ** (email.attempts - 1)), 3600)
            email.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        await self.db_session.flush()
