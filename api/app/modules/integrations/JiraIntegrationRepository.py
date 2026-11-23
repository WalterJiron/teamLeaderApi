from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.dto.JiraIntegrationTableDto import JiraIntegrationTableDto


class JiraIntegrationRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def createIntegration(
        self,
        integration: JiraIntegrationTableDto,
    ) -> JiraIntegrationTableDto:
        self.db_session.add(integration)
        await self.db_session.flush()
        await self.db_session.refresh(integration)
        return integration

    async def getIntegrationForOrganization(
        self,
        integration_id: int,
        organization_id: int,
    ) -> JiraIntegrationTableDto | None:
        query = select(JiraIntegrationTableDto).where(
            JiraIntegrationTableDto.integration_id == integration_id,
            JiraIntegrationTableDto.organization_id == organization_id,
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getIntegrationByInternalProject(
        self,
        project_id: int,
        organization_id: int,
    ) -> JiraIntegrationTableDto | None:
        query = select(JiraIntegrationTableDto).where(
            JiraIntegrationTableDto.project_id == project_id,
            JiraIntegrationTableDto.organization_id == organization_id,
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getIntegrationByJiraProject(
        self,
        jira_base_url: str,
        jira_project_key: str,
        organization_id: int,
    ) -> JiraIntegrationTableDto | None:
        query = select(JiraIntegrationTableDto).where(
            JiraIntegrationTableDto.organization_id == organization_id,
            func.lower(JiraIntegrationTableDto.jira_base_url) == jira_base_url.lower(),
            func.lower(JiraIntegrationTableDto.jira_project_key)
            == jira_project_key.lower(),
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def listIntegrations(
        self,
        organization_id: int,
        offset: int,
        limit: int,
    ) -> list[JiraIntegrationTableDto]:
        query = (
            select(JiraIntegrationTableDto)
            .where(JiraIntegrationTableDto.organization_id == organization_id)
            .order_by(
                JiraIntegrationTableDto.created_at.desc(),
                JiraIntegrationTableDto.integration_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countIntegrations(self, organization_id: int) -> int:
        query = select(func.count(JiraIntegrationTableDto.integration_id)).where(
            JiraIntegrationTableDto.organization_id == organization_id
        )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())

    async def updateLastSyncedAt(
        self,
        integration: JiraIntegrationTableDto,
        synced_at: datetime,
    ) -> JiraIntegrationTableDto:
        integration.last_synced_at = synced_at
        await self.db_session.flush()
        await self.db_session.refresh(integration)
        return integration
