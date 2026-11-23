from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.integrations.dto.GithubIntegrationTableDto import GithubIntegrationTableDto
from app.modules.integrations.dto.GithubWebhookDeliveryTableDto import GithubWebhookDeliveryTableDto


class IntegrationRepository:

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the repository with an asynchronous PostgreSQL session.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session.
        """
        self.db_session = db_session

    async def createIntegration(
        self,
        integration: GithubIntegrationTableDto,
    ) -> GithubIntegrationTableDto:
        """Persists a new GitHub repository integration.

        Args:
            integration (GithubIntegrationTableDto): Integration entity ready for insertion.

        Returns:
            GithubIntegrationTableDto: Flushed integration with its primary key.
        """
        self.db_session.add(integration)
        await self.db_session.flush()
        await self.db_session.refresh(integration)
        return integration

    async def getIntegration(self, integration_id: int) -> GithubIntegrationTableDto | None:
        """Fetches a GitHub integration by primary key.

        Args:
            integration_id (int): Integration identifier.

        Returns:
            GithubIntegrationTableDto | None: Matching integration or None when absent.
        """
        query = select(GithubIntegrationTableDto).where(
            GithubIntegrationTableDto.integration_id == integration_id
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getIntegrationForOrganization(
        self,
        integration_id: int,
        organization_id: int,
    ) -> GithubIntegrationTableDto | None:
        """Fetches a GitHub integration scoped to its owning organization.

        Args:
            integration_id (int): Integration identifier.
            organization_id (int): Tenant identifier used for isolation.

        Returns:
            GithubIntegrationTableDto | None: Matching integration or None when absent.
        """
        query = select(GithubIntegrationTableDto).where(
            GithubIntegrationTableDto.integration_id == integration_id,
            GithubIntegrationTableDto.organization_id == organization_id,
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def getIntegrationByRepository(
        self,
        organization_id: int,
        project_id: int,
        repository_owner: str,
        repository_name: str,
    ) -> GithubIntegrationTableDto | None:
        """Fetches an integration by tenant, project, and case-insensitive repository identity.

        Args:
            organization_id (int): Tenant identifier.
            project_id (int): Project identifier.
            repository_owner (str): GitHub repository owner.
            repository_name (str): GitHub repository name.

        Returns:
            GithubIntegrationTableDto | None: Matching integration or None when absent.
        """
        query = select(GithubIntegrationTableDto).where(
            GithubIntegrationTableDto.organization_id == organization_id,
            GithubIntegrationTableDto.project_id == project_id,
            func.lower(GithubIntegrationTableDto.repository_owner) == repository_owner.lower(),
            func.lower(GithubIntegrationTableDto.repository_name) == repository_name.lower(),
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def listIntegrations(
        self,
        organization_id: int,
        offset: int,
        limit: int,
    ) -> list[GithubIntegrationTableDto]:
        """Lists GitHub integrations for a tenant ordered newest first.

        Args:
            organization_id (int): Tenant identifier.
            offset (int): Number of records to skip.
            limit (int): Maximum records to return.

        Returns:
            list[GithubIntegrationTableDto]: Matching integrations.
        """
        query = (
            select(GithubIntegrationTableDto)
            .where(GithubIntegrationTableDto.organization_id == organization_id)
            .order_by(
                GithubIntegrationTableDto.created_at.desc(),
                GithubIntegrationTableDto.integration_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def countIntegrations(self, organization_id: int) -> int:
        """Counts GitHub integrations for a tenant.

        Args:
            organization_id (int): Tenant identifier.

        Returns:
            int: Total matching integrations.
        """
        query = select(func.count(GithubIntegrationTableDto.integration_id)).where(
            GithubIntegrationTableDto.organization_id == organization_id
        )
        result = await self.db_session.execute(query)
        return int(result.scalar_one())

    async def updateLastSyncedAt(
        self,
        integration: GithubIntegrationTableDto,
        synced_at: datetime,
    ) -> GithubIntegrationTableDto:
        """Updates the last successful synchronization timestamp.

        Args:
            integration (GithubIntegrationTableDto): Persisted integration entity.
            synced_at (datetime): Successful synchronization instant.

        Returns:
            GithubIntegrationTableDto: Refreshed integration entity.
        """
        integration.last_synced_at = synced_at
        await self.db_session.flush()
        await self.db_session.refresh(integration)
        return integration

    async def recordDelivery(
        self,
        delivery_id: str,
        integration_id: int,
        event_type: str,
    ) -> bool:
        """Atomically records a webhook delivery identifier for replay protection.

        Args:
            delivery_id (str): GitHub X-GitHub-Delivery identifier.
            integration_id (int): Targeted integration identifier.
            event_type (str): GitHub event type.

        Returns:
            bool: True when the delivery was recorded, False when it already existed.
        """
        statement = (
            postgres_insert(GithubWebhookDeliveryTableDto)
            .values(
                delivery_id=delivery_id,
                integration_id=integration_id,
                event_type=event_type,
            )
            .on_conflict_do_nothing(index_elements=["delivery_id"])
            .returning(GithubWebhookDeliveryTableDto.id)
        )
        result = await self.db_session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def getDeliveryByDeliveryId(
        self,
        delivery_id: str,
    ) -> GithubWebhookDeliveryTableDto | None:
        """Fetches a recorded webhook delivery by identifier.

        Args:
            delivery_id (str): GitHub X-GitHub-Delivery identifier.

        Returns:
            GithubWebhookDeliveryTableDto | None: Matching delivery or None when absent.
        """
        query = select(GithubWebhookDeliveryTableDto).where(
            GithubWebhookDeliveryTableDto.delivery_id == delivery_id
        )
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()
