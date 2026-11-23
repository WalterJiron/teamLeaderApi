from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.PostgresManager import PostgresManager
from app.core.dependencies.MetricDependencies import getMetricRepository
from app.modules.agent.AgentRepository import AgentRepository
from app.modules.agent.client.N8nAgentClient import N8nAgentClient
from app.modules.agent.service.AgentService import AgentService
from app.modules.metrics.MetricRepository import MetricRepository


def getAgentRepository(
    db_session: AsyncSession = Depends(PostgresManager.getSession),
) -> AgentRepository:
    """Provides an AgentRepository bound to PostgreSQL and MongoDB.

    Args:
        db_session (AsyncSession): Active PostgreSQL session.

    Returns:
        AgentRepository: Agent cache and memory persistence repository.
    """
    return AgentRepository(db_session=db_session)


def getN8nAgentClient() -> N8nAgentClient:
    """Provides an HTTP client configured for n8n AI agent webhook calls.

    Returns:
        N8nAgentClient: n8n agent chat client.
    """
    return N8nAgentClient()


def getAgentService(
    agent_repository: AgentRepository = Depends(getAgentRepository),
    n8n_agent_client: N8nAgentClient = Depends(getN8nAgentClient),
    metric_repository: MetricRepository = Depends(getMetricRepository),
) -> AgentService:
    """Provides an AgentService with injected repository, n8n client, and metrics.

    Args:
        agent_repository (AgentRepository): Injected agent cache and memory repository.
        n8n_agent_client (N8nAgentClient): Injected n8n chat client.
        metric_repository (MetricRepository): Injected metric snapshot repository.

    Returns:
        AgentService: AI agent service with state-hash caching and conversation memory.
    """
    return AgentService(
        agent_repository=agent_repository,
        n8n_agent_client=n8n_agent_client,
        metric_repository=metric_repository,
    )
