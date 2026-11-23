from fastapi import APIRouter, Depends, status
from app.common.schemas.ApiResponseSchema import ResponseSchema
from app.core.dependencies import getCurrentUser
from app.modules.auth.dto.UserTableDto import UserTableDto
from app.modules.metrics.schemas.DelayRiskSchema import (
    DelayRiskAssessmentRequestSchema,
    DelayRiskAssessmentResponseSchema,
)
from app.modules.metrics.utils.DelayRiskCalculator import DelayRiskCalculator


class MetricRouter:

    def __init__(self) -> None:
        """Configures the project metric assessment routes."""
        self.router = APIRouter(prefix="/metrics", tags=["Metrics"])
        self._registerRoutes()

    def _registerRoutes(self) -> None:
        """Registers the AI-ready delay risk assessment endpoint."""
        self.router.add_api_route(
            path="/delay-risk-assessment",
            endpoint=self.assessDelayRisk,
            methods=["POST"],
            response_model=ResponseSchema[DelayRiskAssessmentResponseSchema],
            status_code=status.HTTP_200_OK,
        )

    async def assessDelayRisk(
        self,
        payload: DelayRiskAssessmentRequestSchema,
        current_user: UserTableDto = Depends(getCurrentUser),
    ) -> ResponseSchema[DelayRiskAssessmentResponseSchema]:
        """Calculates the Jira delay risk for an AI agent to interpret.

        Args:
            payload (DelayRiskAssessmentRequestSchema): Normalized Jira task metrics.
            current_user (UserTableDto): Authenticated caller.

        Returns:
            ResponseSchema[DelayRiskAssessmentResponseSchema]: AI-ready risk assessment.
        """
        assessment = DelayRiskCalculator.resolveRisk(request=payload)
        return ResponseSchema(data=assessment)
