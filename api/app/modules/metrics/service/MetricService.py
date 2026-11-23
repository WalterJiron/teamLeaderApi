from datetime import datetime
from app.common.exceptions.AppExceptions import BadRequestException
from app.common.utils.StateHashHelper import StateHashHelper
from app.modules.metrics.MetricRepository import MetricRepository
from app.modules.metrics.dto.AreaSnapshotTableDto import AreaSnapshotTableDto
from app.modules.metrics.schemas.AreaSnapshotSchema import AreaSnapshotResponse
from app.modules.metrics.utils.DeadlineCalculator import DeadlineCalculator


class MetricService:

    def __init__(self, metric_repository: MetricRepository) -> None:
        """Initializes the metric service with its repository.

        Args:
            metric_repository (MetricRepository): Area snapshot persistence repository.
        """
        self.metric_repository = metric_repository

    def _validateTaskCounts(
        self,
        total_tasks: int,
        completed_tasks: int,
        blocked_tasks: int,
    ) -> None:
        """Validates normalized task counts before computing metrics.

        Args:
            total_tasks (int): Total normalized tasks in the area.
            completed_tasks (int): Closed tasks in the area.
            blocked_tasks (int): Tasks carrying the configured blocked label.

        Raises:
            BadRequestException: If any count is negative or exceeds the total.
        """
        if total_tasks < 0 or completed_tasks < 0 or blocked_tasks < 0:
            raise BadRequestException(detail="Task counts cannot be negative.")
        if completed_tasks > total_tasks or blocked_tasks > total_tasks:
            raise BadRequestException(detail="Completed and blocked task counts cannot exceed the total.")

    async def createAreaSnapshot(
        self,
        organization_id: int,
        project_id: int,
        area_id: int,
        total_tasks: int,
        completed_tasks: int,
        blocked_tasks: int,
        deadline: datetime | None,
        reference_time: datetime | None = None,
    ) -> AreaSnapshotResponse:
        """Computes and persists a deterministic area snapshot.

        Args:
            organization_id (int): Tenant identifier.
            project_id (int): Project identifier.
            area_id (int): Area identifier.
            total_tasks (int): Total normalized tasks in the area.
            completed_tasks (int): Closed tasks in the area.
            blocked_tasks (int): Tasks carrying the configured blocked label.
            deadline (datetime | None): Area deadline used for schedule calculations.
            reference_time (datetime | None, optional): Calculation instant. Defaults to None.

        Returns:
            AreaSnapshotResponse: Persisted deterministic snapshot.

        Raises:
            BadRequestException: If the normalized task counts are inconsistent.
        """
        self._validateTaskCounts(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            blocked_tasks=blocked_tasks,
        )
        captured_at = DeadlineCalculator.normalizeReferenceTime(reference_time)
        remaining_days = DeadlineCalculator.calculateRemainingDays(
            deadline=deadline,
            reference_time=captured_at,
        )
        deadline_probability = DeadlineCalculator.calculateDeadlineProbability(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            blocked_tasks=blocked_tasks,
            remaining_days=remaining_days,
        )
        health_status = DeadlineCalculator.resolveHealthStatus(
            deadline_probability=deadline_probability,
            remaining_days=remaining_days,
        )
        state_hash = StateHashHelper.buildSnapshotHash(
            DeadlineCalculator.buildStatePayload(
                area_id=area_id,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                blocked_tasks=blocked_tasks,
                remaining_days=remaining_days,
                deadline_probability=deadline_probability,
                health_status=health_status,
            )
        )
        snapshot = AreaSnapshotTableDto(
            organization_id=organization_id,
            project_id=project_id,
            area_id=area_id,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            blocked_tasks=blocked_tasks,
            remaining_days=remaining_days,
            deadline_probability=deadline_probability,
            health_status=health_status,
            state_hash=state_hash,
            captured_at=captured_at,
        )
        saved_snapshot = await self.metric_repository.createSnapshot(snapshot=snapshot)
        return AreaSnapshotResponse.model_validate(saved_snapshot)

    async def getLatestSnapshot(
        self,
        area_id: int,
        organization_id: int,
    ) -> AreaSnapshotResponse | None:
        """Fetches the latest persisted snapshot for an area.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            AreaSnapshotResponse | None: Latest snapshot or None when absent.
        """
        snapshot = await self.metric_repository.getLatestSnapshot(
            area_id=area_id,
            organization_id=organization_id,
        )
        if snapshot is None:
            return None
        return AreaSnapshotResponse.model_validate(snapshot)

    async def listAreaSnapshots(
        self,
        area_id: int,
        organization_id: int,
        page: int,
        limit: int,
    ) -> tuple[list[AreaSnapshotResponse], int]:
        """Lists persisted snapshots for an area with pagination.

        Args:
            area_id (int): Area identifier.
            organization_id (int): Tenant identifier used for isolation.
            page (int): One-based page number.
            limit (int): Page size.

        Returns:
            tuple[list[AreaSnapshotResponse], int]: Snapshots and total count.
        """
        offset = (page - 1) * limit
        snapshots = await self.metric_repository.listSnapshotsByArea(
            area_id=area_id,
            organization_id=organization_id,
            offset=offset,
            limit=limit,
        )
        total = await self.metric_repository.countSnapshotsByArea(
            area_id=area_id,
            organization_id=organization_id,
        )
        return [AreaSnapshotResponse.model_validate(snapshot) for snapshot in snapshots], total
