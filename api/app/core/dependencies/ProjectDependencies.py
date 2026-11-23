from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.PostgresManager import PostgresManager
from app.modules.projects.ProjectRepository import ProjectRepository


def getProjectRepository(
    db_session: AsyncSession = Depends(PostgresManager.getSession),
) -> ProjectRepository:
    """Provides a ProjectRepository bound to the current database session.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        ProjectRepository: Project and area persistence repository.
    """
    return ProjectRepository(db_session=db_session)
