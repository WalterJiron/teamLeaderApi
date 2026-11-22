from contextvars import ContextVar
from uuid import uuid4
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
client_ip_ctx: ContextVar[str | None] = ContextVar("client_ip", default=None)
user_agent_ctx: ContextVar[str | None] = ContextVar("user_agent", default=None)


def getRequestId() -> str | None:
    """Returns the current request correlation identifier.

    Returns:
        str | None: Request identifier from the active context.
    """
    return request_id_ctx.get()


def getClientIp() -> str | None:
    """Returns the current request client IP address.

    Returns:
        str | None: Client IP address from the active context.
    """
    return client_ip_ctx.get()


def getUserAgent() -> str | None:
    """Returns the current request User-Agent header.

    Returns:
        str | None: User-Agent value from the active context.
    """
    return user_agent_ctx.get()


class RequestContextMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Adds a correlation identifier and request metadata to the logging context.

        Args:
            request (Request): Incoming HTTP request.
            call_next (RequestResponseEndpoint): Next ASGI handler.

        Returns:
            Response: HTTP response with the X-Request-ID header.
        """
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        client_ip = request.client.host if request.client else None
        user_agent = (request.headers.get("user-agent") or "")[:255] or None
        request_tokens = (
            request_id_ctx.set(request_id),
            client_ip_ctx.set(client_ip),
            user_agent_ctx.set(user_agent),
        )
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(request_tokens[0])
            client_ip_ctx.reset(request_tokens[1])
            user_agent_ctx.reset(request_tokens[2])
        response.headers["X-Request-ID"] = request_id
        return response
