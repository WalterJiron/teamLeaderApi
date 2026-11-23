from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy.exc import IntegrityError

from app.common.exceptions.AppExceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ServiceUnavailableException,
)
from app.modules.integrations.JiraIntegrationRepository import JiraIntegrationRepository
from app.modules.integrations.client.JiraApiClient import JiraApiClient
from app.modules.integrations.dto.JiraIntegrationTableDto import JiraIntegrationTableDto
from app.modules.integrations.schemas.JiraIntegrationSchema import (
    JiraIntegrationCreateSchema,
    JiraIntegrationResponseSchema,
    JiraSyncResponseSchema,
)
from app.modules.integrations.utils.SecretEncryptionHelper import SecretEncryptionHelper
from app.modules.metrics.schemas.DelayRiskSchema import (
    CurrentDeliveryPeriodSchema,
    DelayRiskAssessmentRequestSchema,
    DeliveryPeriodSchema,
    MemberPendingSchema,
)
from app.modules.metrics.utils.DelayRiskCalculator import DelayRiskCalculator
from app.modules.projects.ProjectRepository import ProjectRepository


class JiraSyncService:

    PRODUCTIVITY_HISTORY_WEEKS = 12
    ROLE_UNAVAILABLE = "Jira project role unavailable"

    def __init__(
        self,
        integration_repository: JiraIntegrationRepository,
        project_repository: ProjectRepository,
        secret_encryption_helper: SecretEncryptionHelper,
    ) -> None:
        self.integration_repository = integration_repository
        self.project_repository = project_repository
        self.secret_encryption_helper = secret_encryption_helper

    def _buildResponse(
        self,
        integration: JiraIntegrationTableDto,
    ) -> JiraIntegrationResponseSchema:
        return JiraIntegrationResponseSchema(
            integration_id=integration.integration_id,
            organization_id=integration.organization_id,
            project_id=integration.project_id,
            jira_base_url=integration.jira_base_url,
            jira_project_key=integration.jira_project_key,
            jira_project_name=integration.jira_project_name,
            jira_email=integration.jira_email,
            project_deadline=integration.project_deadline,
            is_active=integration.is_active,
            last_synced_at=integration.last_synced_at,
            created_at=integration.created_at,
            masked_api_token="****",
        )

    async def registerIntegration(
        self,
        organization_id: int,
        payload: JiraIntegrationCreateSchema,
    ) -> JiraIntegrationResponseSchema:
        project = await self.project_repository.getProject(
            project_id=payload.project_id,
            organization_id=organization_id,
        )
        if project is None:
            raise NotFoundException(detail="Internal project not found.")

        existing_project = await self.integration_repository.getIntegrationByInternalProject(
            project_id=payload.project_id,
            organization_id=organization_id,
        )
        if existing_project is not None:
            raise ConflictException(
                detail="The internal project already has a Jira integration."
            )

        existing_jira_project = await self.integration_repository.getIntegrationByJiraProject(
            jira_base_url=payload.jira_base_url,
            jira_project_key=payload.jira_project_key,
            organization_id=organization_id,
        )
        if existing_jira_project is not None:
            raise ConflictException(
                detail="This Jira project is already connected to the organization."
            )

        jira_client = JiraApiClient(base_url=payload.jira_base_url)
        project_metadata = await jira_client.verifyProjectAccess(
            project_key=payload.jira_project_key,
            jira_email=str(payload.jira_email),
            api_token=payload.api_token.get_secret_value(),
        )
        integration = JiraIntegrationTableDto(
            organization_id=organization_id,
            project_id=payload.project_id,
            jira_base_url=payload.jira_base_url,
            jira_project_key=project_metadata["project_key"],
            jira_project_name=project_metadata["project_name"],
            jira_email=str(payload.jira_email),
            encrypted_api_token=self.secret_encryption_helper.encryptSecret(
                payload.api_token.get_secret_value()
            ),
            project_deadline=payload.project_deadline,
            is_active=True,
        )
        try:
            saved_integration = await self.integration_repository.createIntegration(
                integration
            )
        except IntegrityError as exc:
            raise ConflictException(
                detail="This internal or Jira project is already connected."
            ) from exc
        return self._buildResponse(saved_integration)

    async def listIntegrations(
        self,
        organization_id: int,
        page: int,
        limit: int,
    ) -> tuple[list[JiraIntegrationResponseSchema], int]:
        offset = (page - 1) * limit
        integrations = await self.integration_repository.listIntegrations(
            organization_id=organization_id,
            offset=offset,
            limit=limit,
        )
        total = await self.integration_repository.countIntegrations(
            organization_id=organization_id
        )
        return [self._buildResponse(item) for item in integrations], total

    async def syncIntegration(
        self,
        integration_id: int,
        organization_id: int,
        reference_time: datetime | None = None,
    ) -> JiraSyncResponseSchema:
        integration = await self.integration_repository.getIntegrationForOrganization(
            integration_id=integration_id,
            organization_id=organization_id,
        )
        if integration is None:
            raise NotFoundException(detail="Jira integration not found.")
        if not integration.is_active:
            raise BadRequestException(detail="Jira integration is inactive.")
        try:
            api_token = self.secret_encryption_helper.decryptSecret(
                integration.encrypted_api_token
            )
        except ValueError as exc:
            raise ServiceUnavailableException(
                detail="Stored Jira credentials could not be decrypted."
            ) from exc

        synced_at = reference_time or datetime.now(timezone.utc)
        jira_client = JiraApiClient(base_url=integration.jira_base_url)
        issues = await jira_client.fetchProjectIssues(
            project_key=integration.jira_project_key,
            jira_email=integration.jira_email,
            api_token=api_token,
        )
        project_roles, roles_available = await jira_client.fetchProjectRoles(
            project_key=integration.jira_project_key,
            jira_email=integration.jira_email,
            api_token=api_token,
        )
        assessment_request, warnings = self.buildAssessmentRequest(
            issues=issues,
            project_roles=project_roles,
            project_deadline=integration.project_deadline,
            reference_time=synced_at,
        )
        if not roles_available:
            warnings.append(
                "Jira project roles could not be read; assigned users are marked "
                f"'{self.ROLE_UNAVAILABLE}'. Grant the API account project-role access "
                "to include roles."
            )

        assessment = DelayRiskCalculator.resolveRisk(assessment_request)
        await self.integration_repository.updateLastSyncedAt(
            integration=integration,
            synced_at=synced_at,
        )
        return JiraSyncResponseSchema(
            integration_id=integration.integration_id,
            internal_project_id=integration.project_id,
            jira_project_key=integration.jira_project_key,
            synced_at=synced_at,
            assessment=assessment,
            warnings=warnings,
        )

    @classmethod
    def buildAssessmentRequest(
        cls,
        issues: list[dict],
        project_roles: dict[str, list[str]],
        project_deadline: date | None,
        reference_time: datetime,
    ) -> tuple[DelayRiskAssessmentRequestSchema, list[str]]:
        """Maps Jira issues into the normalized team and productivity metrics.

        Args:
            issues (list[dict]): Complete project issue list from Jira.
            project_roles (dict[str, list[str]]): Account id to project roles map.
            project_deadline (date | None): Configured project deadline.
            reference_time (datetime): Stable UTC instant for this assessment.

        Returns:
            tuple[DelayRiskAssessmentRequestSchema, list[str]]: Assessment data and warnings.
        """
        normalized_now = cls._normalizeReferenceTime(reference_time)
        unresolved_count = 0
        due_dates: list[date] = []
        member_counts: dict[str, dict[str, object]] = {}
        resolution_dates: list[datetime] = []
        warnings: list[str] = []
        issues_without_account_id = False
        completed_issues_without_resolution_date = 0

        for issue in issues:
            fields = issue.get("fields")
            if not isinstance(fields, dict):
                raise ServiceUnavailableException(
                    detail="Jira returned an issue without its fields."
                )
            status = fields.get("status")
            status_category = (
                status.get("statusCategory")
                if isinstance(status, dict)
                else None
            )
            category_key = (
                status_category.get("key")
                if isinstance(status_category, dict)
                else None
            )
            if not isinstance(category_key, str):
                raise ServiceUnavailableException(
                    detail="Jira returned an issue without a valid status category."
                )
            is_resolved = (
                category_key.casefold() == "done"
                or fields.get("resolution") is not None
            )
            if not is_resolved:
                unresolved_count += 1
                due_date = cls._parseDate(fields.get("duedate"))
                if due_date is not None:
                    due_dates.append(due_date)

            assignee = fields.get("assignee")
            if isinstance(assignee, dict):
                account_id = assignee.get("accountId")
                if not isinstance(account_id, str) or not account_id:
                    issues_without_account_id = True
                else:
                    member = member_counts.setdefault(
                        account_id,
                        {
                            "member_id": account_id,
                            "member_name": str(
                                assignee.get("displayName") or account_id
                            )[:160],
                            "assigned_tasks": 0,
                            "unresolved_tasks": 0,
                        },
                    )
                    member["assigned_tasks"] = int(member["assigned_tasks"]) + 1
                    if not is_resolved:
                        member["unresolved_tasks"] = int(
                            member["unresolved_tasks"]
                        ) + 1

            if is_resolved:
                resolution_date = cls._parseDateTime(fields.get("resolutiondate"))
                if resolution_date is not None and resolution_date <= normalized_now:
                    resolution_dates.append(resolution_date)
                elif resolution_date is None:
                    completed_issues_without_resolution_date += 1

        if len(member_counts) > 500:
            raise ServiceUnavailableException(
                detail=(
                    "Jira project has more than 500 assigned team members; "
                    "the full team assessment cannot be represented."
                )
            )
        if issues_without_account_id:
            warnings.append(
                "Some assigned Jira issues had no accountId and were excluded "
                "from member-level counts."
            )
        if completed_issues_without_resolution_date:
            warnings.append(
                f"{completed_issues_without_resolution_date} resolved Jira issue(s) "
                "had no resolution date and were excluded from productivity history."
            )

        members: list[MemberPendingSchema] = []
        missing_role_count = 0
        for account_id, counts in sorted(member_counts.items()):
            roles = project_roles.get(account_id, [])
            role = ", ".join(sorted(set(roles))) if roles else cls.ROLE_UNAVAILABLE
            if not roles:
                missing_role_count += 1
            members.append(
                MemberPendingSchema(
                    member_id=account_id,
                    member_name=str(counts["member_name"]),
                    role=role[:120],
                    assigned_tasks=int(counts["assigned_tasks"]),
                    unresolved_tasks=int(counts["unresolved_tasks"]),
                )
            )
        if missing_role_count:
            warnings.append(
                f"Jira returned no project role for {missing_role_count} assigned user(s); "
                f"they are marked '{cls.ROLE_UNAVAILABLE}'."
            )

        utc_today = normalized_now.date()
        current_week_start = utc_today - timedelta(days=utc_today.weekday())
        history_start = current_week_start - timedelta(
            weeks=cls.PRODUCTIVITY_HISTORY_WEEKS
        )
        history_counts = [0] * cls.PRODUCTIVITY_HISTORY_WEEKS
        current_week_completions = 0
        for resolution_date in resolution_dates:
            resolved_day = resolution_date.date()
            if history_start <= resolved_day < current_week_start:
                week_index = (resolved_day - history_start).days // 7
                history_counts[week_index] += 1
            elif current_week_start <= resolved_day <= utc_today:
                current_week_completions += 1

        delivery_history = [
            DeliveryPeriodSchema(tasks_completed=count, period_days=7)
            for count in history_counts
        ]
        week_start_time = datetime.combine(
            current_week_start,
            time.min,
            tzinfo=timezone.utc,
        )
        elapsed_week_days = max(
            (normalized_now - week_start_time).total_seconds() / 86400,
            1 / 24,
        )
        current_delivery_period = CurrentDeliveryPeriodSchema(
            tasks_completed=current_week_completions,
            period_days=elapsed_week_days,
        )

        deadline = project_deadline or (min(due_dates) if due_dates else None)
        remaining_days = (deadline - utc_today).days if deadline else None
        if deadline is None:
            warnings.append(
                "No project deadline or unresolved Jira issue due date is available; "
                "the imminent-deadline risk rule cannot be evaluated."
            )

        request = DelayRiskAssessmentRequestSchema(
            total_tasks=len(issues),
            unresolved_tasks=unresolved_count,
            remaining_days=remaining_days,
            members=members,
            delivery_history=delivery_history,
            current_delivery_period=current_delivery_period,
        )
        return request, warnings

    @staticmethod
    def _normalizeReferenceTime(reference_time: datetime) -> datetime:
        if reference_time.tzinfo is None:
            return reference_time.replace(tzinfo=timezone.utc)
        return reference_time.astimezone(timezone.utc)

    @staticmethod
    def _parseDate(value: object) -> date | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ServiceUnavailableException(
                detail="Jira returned an invalid issue due date."
            )
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ServiceUnavailableException(
                detail="Jira returned an invalid issue due date."
            ) from exc

    @staticmethod
    def _parseDateTime(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ServiceUnavailableException(
                detail="Jira returned an invalid issue resolution date."
            )
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ServiceUnavailableException(
                detail="Jira returned an invalid issue resolution date."
            ) from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
