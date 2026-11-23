from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.metrics.dto.AreaSnapshotTableDto import AreaSnapshotTableDto


class MetricRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def createSnapshot(self, snapshot: AreaSnapshotTableDto) -> AreaSnapshotTableDto:
        """Persists a deterministic area snapshot.

        Args:
            snapshot (AreaSnapshotTableDto): Snapshot entity ready for insertion.

        Returns:
            AreaSnapshotTableDto: Flushed snapshot entity with its primary key.
        """
        self.db_session.add(snapshot)
        await self.db_session.flush()
        await self.db_session.refresh(snapshot)
        return snapshot

    async def getLatestSnapshot(
        self,
        area_id: int,
        organization_id: int,
    ) -> AreaSnapshotTableDto | None:
        """Fetches the newest snapshot for an area within a tenant.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            AreaSnapshotTableDto | None: Latest snapshot or None when absent.
        """
        query = (
            select(AreaSnapshotTableDto)
            .where(
                AreaSnapshotTableDto.area_id == area_id,
                AreaSnapshotTableDto.organization_id == organization_id,
            )
            .order_by(
                AreaSnapshotTableDto.captured_at.desc(),
                AreaSnapshotTableDto.snapshot_id.desc(),
            )
            .limit(1)
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def listSnapshotsByArea(
        self,
        area_id: int,
        organization_id: int,
        offset: int,
        limit: int,
    ) -> list[AreaSnapshotTableDto]:
        """Lists snapshots for an area within a tenant ordered newest first.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.

        Returns:
            list[AreaSnapshotTableDto]: Matching snapshots.
        """
        query = (
            select(AreaSnapshotTableDto)
            .where(
                AreaSnapshotTableDto.area_id == area_id,
                AreaSnapshotTableDto.organization_id == organization_id,
            )
            .order_by(
                AreaSnapshotTableDto.captured_at.desc(),
                AreaSnapshotTableDto.snapshot_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countSnapshotsByArea(self, area_id: int, organization_id: int) -> int:
        """Counts snapshots for an area within a tenant.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            int: Total matching snapshots.
        """
        query = select(func.count(AreaSnapshotTableDto.snapshot_id)).where(
            AreaSnapshotTableDto.area_id == area_id,
            AreaSnapshotTableDto.organization_id == organization_id,
        )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())
