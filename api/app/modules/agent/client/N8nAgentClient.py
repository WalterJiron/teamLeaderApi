import logging
import uuid
import httpx
from app.common.exceptions.AppExceptions import ServiceUnavailableException
from app.core.AppConfig import AppConfig

logger = logging.getLogger(__name__)


class N8nAgentClient:

    def __init__(self) -> None:
        """Configures the HTTP client for the n8n AI agent chat webhook."""
        self.webhook_url = AppConfig.N8N_AGENT_CHAT_URL
        self.timeout = httpx.Timeout(timeout=30.0, connect=10.0)

    async def sendMessage(
        self,
        message: str,
        session_id: str,
        user_id: int,
        organization_id: int,
    ) -> str:
        """Sends a user message to the n8n AI agent and returns the assistant reply.

        Args:
            message (str): User chat message.
            session_id (str): Conversation session identifier for context continuity.
            user_id (int): Authenticated user identifier.
            organization_id (int): Tenant identifier for multi-tenant isolation.

        Returns:
            str: Assistant reply text from the n8n agent workflow.

        Raises:
            ServiceUnavailableException: If the n8n agent is unreachable or returns an error.
        """
        payload = {
            "action": "sendMessage",
            "chatInput": message,
            "sessionId": session_id,
            "metadata": {
                "user_id": user_id,
                "organization_id": organization_id,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                return self._extractReply(data=data)
        except httpx.TimeoutException:
            logger.error("n8n agent request timed out for session %s.", session_id)
            raise ServiceUnavailableException(
                detail="AI agent is not responding. Please try again later."
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "n8n agent returned HTTP %s for session %s.",
                exc.response.status_code,
                session_id,
            )
            raise ServiceUnavailableException(
                detail="AI agent returned an unexpected error."
            )
        except Exception as exc:
            logger.exception("Unexpected error calling n8n agent for session %s.", session_id)
            raise ServiceUnavailableException(
                detail="AI agent is currently unavailable."
            ) from exc

    @staticmethod
    def _extractReply(data: dict | list | str) -> str:
        """Extracts the assistant reply text from the n8n webhook response payload.

        Args:
            data (dict | list | str): Raw response from the n8n webhook.

        Returns:
            str: Extracted reply text.
        """
        if isinstance(data, str):
            return data
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                return first.get("output", first.get("text", str(first)))
            return str(first)
        if isinstance(data, dict):
            return data.get("output", data.get("text", data.get("response", str(data))))
        return str(data)
