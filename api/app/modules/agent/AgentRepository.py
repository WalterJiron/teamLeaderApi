import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.MongoManager import MongoManager
from app.modules.agent.dto.AgentCacheTableDto import AgentCacheTableDto
from app.modules.agent.dto.AgentMemoryDoc import AgentMemoryDoc

logger = logging.getLogger(__name__)


class AgentRepository:

    COLLECTION_NAME: str = "agent_memory"

    def __init__(self, db_session: AsyncSession) -> None:
        """Initializes the agent repository with PostgreSQL and MongoDB access.

        Args:
            db_session (AsyncSession): Active SQLAlchemy async session for agent cache.
        """
        self.db_session = db_session

    async def getCachedResponse(
        self,
        organization_id: int,
        area_id: int,
        state_hash: str,
    ) -> str | None:
        """Finds a cached agent response matching the exact area state hash.

        Args:
            organization_id (int): Tenant identifier.
            area_id (int): Area identifier.
            state_hash (str): Deterministic SHA-256 hash of area snapshot metrics.

        Returns:
            str | None: Cached response text or None if cache miss.
        """
        query = (
            select(AgentCacheTableDto.response_text)
            .where(
                AgentCacheTableDto.organization_id == organization_id,
                AgentCacheTableDto.area_id == area_id,
                AgentCacheTableDto.state_hash == state_hash,
            )
            .order_by(AgentCacheTableDto.cache_id.desc())
            .limit(1)
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()

    async def setCachedResponse(
        self,
        organization_id: int,
        area_id: int | None,
        state_hash: str,
        response_text: str,
    ) -> None:
        """Stores an assistant response in PostgreSQL for state-hash response caching.

        Args:
            organization_id (int): Tenant identifier.
            area_id (int | None): Area identifier when scoped to an area.
            state_hash (str): Deterministic SHA-256 hash of area metrics.
            response_text (str): Assistant reply text to cache.
        """
        entry = AgentCacheTableDto(
            organization_id=organization_id,
            area_id=area_id,
            state_hash=state_hash,
            response_text=response_text,
        )
        self.db_session.add(entry)
        await self.db_session.flush()

    async def appendMemory(self, memory: AgentMemoryDoc) -> None:
        """Appends a conversation message to MongoDB agent memory collection.

        Args:
            memory (AgentMemoryDoc): Conversational memory document.
        """
        try:
            db = MongoManager.getDatabase()
            await db[self.COLLECTION_NAME].insert_one(memory.toMongoDict())
        except Exception:
            logger.warning("Failed to persist conversation memory to MongoDB.", exc_info=True)

    async def getRecentHistory(
        self,
        organization_id: int,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves recent conversation messages for the session from MongoDB.

        Args:
            organization_id (int): Tenant identifier for isolation.
            session_id (str): Conversation session identifier.
            limit (int, optional): Max messages to fetch. Defaults to 10.

        Returns:
            list[dict[str, Any]]: Chronologically ordered list of recent messages.
        """
        try:
            db = MongoManager.getDatabase()
            cursor = (
                db[self.COLLECTION_NAME]
                .find(
                    {
                        "organization_id": organization_id,
                        "session_id": session_id,
                    },
                    {"_id": 0},
                )
                .sort("created_at", -1)
                .limit(limit)
            )
            docs = await cursor.to_list(length=limit)
            docs.reverse()
            return docs
        except Exception:
            logger.warning("Failed to retrieve conversation history from MongoDB.", exc_info=True)
            return []

    async def listSessions(
        self,
        organization_id: int,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lists chat conversation sessions for the authenticated user with aggregation.

        Args:
            organization_id (int): Tenant identifier for isolation.
            user_id (int): Authenticated user identifier.
            offset (int, optional): Pagination offset. Defaults to 0.
            limit (int, optional): Pagination limit. Defaults to 20.

        Returns:
            tuple[list[dict[str, Any]], int]: Aggregated sessions list and total session count.
        """
        try:
            db = MongoManager.getDatabase()
            match_stage = {
                "$match": {
                    "organization_id": organization_id,
                    "user_id": user_id,
                }
            }

            # Count total distinct sessions
            count_pipeline = [
                match_stage,
                {"$group": {"_id": "$session_id"}},
                {"$count": "total"},
            ]
            count_result = await db[self.COLLECTION_NAME].aggregate(count_pipeline).to_list(length=1)
            total = count_result[0]["total"] if count_result else 0

            if total == 0:
                return [], 0

            # Aggregation for session summaries
            pipeline = [
                match_stage,
                {"$sort": {"created_at": -1}},
                {
                    "$group": {
                        "_id": "$session_id",
                        "session_id": {"$first": "$session_id"},
                        "project_id": {"$first": "$project_id"},
                        "area_id": {"$first": "$area_id"},
                        "message_count": {"$sum": 1},
                        "last_message": {"$first": "$content"},
                        "last_role": {"$first": "$role"},
                        "updated_at": {"$max": "$created_at"},
                    }
                },
                {"$sort": {"updated_at": -1}},
                {"$skip": offset},
                {"$limit": limit},
                {"$project": {"_id": 0}},
            ]
            sessions = await db[self.COLLECTION_NAME].aggregate(pipeline).to_list(length=limit)
            return sessions, total
        except Exception:
            logger.warning("Failed to list agent sessions from MongoDB.", exc_info=True)
            return [], 0

    async def getSessionMessages(
        self,
        organization_id: int,
        session_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieves paginated messages of a specific session from MongoDB.

        Args:
            organization_id (int): Tenant identifier for isolation.
            session_id (str): Conversation session identifier.
            offset (int, optional): Pagination offset. Defaults to 0.
            limit (int, optional): Pagination limit. Defaults to 50.

        Returns:
            tuple[list[dict[str, Any]], int]: Message documents and total count.
        """
        try:
            db = MongoManager.getDatabase()
            query = {
                "organization_id": organization_id,
                "session_id": session_id,
            }
            total = await db[self.COLLECTION_NAME].count_documents(query)
            if total == 0:
                return [], 0

            cursor = (
                db[self.COLLECTION_NAME]
                .find(query, {"_id": 0})
                .sort("created_at", 1)
                .skip(offset)
                .limit(limit)
            )
            messages = await cursor.to_list(length=limit)
            return messages, total
        except Exception:
            logger.warning("Failed to fetch session messages from MongoDB.", exc_info=True)
            return [], 0

    async def deleteSession(
        self,
        organization_id: int,
        session_id: str,
    ) -> int:
        """Deletes all messages of a specific conversation session from MongoDB.

        Args:
            organization_id (int): Tenant identifier for isolation.
            session_id (str): Conversation session identifier.

        Returns:
            int: Number of deleted message documents.
        """
        try:
            db = MongoManager.getDatabase()
            result = await db[self.COLLECTION_NAME].delete_many({
                "organization_id": organization_id,
                "session_id": session_id,
            })
            return result.deleted_count
        except Exception:
            logger.warning("Failed to delete session history from MongoDB.", exc_info=True)
            return 0
