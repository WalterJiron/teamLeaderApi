from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from app.core.AppConfig import AppConfig


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Adds defensive HTTP headers to every response.

        Args:
            request (Request): Incoming HTTP request.
            call_next (RequestResponseEndpoint): Next ASGI handler.

        Returns:
            Response: HTTP response enriched with security headers.
        """
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if AppConfig.SECURITY_HSTS_ENABLED:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.url.path.startswith(f"{AppConfig.API_V1_PREFIX}/auth"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
