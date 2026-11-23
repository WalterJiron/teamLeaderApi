from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.projects.dto.AreaTableDto import AreaTableDto
from app.modules.projects.dto.ProjectTableDto import ProjectTableDto


class ProjectRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def getProject(self, project_id: int, organization_id: int) -> ProjectTableDto | None:
        """Fetches a project scoped to its owning organization.

        Args:
            project_id (int): Project identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            ProjectTableDto | None: Matching project or None when it is absent.
        """
        query = select(ProjectTableDto).where(
            ProjectTableDto.project_id == project_id,
            ProjectTableDto.organization_id == organization_id,
            ProjectTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getArea(self, area_id: int, organization_id: int) -> AreaTableDto | None:
        """Fetches an area scoped to its owning organization.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            AreaTableDto | None: Matching area or None when it is absent.
        """
        query = select(AreaTableDto).where(
            AreaTableDto.area_id == area_id,
            AreaTableDto.organization_id == organization_id,
            AreaTableDto.deleted_at.is_(None),
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getAreasByIds(
        self,
        project_id: int,
        organization_id: int,
        area_ids: list[int],
    ) -> list[AreaTableDto]:
        """Fetches project areas by identifier while enforcing tenant isolation.

        Args:
            project_id (int): Project identifier that owns the areas.
            organization_id (int): Tenant identifier used for isolation.
            area_ids (list[int]): Area identifiers to resolve.

        Returns:
            list[AreaTableDto]: Matching areas ordered by identifier.
        """
        if not area_ids:
            return []
        query = (
            select(AreaTableDto)
            .where(
                AreaTableDto.area_id.in_(area_ids),
                AreaTableDto.project_id == project_id,
                AreaTableDto.organization_id == organization_id,
                AreaTableDto.deleted_at.is_(None),
            )
            .order_by(AreaTableDto.area_id.asc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def listAreas(self, project_id: int, organization_id: int) -> list[AreaTableDto]:
        """Lists all areas belonging to a project within a tenant.

        Args:
            project_id (int): Project identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            list[AreaTableDto]: Project areas ordered by identifier.
        """
        query = (
            select(AreaTableDto)
            .where(
                AreaTableDto.project_id == project_id,
                AreaTableDto.organization_id == organization_id,
                AreaTableDto.deleted_at.is_(None),
            )
            .order_by(AreaTableDto.area_id.asc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def createProject(self, project: ProjectTableDto) -> ProjectTableDto:
        """Persists a new project entity.

        Args:
            project (ProjectTableDto): Project entity ready for insertion.

        Returns:
            ProjectTableDto: Flushed project entity with its primary key.
        """
        self.db_session.add(project)
        await self.db_session.flush()
        await self.db_session.refresh(project)
        return project

    async def createArea(self, area: AreaTableDto) -> AreaTableDto:
        """Persists a new area entity.

        Args:
            area (AreaTableDto): Area entity ready for insertion.

        Returns:
            AreaTableDto: Flushed area entity with its primary key.
        """
        self.db_session.add(area)
        await self.db_session.flush()
        await self.db_session.refresh(area)
        return area
