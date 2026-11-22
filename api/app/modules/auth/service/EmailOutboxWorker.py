import asyncio
import logging
from app.core.AppConfig import AppConfig
from app.core.PostgresManager import PostgresManager
from app.modules.auth.OutboxRepository import OutboxRepository
from app.modules.auth.service.EmailService import EmailService

logger = logging.getLogger(__name__)


class EmailOutboxWorker:

    _task: asyncio.Task | None = None

    @classmethod
    def start(cls) -> None:
        """Starts the background email outbox delivery loop."""
        if cls._task is None:
            cls._task = asyncio.create_task(cls._run())

    @classmethod
    async def stop(cls) -> None:
        """Stops the background email outbox delivery loop."""
        if cls._task is not None:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
            cls._task = None

    @classmethod
    async def _run(cls) -> None:
        """Continuously processes due outbox emails until cancelled."""
        while True:
            try:
                async with PostgresManager.session_factory() as session:
                    repository = OutboxRepository(db_session=session)
                    processed = await EmailService.processOutbox(session, repository)
                    if processed:
                        await session.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Email outbox worker iteration failed.")
            await asyncio.sleep(AppConfig.EMAIL_OUTBOX_INTERVAL_SECONDS)
