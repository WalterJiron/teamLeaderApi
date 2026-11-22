from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.AppConfig import AppConfig
from app.core.ExceptionHandler import ExceptionHandler
from app.core.MongoManager import MongoManager
from app.core.PostgresManager import PostgresManager
from app.core.RedisManager import RedisManager
from app.core.RequestContext import RequestContextMiddleware
from app.core.SecurityHeadersMiddleware import SecurityHeadersMiddleware
from app.modules.ModelMain import ModelMain
from app.modules.auth.service.EmailOutboxWorker import EmailOutboxWorker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages startup and shutdown lifecycles for PostgreSQL, MongoDB, Redis, and email delivery.

    Args:
        app (FastAPI): FastAPI application instance.

    Yields:
        AsyncGenerator[None, None]: Control back to the running ASGI server.
    """
    if AppConfig.AUTO_CREATE_TABLES:
        await PostgresManager.initModels()
    MongoManager.connect()
    await RedisManager.connect()
    EmailOutboxWorker.start()
    yield
    await EmailOutboxWorker.stop()
    await RedisManager.close()
    MongoManager.close()
    await PostgresManager.close()


def createApplication() -> FastAPI:
    """Builds and configures the FastAPI application with middleware, handlers, and routers.

    Returns:
        FastAPI: Configured ASGI application instance.
    """
    application = FastAPI(
        title=AppConfig.APP_NAME,
        lifespan=lifespan,
        docs_url="/docs" if AppConfig.ENABLE_DOCS else None,
        redoc_url="/redoc" if AppConfig.ENABLE_DOCS else None,
        openapi_url="/openapi.json" if AppConfig.ENABLE_DOCS else None,
    )

    allowed_origins = [
        origin.strip()
        for origin in AppConfig.CORS_ALLOW_ORIGINS.split(",")
        if origin.strip()
    ] or ["http://localhost:3000"]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=AppConfig.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            host.strip()
            for host in AppConfig.TRUSTED_HOSTS.split(",")
            if host.strip()
        ] or ["*"],
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestContextMiddleware)

    ExceptionHandler.registerHandlers(app=application)

    @application.get("/health", tags=["Health"])
    async def healthCheck() -> dict[str, str]:
        """Returns the API liveness status used by container health checks.

        Returns:
            dict[str, str]: Simple status payload.
        """
        return {"status": "ok"}

    @application.get("/health/ready", tags=["Health"])
    async def readinessCheck() -> dict[str, str]:
        """Verifies PostgreSQL and Redis connectivity for readiness probes.

        Returns:
            dict[str, str]: Readiness status payload.
        """
        async with PostgresManager.session_factory() as session:
            await session.execute(text("SELECT 1"))
        redis_client = RedisManager.getClient()
        if redis_client is not None:
            await redis_client.ping()
        return {"status": "ready"}

    ModelMain.registerRouters(application)

    return application


app = createApplication()
