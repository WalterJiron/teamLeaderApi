from app.modules.metrics.schemas.DelayRiskSchema import (
    DelayRiskAssessmentRequestSchema,
    DelayRiskAssessmentResponseSchema,
    MemberPendingResponseSchema,
    MemberPendingSchema,
    ProductivityAssessmentSchema,
    TeamRecommendationSchema,
)


class DelayRiskCalculator:

    @staticmethod
    def resolveRisk(
        request: DelayRiskAssessmentRequestSchema,
    ) -> DelayRiskAssessmentResponseSchema:
        """Evaluates normalized task data and returns an AI-ready team assessment.

        Args:
            request (DelayRiskAssessmentRequestSchema): Normalized Jira project values.

        Returns:
            DelayRiskAssessmentResponseSchema: Risk, team, productivity, and actions.
        """
        total_tasks = request.total_tasks
        unresolved_tasks = request.unresolved_tasks
        remaining_days = request.remaining_days
        unresolved_ratio = (
            round(unresolved_tasks / total_tasks, 4) if total_tasks > 0 else 0.0
        )
        member_with_most_pending = None
        if request.members:
            member_with_most_pending = DelayRiskCalculator._buildMemberResponse(
                max(request.members, key=lambda member: member.unresolved_tasks)
            )

        member_with_most_tasks = None
        member_task_count_basis = None
        if request.members:
            has_assignment_counts = all(
                member.assigned_tasks is not None for member in request.members
            )
            member_with_most_tasks = max(
                request.members,
                key=lambda member: (
                    member.assigned_tasks
                    if has_assignment_counts
                    else member.unresolved_tasks
                ),
            )
            member_task_count_basis = (
                "assigned_tasks" if has_assignment_counts else "unresolved_tasks"
            )
            member_with_most_tasks = DelayRiskCalculator._buildMemberResponse(
                member_with_most_tasks
            )

        productivity = DelayRiskCalculator._assessProductivity(request)
        team_recommendations = DelayRiskCalculator._buildTeamRecommendations(
            request=request,
            productivity=productivity,
        )

        deadline_is_imminent = remaining_days is not None and remaining_days < 2
        majority_unresolved = total_tasks > 0 and unresolved_tasks > total_tasks / 2
        at_least_half_unresolved = (
            total_tasks > 0 and unresolved_tasks >= total_tasks / 2
        )
        if unresolved_tasks == 0:
            risk_level = "LOW"
            reason = "There are no unresolved Jira tasks."
            recommended_action = (
                "Maintain the current delivery pace and continue monitoring."
            )
        elif majority_unresolved and deadline_is_imminent:
            risk_level = "HIGH"
            reason = (
                "More than half of the Jira tasks are unresolved and fewer than two "
                "days remain before delivery."
            )
            recommended_action = (
                "Schedule an immediate team meeting and agree on a recovery plan."
            )
        elif 1 <= unresolved_tasks <= 3 and total_tasks > 8:
            risk_level = "LOW"
            reason = (
                "Only 1 to 3 Jira tasks remain unresolved and the project has more "
                "than 8 tasks."
            )
            recommended_action = (
                "Monitor the remaining tasks and preserve the current delivery pace."
            )
        elif 4 <= unresolved_tasks <= 6 and total_tasks > 12:
            risk_level = "LOW_MEDIUM"
            reason = (
                "Four to six Jira tasks remain unresolved and the project has more "
                "than 12 tasks."
            )
            recommended_action = (
                "Take preventive action now to avoid the delay becoming more likely."
            )
        elif majority_unresolved:
            risk_level = "MEDIUM_HIGH"
            reason = "More than half of the assigned Jira tasks remain unresolved."
            if member_with_most_pending is not None:
                recommended_action = (
                    f"Contact {member_with_most_pending.member_name}, who has the most "
                    "unresolved tasks, and redistribute or unblock the work."
                )
            else:
                recommended_action = (
                    "Identify the member with the most unresolved tasks and take "
                    "recovery actions."
                )
        elif at_least_half_unresolved:
            risk_level = "MEDIUM"
            reason = "Half of the assigned Jira tasks remain unresolved."
            recommended_action = (
                "Take actions now before the delay becomes more likely."
            )
        else:
            risk_level = "LOW"
            reason = (
                "The unresolved Jira task count does not yet meet a higher risk threshold."
            )
            recommended_action = (
                "Continue monitoring the project and unresolved tasks."
            )

        agent_message = DelayRiskCalculator._buildAgentMessage(
            risk_level=risk_level,
            reason=reason,
            recommended_action=recommended_action,
            productivity=productivity,
            team_recommendations=team_recommendations,
            member_with_most_tasks=member_with_most_tasks,
        )
        return DelayRiskAssessmentResponseSchema(
            risk_level=risk_level,
            risk_probability=risk_level,
            unresolved_tasks=unresolved_tasks,
            total_tasks=total_tasks,
            unresolved_ratio=unresolved_ratio,
            remaining_days=remaining_days,
            is_immediate=risk_level == "HIGH",
            member_with_most_pending=member_with_most_pending,
            member_with_most_tasks=member_with_most_tasks,
            member_task_count_basis=member_task_count_basis,
            productivity=productivity,
            team_recommendations=team_recommendations,
            reason=reason,
            recommended_action=recommended_action,
            agent_message=agent_message,
        )

    @staticmethod
    def _buildMemberResponse(
        member: MemberPendingSchema,
    ) -> MemberPendingResponseSchema:
        return MemberPendingResponseSchema(
            member_id=member.member_id,
            member_name=member.member_name,
            role=member.role,
            assigned_tasks=member.assigned_tasks,
            unresolved_tasks=member.unresolved_tasks,
        )

    @staticmethod
    def _assessProductivity(
        request: DelayRiskAssessmentRequestSchema,
    ) -> ProductivityAssessmentSchema:
        history = request.delivery_history
        current_period = request.current_delivery_period
        if not history or current_period is None:
            return ProductivityAssessmentSchema(
                historical_periods=len(history),
                historical_average_tasks_per_day=None,
                historical_average_days_per_task=None,
                current_tasks_per_day=None,
                is_below_historical_average=None,
                comparison=(
                    "Historical delivery periods and a current period are required "
                    "to compare team productivity."
                ),
            )

        historical_rates = [
            period.tasks_completed / period.period_days for period in history
        ]
        historical_average = sum(historical_rates) / len(historical_rates)
        current_rate = current_period.tasks_completed / current_period.period_days
        if historical_average == 0:
            return ProductivityAssessmentSchema(
                historical_periods=len(history),
                historical_average_tasks_per_day=0.0,
                historical_average_days_per_task=None,
                current_tasks_per_day=round(current_rate, 4),
                is_below_historical_average=None,
                comparison=(
                    "No historical task completions are available to establish "
                    "a productivity baseline."
                ),
            )
        average_days_per_task = (
            1 / historical_average if historical_average > 0 else None
        )
        is_below_average = current_rate < historical_average
        comparison = (
            "Current delivery speed is below the historical team average."
            if is_below_average
            else "Current delivery speed is at or above the historical team average."
        )
        return ProductivityAssessmentSchema(
            historical_periods=len(history),
            historical_average_tasks_per_day=round(historical_average, 4),
            historical_average_days_per_task=(
                round(average_days_per_task, 4)
                if average_days_per_task is not None
                else None
            ),
            current_tasks_per_day=round(current_rate, 4),
            is_below_historical_average=is_below_average,
            comparison=comparison,
        )

    @staticmethod
    def _buildTeamRecommendations(
        request: DelayRiskAssessmentRequestSchema,
        productivity: ProductivityAssessmentSchema,
    ) -> list[TeamRecommendationSchema]:
        recommendations: list[TeamRecommendationSchema] = []
        if len(request.members) > 1:
            pending_counts = [
                member.unresolved_tasks for member in request.members
            ]
            average_pending = sum(pending_counts) / len(pending_counts)
            most_pending_count = max(pending_counts)
            if most_pending_count > average_pending * 1.5:
                overloaded_member = max(
                    request.members,
                    key=lambda member: member.unresolved_tasks,
                )
                below_average_members = [
                    member.member_name
                    for member in request.members
                    if member.unresolved_tasks < average_pending
                ]
                balancing_target = (
                    " Consider redistributing suitable work to "
                    + ", ".join(below_average_members)
                    + "."
                    if below_average_members
                    else ""
                )
                recommendations.append(
                    TeamRecommendationSchema(
                        category="WORKLOAD_IMBALANCE",
                        priority="HIGH",
                        message=(
                            f"{overloaded_member.member_name} has more than 1.5 times "
                            f"the team's average unresolved workload (role: "
                            f"{overloaded_member.role})."
                            f"{balancing_target} Review availability, role, and task "
                            "complexity before reassigning work."
                        ),
                    )
                )

        if productivity.is_below_historical_average is True:
            recommendations.append(
                TeamRecommendationSchema(
                    category="PRODUCTIVITY",
                    priority="MEDIUM",
                    message=(
                        "Current team delivery speed is below its historical average. "
                        "Review blockers, scope changes, and workload distribution "
                        "before changing individual expectations."
                    ),
                )
            )
        return recommendations

    @staticmethod
    def _buildAgentMessage(
        risk_level: str,
        reason: str,
        recommended_action: str,
        productivity: ProductivityAssessmentSchema,
        team_recommendations: list[TeamRecommendationSchema],
        member_with_most_tasks: MemberPendingResponseSchema | None,
    ) -> str:
        parts = [
            f"Delay risk: {risk_level}.",
            reason,
            f"Recommended action: {recommended_action}",
            productivity.comparison,
        ]
        if member_with_most_tasks is not None:
            if member_with_most_tasks.assigned_tasks is not None:
                task_count = member_with_most_tasks.assigned_tasks
                count_basis = "assigned tasks"
            else:
                task_count = member_with_most_tasks.unresolved_tasks
                count_basis = "unresolved tasks"
            parts.append(
                f"Member with the most tasks: {member_with_most_tasks.member_name} "
                f"(role: {member_with_most_tasks.role}; "
                f"{count_basis}: {task_count})."
            )
        parts.extend(
            recommendation.message for recommendation in team_recommendations
        )
        return " ".join(parts)
