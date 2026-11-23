import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.metrics.schemas.DelayRiskSchema import (
    CurrentDeliveryPeriodSchema,
    DelayRiskAssessmentRequestSchema,
    DeliveryPeriodSchema,
    MemberPendingSchema,
)
from app.modules.metrics.utils.DelayRiskCalculator import DelayRiskCalculator


def test_low_risk_with_few_unresolved_tasks():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=2,
        remaining_days=5,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "LOW"
    assert result.is_immediate is False


def test_low_medium_risk_with_four_to_six_pending_and_large_total():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=20,
        unresolved_tasks=5,
        remaining_days=8,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "LOW_MEDIUM"


def test_medium_risk_for_exact_half():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=12,
        unresolved_tasks=6,
        remaining_days=10,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "MEDIUM"


def test_medium_high_risk_identifies_member_with_most_pending():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=7,
        remaining_days=5,
        members=[
            MemberPendingSchema(
                member_name="Ana", role="Developer", unresolved_tasks=2
            ),
            MemberPendingSchema(member_name="Luis", role="QA", unresolved_tasks=5),
        ],
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "MEDIUM_HIGH"
    assert result.member_with_most_pending.member_name == "Luis"


def test_high_risk_when_more_than_half_unresolved_and_deadline_under_two_days():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=8,
        remaining_days=1,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "HIGH"
    assert result.is_immediate is True


def test_exactly_half_unresolved_near_deadline_is_medium_not_high():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=5,
        remaining_days=1,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "MEDIUM"
    assert result.is_immediate is False


def test_more_than_half_unresolved_at_two_days_is_not_immediate_high():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=8,
        remaining_days=2,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.risk_level == "MEDIUM_HIGH"
    assert result.is_immediate is False


def test_identifies_most_assigned_member_and_role_separately_from_pending_lead():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=12,
        unresolved_tasks=6,
        remaining_days=8,
        members=[
            MemberPendingSchema(
                member_id="ana",
                member_name="Ana",
                role="QA",
                assigned_tasks=7,
                unresolved_tasks=1,
            ),
            MemberPendingSchema(
                member_id="luis",
                member_name="Luis",
                role="Developer",
                assigned_tasks=5,
                unresolved_tasks=5,
            ),
        ],
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.member_with_most_tasks.member_name == "Ana"
    assert result.member_with_most_tasks.role == "QA"
    assert result.member_with_most_pending.member_name == "Luis"
    assert "Member with the most tasks: Ana (role: QA" in result.agent_message
    assert any(
        recommendation.category == "WORKLOAD_IMBALANCE"
        for recommendation in result.team_recommendations
    )


def test_compares_current_team_rate_to_mean_of_delivery_period_rates():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=20,
        unresolved_tasks=5,
        remaining_days=8,
        delivery_history=[
            DeliveryPeriodSchema(tasks_completed=4, period_days=4),
            DeliveryPeriodSchema(tasks_completed=10, period_days=5),
        ],
        current_delivery_period=CurrentDeliveryPeriodSchema(
            tasks_completed=2,
            period_days=2,
        ),
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.productivity.historical_average_tasks_per_day == 1.5
    assert result.productivity.historical_average_days_per_task == 0.6667
    assert result.productivity.current_tasks_per_day == 1.0
    assert result.productivity.is_below_historical_average is True
    assert any(
        recommendation.category == "PRODUCTIVITY"
        for recommendation in result.team_recommendations
    )


def test_productivity_equal_to_historical_mean_is_not_below_average():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=2,
        remaining_days=6,
        delivery_history=[
            DeliveryPeriodSchema(tasks_completed=4, period_days=2),
        ],
        current_delivery_period=CurrentDeliveryPeriodSchema(
            tasks_completed=6,
            period_days=3,
        ),
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.productivity.is_below_historical_average is False


def test_workload_at_exactly_one_and_a_half_times_average_is_not_flagged():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=4,
        remaining_days=5,
        members=[
            MemberPendingSchema(
                member_name="Ana",
                role="Developer",
                unresolved_tasks=3,
            ),
            MemberPendingSchema(
                member_name="Luis",
                role="QA",
                unresolved_tasks=1,
            ),
        ],
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert not any(
        recommendation.category == "WORKLOAD_IMBALANCE"
        for recommendation in result.team_recommendations
    )


def test_productivity_is_unknown_without_both_history_and_current_period():
    request = DelayRiskAssessmentRequestSchema(
        total_tasks=10,
        unresolved_tasks=2,
        remaining_days=6,
    )
    result = DelayRiskCalculator.resolveRisk(request)
    assert result.productivity.is_below_historical_average is None
    assert result.productivity.historical_average_tasks_per_day is None


def test_member_pending_count_cannot_exceed_assigned_count():
    with pytest.raises(ValueError, match="unresolved tasks cannot exceed"):
        DelayRiskAssessmentRequestSchema(
            total_tasks=8,
            unresolved_tasks=4,
            remaining_days=3,
            members=[
                MemberPendingSchema(
                    member_name="Ana",
                    role="QA",
                    assigned_tasks=2,
                    unresolved_tasks=3,
                )
            ],
        )
