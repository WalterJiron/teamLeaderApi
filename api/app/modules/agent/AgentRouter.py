from fastapi import APIRouter, Depends, Path, Query, status
from app.common.schemas.ApiResponseSchema import PaginatedResponseSchema, PaginationInfo, ResponseSchema
from app.core.dependencies import getAgentService, getCurrentUser
from app.modules.agent.schemas.AgentSchema import (
    AgentChatRequestSchema,
    AgentChatResponseSchema,
    AgentMessageResponse,
    AgentSessionSummaryResponse,
)
from app.modules.agent.service.AgentService import AgentService
from app.modules.auth.dto.UserTableDto import UserTableDto


class AgentRouter:

    def __init__(self) -> None:
        """Configures the AI agent chat and conversation history router."""
        self.router = APIRouter(prefix="/agent", tags=["AI Agent"])
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers the agent chat and MongoDB conversation history endpoints."""
        self.router.add_api_route(
            path="/chat",
            endpoint=self.chat,
            methods=["POST"],
            response_model=ResponseSchema[AgentChatResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/sessions",
            endpoint=self.listSessions,
            methods=["GET"],
            response_model=PaginatedResponseSchema[AgentSessionSummaryResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/sessions/{session_id}/messages",
            endpoint=self.getSessionMessages,
            methods=["GET"],
            response_model=PaginatedResponseSchema[AgentMessageResponse],
            status_code=status.HTTP_200_OK,
        )
        self.router.add_api_route(
            path="/sessions/{session_id}",
            endpoint=self.deleteSession,
            methods=["DELETE"],
            response_model=ResponseSchema[dict[str, str]],
            status_code=status.HTTP_200_OK,
        )

    async def chat(
        self,
        payload: AgentChatRequestSchema,
        current_user: UserTableDto = Depends(getCurrentUser),
        agent_service: AgentService = Depends(getAgentService),
    ) -> ResponseSchema[AgentChatResponseSchema]:
        """Sends a user message to the AI agent and returns the assistant reply.

        Args:
            payload (AgentChatRequestSchema): Chat message and optional session/area context.
            current_user (UserTableDto): Authenticated user from Bearer JWT.
            agent_service (AgentService): Injected AI agent service.

        Returns:
            ResponseSchema[AgentChatResponseSchema]: Agent reply wrapped in standard response.
        """
        result = await agent_service.chat(
            message=payload.message,
            session_id=payload.session_id,
            user_id=current_user.user_id,
            organization_id=current_user.organization_id,
            project_id=payload.project_id,
            area_id=payload.area_id,
        )
        return ResponseSchema(data=result)

    async def listSessions(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=20, ge=1, le=100),
        current_user: UserTableDto = Depends(getCurrentUser),
        agent_service: AgentService = Depends(getAgentService),
    ) -> PaginatedResponseSchema[AgentSessionSummaryResponse]:
        """Lists active conversation sessions from MongoDB for the authenticated user.

        Args:
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size limit. Defaults to 20.
            current_user (UserTableDto): Authenticated user from Bearer JWT.
            agent_service (AgentService): Injected AI agent service.

        Returns:
            PaginatedResponseSchema[AgentSessionSummaryResponse]: Paginated conversation sessions.
        """
        sessions, total = await agent_service.listSessions(
            organization_id=current_user.organization_id,
            user_id=current_user.user_id,
            page=page,
            limit=limit,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=sessions,
        )

    async def getSessionMessages(
        self,
        session_id: str = Path(..., min_length=1, max_length=128),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
        current_user: UserTableDto = Depends(getCurrentUser),
        agent_service: AgentService = Depends(getAgentService),
    ) -> PaginatedResponseSchema[AgentMessageResponse]:
        """Retrieves paginated conversation message history for a specific session.

        Args:
            session_id (str): Conversation session identifier.
            page (int, optional): One-based page number. Defaults to 1.
            limit (int, optional): Page size limit. Defaults to 50.
            current_user (UserTableDto): Authenticated user from Bearer JWT.
            agent_service (AgentService): Injected AI agent service.

        Returns:
            PaginatedResponseSchema[AgentMessageResponse]: Paginated message history.
        """
        messages, total = await agent_service.getSessionMessages(
            organization_id=current_user.organization_id,
            session_id=session_id,
            page=page,
            limit=limit,
        )
        return PaginatedResponseSchema(
            info=PaginationInfo(page=page, limit=limit, total=total),
            data=messages,
        )

    async def deleteSession(
        self,
        session_id: str = Path(..., min_length=1, max_length=128),
        current_user: UserTableDto = Depends(getCurrentUser),
        agent_service: AgentService = Depends(getAgentService),
    ) -> ResponseSchema[dict[str, str]]:
        """Deletes conversation message history for a session from MongoDB.

        Args:
            session_id (str): Conversation session identifier.
            current_user (UserTableDto): Authenticated user from Bearer JWT.
            agent_service (AgentService): Injected AI agent service.

        Returns:
            ResponseSchema[dict[str, str]]: Deletion confirmation status.
        """
        result = await agent_service.deleteSession(
            organization_id=current_user.organization_id,
            session_id=session_id,
        )
        return ResponseSchema(data=result)
