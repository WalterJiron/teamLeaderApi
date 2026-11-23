from fastapi import FastAPI
from app.core.AppConfig import AppConfig
from app.modules.agent.AgentRouter import AgentRouter
from app.modules.auth.routers.AdminAuthRouter import AdminAuthRouter
from app.modules.auth.routers.AuthRouter import AuthRouter
from app.modules.integrations.IntegrationRouter import IntegrationRouter
from app.modules.integrations.JiraIntegrationRouter import JiraIntegrationRouter
from app.modules.metrics.MetricRouter import MetricRouter


class ModelMain:

    @staticmethod
    def registerRouters(application: FastAPI) -> None:
        """Registers all domain module routers with the FastAPI application instance.

        Args:
            application (FastAPI): Active application instance to mount routers onto.
        """
        auth_router = AuthRouter()
        admin_auth_router = AdminAuthRouter()
        integration_router = IntegrationRouter()
        agent_router = AgentRouter()
        jira_integration_router = JiraIntegrationRouter()
        metric_router = MetricRouter()

        application.include_router(auth_router.router, prefix=AppConfig.API_V1_PREFIX)
        application.include_router(admin_auth_router.router, prefix=AppConfig.API_V1_PREFIX)
        application.include_router(integration_router.router, prefix=AppConfig.API_V1_PREFIX)
        application.include_router(agent_router.router, prefix=AppConfig.API_V1_PREFIX)
        application.include_router(jira_integration_router.router, prefix=AppConfig.API_V1_PREFIX)
        application.include_router(metric_router.router, prefix=AppConfig.API_V1_PREFIX)


def registerModuleRouters(application: FastAPI) -> None:
    """Convenience helper to register domain module routers.

    Args:
        application (FastAPI): Active application instance to mount routers onto.
    """
    ModelMain.registerRouters(application=application);
