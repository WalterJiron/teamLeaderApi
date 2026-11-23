from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.PostgresManager import PostgresManager
from app.modules.metrics.MetricRepository import MetricRepository
from app.modules.metrics.service.MetricService import MetricService


def getMetricRepository(
    db_session: AsyncSession = Depends(PostgresManager.getSession),
) -> MetricRepository:
    """Provides a MetricRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        MetricRepository: Area snapshot persistence repository.
    """
    return MetricRepository(db_session=db_session)


def getMetricService(
    metric_repository: MetricRepository = Depends(getMetricRepository),
) -> MetricService:
    """Provides a MetricService with its injected repository.

    Args:
        metric_repository (MetricRepository): Injected area snapshot repository.

    Returns:
        MetricService: Deterministic metric calculation service.
    """
    return MetricService(metric_repository=metric_repository)
