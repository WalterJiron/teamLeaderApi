from datetime import datetime, timezone
from typing import Any


class DeadlineCalculator:

    OPTIMAL_THRESHOLD: float = 70.0
    AT_RISK_THRESHOLD: float = 40.0
    BLOCKED_PENALTY_WEIGHT: float = 20.0

    @staticmethod
    def normalizeReferenceTime(reference_time: datetime | None = None) -> datetime:
        """Normalizes an optional reference time to a timezone-aware UTC value.

        Args:
            reference_time (datetime | None, optional): Reference instant. Defaults to None.

        Returns:
            datetime: Timezone-aware UTC reference instant.
        """
        if reference_time is None:
            return datetime.now(timezone.utc)
        if reference_time.tzinfo is None:
            return reference_time.replace(tzinfo=timezone.utc)
        return reference_time.astimezone(timezone.utc)

    @staticmethod
    def calculateRemainingDays(
        deadline: datetime | None,
        reference_time: datetime | None = None,
    ) -> int:
        """Calculates the whole remaining days until an area deadline.

        Args:
            deadline (datetime | None): Area deadline, or None when no deadline is configured.
            reference_time (datetime | None, optional): Calculation instant. Defaults to None.

        Returns:
            int: Remaining whole days, negative when the deadline has passed, or 0 when no deadline exists.
        """
        if deadline is None:
            return 0
        normalized_now = DeadlineCalculator.normalizeReferenceTime(reference_time)
        normalized_deadline = deadline
        if normalized_deadline.tzinfo is None:
            normalized_deadline = normalized_deadline.replace(tzinfo=timezone.utc)
        else:
            normalized_deadline = normalized_deadline.astimezone(timezone.utc)
        return (normalized_deadline - normalized_now).days

    @staticmethod
    def calculateDeadlineProbability(
        total_tasks: int,
        completed_tasks: int,
        blocked_tasks: int,
        remaining_days: int,
    ) -> float:
        """Computes a deterministic deadline completion probability.

        The probability combines completed work with the available schedule buffer
        and applies a bounded penalty for blocked tasks. A finished area always
        receives 100 percent, while an overdue unfinished area receives 0 percent.

        Args:
            total_tasks (int): Total normalized tasks in the area.
            completed_tasks (int): Closed tasks in the area.
            blocked_tasks (int): Tasks carrying the configured blocked label.
            remaining_days (int): Whole days remaining until the area deadline.

        Returns:
            float: Probability between 0.0 and 100.0 rounded to two decimals.
        """
        if total_tasks <= 0:
            return 100.0 if remaining_days >= 0 else 0.0
        if completed_tasks >= total_tasks:
            return 100.0
        if remaining_days < 0:
            return 0.0

        schedule_buffer = max(remaining_days, 0)
        base_probability = 100.0 * (completed_tasks + schedule_buffer) / (total_tasks + schedule_buffer)
        blocked_penalty = DeadlineCalculator.BLOCKED_PENALTY_WEIGHT * (blocked_tasks / total_tasks)
        probability = max(0.0, min(100.0, base_probability - blocked_penalty))
        return round(probability, 2)

    @staticmethod
    def resolveHealthStatus(deadline_probability: float, remaining_days: int) -> str:
        """Maps a deterministic probability to an operational health status.

        Args:
            deadline_probability (float): Computed deadline completion probability.
            remaining_days (int): Whole days remaining until the area deadline.

        Returns:
            str: Health status value among OPTIMAL, AT_RISK, or CRITICAL.
        """
        if remaining_days < 0 and deadline_probability < 100.0:
            return "CRITICAL"
        if deadline_probability >= DeadlineCalculator.OPTIMAL_THRESHOLD:
            return "OPTIMAL"
        if deadline_probability >= DeadlineCalculator.AT_RISK_THRESHOLD:
            return "AT_RISK"
        return "CRITICAL"

    @staticmethod
    def buildStatePayload(
        area_id: int,
        total_tasks: int,
        completed_tasks: int,
        blocked_tasks: int,
        remaining_days: int,
        deadline_probability: float,
        health_status: str,
    ) -> dict[str, Any]:
        """Builds the canonical payload used to derive a deterministic state hash.

        Args:
            area_id (int): Area identifier.
            total_tasks (int): Total normalized tasks in the area.
            completed_tasks (int): Closed tasks in the area.
            blocked_tasks (int): Tasks carrying the configured blocked label.
            remaining_days (int): Whole days remaining until the area deadline.
            deadline_probability (float): Computed deadline completion probability.
            health_status (str): Resolved operational health status.

        Returns:
            dict[str, Any]: Canonical snapshot payload for hashing and agent caching.
        """
        return {
            "area_id": area_id,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "blocked_tasks": blocked_tasks,
            "remaining_days": remaining_days,
            "deadline_probability": deadline_probability,
            "health_status": health_status,
        }
