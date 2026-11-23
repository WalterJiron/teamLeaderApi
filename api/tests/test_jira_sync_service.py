from datetime import date, datetime, timezone

import pytest

from app.common.exceptions.AppExceptions import ServiceUnavailableException
from app.modules.integrations.service.JiraSyncService import JiraSyncService
from app.modules.metrics.utils.DelayRiskCalculator import DelayRiskCalculator


def _issue(
    key,
    status_category,
    assignee=None,
    resolution=None,
    resolution_date=None,
    due_date=None,
):
    return {
        "key": key,
        "fields": {
            "assignee": assignee,
            "duedate": due_date,
            "resolution": resolution,
            "resolutiondate": resolution_date,
            "status": {
                "statusCategory": {"key": status_category},
            },
        },
    }


def test_jira_issues_are_normalized_into_team_risk_and_weekly_productivity():
    reference_time = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
    assignee = {"accountId": "account-1", "displayName": "Ana"}
    issues = [
        _issue(
            "TEAM-1",
            "indeterminate",
            assignee=assignee,
            due_date="2026-11-27",
        ),
        _issue(
            "TEAM-2",
            "done",
            assignee=assignee,
            resolution={"name": "Done"},
            resolution_date="2026-11-24T11:00:00.000+0000",
        ),
        _issue(
            "TEAM-3",
            "done",
            assignee=assignee,
            resolution={"name": "Done"},
            resolution_date="2026-11-17T11:00:00.000+0000",
        ),
    ]

    request, warnings = JiraSyncService.buildAssessmentRequest(
        issues=issues,
        project_roles={"account-1": ["Developer"]},
        project_deadline=None,
        reference_time=reference_time,
    )

    assert request.total_tasks == 3
    assert request.unresolved_tasks == 1
    assert request.remaining_days == 2
    assert request.members[0].member_name == "Ana"
    assert request.members[0].role == "Developer"
    assert request.members[0].assigned_tasks == 3
    assert sum(period.tasks_completed for period in request.delivery_history) == 1
    assert request.current_delivery_period.tasks_completed == 1
    assert warnings == []


def test_missing_deadlines_and_project_roles_are_returned_as_warnings():
    request, warnings = JiraSyncService.buildAssessmentRequest(
        issues=[
            _issue(
                "TEAM-1",
                "indeterminate",
                assignee={"accountId": "account-1", "displayName": "Ana"},
            )
        ],
        project_roles={},
        project_deadline=None,
        reference_time=datetime(2026, 11, 25, 12, tzinfo=timezone.utc),
    )

    assert request.remaining_days is None
    assert request.members[0].role == JiraSyncService.ROLE_UNAVAILABLE
    assert any("project role" in warning for warning in warnings)
    assert any("deadline" in warning for warning in warnings)
    assert (
        DelayRiskCalculator.resolveRisk(request).is_immediate is False
    )


def test_malformed_jira_issue_data_fails_without_partial_assessment():
    with pytest.raises(ServiceUnavailableException):
        JiraSyncService.buildAssessmentRequest(
            issues=[{"key": "TEAM-1"}],
            project_roles={},
            project_deadline=date(2026, 11, 30),
            reference_time=datetime(2026, 11, 25, 12, tzinfo=timezone.utc),
        )
