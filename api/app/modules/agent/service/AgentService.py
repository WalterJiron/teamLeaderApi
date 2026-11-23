import logging
import uuid
from app.modules.agent.AgentRepository import AgentRepository
from app.modules.agent.client.N8nAgentClient import N8nAgentClient
from app.modules.agent.dto.AgentMemoryDoc import AgentMemoryDoc
from app.modules.agent.schemas.AgentSchema import (
    AgentChatResponseSchema,
    AgentMessageResponse,
    AgentSessionSummaryResponse,
)
from app.modules.metrics.MetricRepository import MetricRepository

logger = logging.getLogger(__name__)


class AgentService:

    def __init__(
        self,
        agent_repository: AgentRepository,
        n8n_agent_client: N8nAgentClient,
        metric_repository: MetricRepository | None = None,
    ) -> None:
        """Initializes the agent service with caching repository, n8n client, and metrics.

        Args:
            agent_repository (AgentRepository): Persistence repository for PG cache and Mongo memory.
            n8n_agent_client (N8nAgentClient): HTTP client for the n8n AI agent webhook.
            metric_repository (MetricRepository | None, optional): Injected snapshot repository. Defaults to None.
        """
        self.agent_repository = agent_repository
        self.n8n_agent_client = n8n_agent_client
        self.metric_repository = metric_repository

    async def chat(
        self,
        message: str,
        session_id: str | None,
        user_id: int,
        organization_id: int,
        project_id: int | None = None,
        area_id: int | None = None,
    ) -> AgentChatResponseSchema:
        """Processes a chat message with state-hash cache checks and conversation memory.

        If area_id is provided, checks whether the latest AreaSnapshot state_hash already
        has a cached response in PostgreSQL agent_cache. If state has not changed,
        returns the cached response spending 0 tokens.

        Args:
            message (str): User message.
            session_id (str | None): Conversation session identifier.
            user_id (int): Authenticated user identifier.
            organization_id (int): Tenant identifier.
            project_id (int | None, optional): Project context identifier. Defaults to None.
            area_id (int | None, optional): Area context identifier. Defaults to None.

        Returns:
            AgentChatResponseSchema: Assistant reply with cache metadata and session identifier.
        """
        resolved_session = session_id or f"{organization_id}-{user_id}-{uuid.uuid4().hex[:8]}"

        # 1. Store user message in MongoDB memory
        user_memory = AgentMemoryDoc(
            session_id=resolved_session,
            organization_id=organization_id,
            user_id=user_id,
            role="user",
            content=message,
            project_id=project_id,
            area_id=area_id,
        )
        await self.agent_repository.appendMemory(user_memory)

        # 2. Check hash-based cache if area_id is specified and metric repository is available
        latest_snapshot = None
        if area_id is not None and self.metric_repository is not None:
            latest_snapshot = await self.metric_repository.getLatestSnapshot(
                organization_id=organization_id,
                area_id=area_id,
            )
            if latest_snapshot and latest_snapshot.state_hash:
                cached_reply = await self.agent_repository.getCachedResponse(
                    organization_id=organization_id,
                    area_id=area_id,
                    state_hash=latest_snapshot.state_hash,
                )
                if cached_reply:
                    logger.info(
                        "Agent cache hit for area %s with state_hash %s. 0 tokens spent.",
                        area_id,
                        latest_snapshot.state_hash,
                    )
                    # Persist assistant cached reply in Mongo memory
                    assistant_memory = AgentMemoryDoc(
                        session_id=resolved_session,
                        organization_id=organization_id,
                        user_id=user_id,
                        role="assistant",
                        content=cached_reply,
                        project_id=project_id,
                        area_id=area_id,
                    )
                    await self.agent_repository.appendMemory(assistant_memory)
                    return AgentChatResponseSchema(
                        reply=cached_reply,
                        session_id=resolved_session,
                        cached=True,
                        tokens_spent=0,
                    )

        # 3. Call n8n AI agent workflow
        reply = await self.n8n_agent_client.sendMessage(
            message=message,
            session_id=resolved_session,
            user_id=user_id,
            organization_id=organization_id,
        )

        # 4. Store assistant reply in MongoDB memory
        assistant_memory = AgentMemoryDoc(
            session_id=resolved_session,
            organization_id=organization_id,
            user_id=user_id,
            role="assistant",
            content=reply,
            project_id=project_id,
            area_id=area_id,
        )
        await self.agent_repository.appendMemory(assistant_memory)

        # 5. Cache response in PostgreSQL if area_id and snapshot state_hash exist
        if area_id is not None and latest_snapshot and latest_snapshot.state_hash:
            await self.agent_repository.setCachedResponse(
                organization_id=organization_id,
                area_id=area_id,
                state_hash=latest_snapshot.state_hash,
                response_text=reply,
            )

        return AgentChatResponseSchema(
            reply=reply,
            session_id=resolved_session,
            cached=False,
            tokens_spent=1,
        )

    async def listSessions(
        self,
        organization_id: int,
        user_id: int,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[AgentSessionSummaryResponse], int]:
        """Lists chat conversation sessions for the authenticated user.

        Args:
            organization_id (int): Tenant identifier for isolation.
            user_id (int): Authenticated user identifier.
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size limit. Defaults to 20.

        Returns:
            tuple[list[AgentSessionSummaryResponse], int]: Summarized sessions and total count.
        """
        offset = (page - 1) * limit
        sessions, total = await self.agent_repository.listSessions(
            organization_id=organization_id,
            user_id=user_id,
            offset=offset,
            limit=limit,
        )
        data = [AgentSessionSummaryResponse.model_validate(item) for item in sessions]
        return data, total

    async def getSessionMessages(
        self,
        organization_id: int,
        session_id: str,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[AgentMessageResponse], int]:
        """Retrieves paginated messages of a specific session from MongoDB.

        Args:
            organization_id (int): Tenant identifier for isolation.
            session_id (str): Conversation session identifier.
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size limit. Defaults to 50.

        Returns:
            tuple[list[AgentMessageResponse], int]: Ordered messages and total message count.
        """
        offset = (page - 1) * limit
        messages, total = await self.agent_repository.getSessionMessages(
            organization_id=organization_id,
            session_id=session_id,
            offset=offset,
            limit=limit,
        )
        data = [AgentMessageResponse.model_validate(item) for item in messages]
        return data, total

    async def deleteSession(
        self,
        organization_id: int,
        session_id: str,
    ) -> dict[str, str]:
        """Deletes all messages of a specific conversation session from MongoDB.

        Args:
            organization_id (int): Tenant identifier for isolation.
            session_id (str): Conversation session identifier.

        Returns:
            dict[str, str]: Deletion operation status confirmation.
        """
        deleted_count = await self.agent_repository.deleteSession(
            organization_id=organization_id,
            session_id=session_id,
        )
        return {
            "session_id": session_id,
            "status": "deleted",
            "messages_deleted": str(deleted_count),
        }
