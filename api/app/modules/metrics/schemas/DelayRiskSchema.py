from pydantic import BaseModel, Field, field_validator, model_validator


class MemberPendingSchema(BaseModel):
    member_id: str | None = Field(default=None, max_length=128)
    member_name: str = Field(..., min_length=1, max_length=160)
    unresolved_tasks: int = Field(..., ge=0)
    role: str = Field(..., min_length=1, max_length=120)
    assigned_tasks: int | None = Field(default=None, ge=0)

    @field_validator("member_name", "role")
    @classmethod
    def normalizeMemberText(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Member names and roles cannot be empty.")
        return normalized


class DeliveryPeriodSchema(BaseModel):
    tasks_completed: int = Field(..., ge=0)
    period_days: float = Field(..., gt=0, le=3650)


class CurrentDeliveryPeriodSchema(BaseModel):
    tasks_completed: int = Field(..., ge=0)
    period_days: float = Field(..., gt=0, le=3650)


class DelayRiskAssessmentRequestSchema(BaseModel):
    total_tasks: int = Field(..., ge=0)
    unresolved_tasks: int = Field(..., ge=0)
    remaining_days: int | None = Field(default=None, ge=-3650, le=3650)
    members: list[MemberPendingSchema] = Field(default_factory=list, max_length=500)
    delivery_history: list[DeliveryPeriodSchema] = Field(default_factory=list, max_length=1000)
    current_delivery_period: CurrentDeliveryPeriodSchema | None = None

    @model_validator(mode="after")
    def validateTaskCounts(self) -> "DelayRiskAssessmentRequestSchema":
        if self.unresolved_tasks > self.total_tasks:
            raise ValueError("Unresolved tasks cannot exceed total tasks.")
        if sum(member.unresolved_tasks for member in self.members) > self.unresolved_tasks:
            raise ValueError("Member pending totals cannot exceed unresolved tasks.")
        for member in self.members:
            if (
                member.assigned_tasks is not None
                and member.unresolved_tasks > member.assigned_tasks
            ):
                raise ValueError(
                    "A member's unresolved tasks cannot exceed their assigned tasks."
                )
        if all(member.assigned_tasks is not None for member in self.members):
            assigned_tasks = sum(member.assigned_tasks or 0 for member in self.members)
            if assigned_tasks > self.total_tasks:
                raise ValueError("Member assigned totals cannot exceed total tasks.")
        return self


class MemberPendingResponseSchema(BaseModel):
    member_id: str | None
    member_name: str
    role: str
    assigned_tasks: int | None
    unresolved_tasks: int


class ProductivityAssessmentSchema(BaseModel):
    historical_periods: int
    historical_average_tasks_per_day: float | None
    historical_average_days_per_task: float | None
    current_tasks_per_day: float | None
    is_below_historical_average: bool | None
    comparison: str


class TeamRecommendationSchema(BaseModel):
    category: str
    priority: str
    message: str


class DelayRiskAssessmentResponseSchema(BaseModel):
    risk_level: str
    risk_probability: str
    unresolved_tasks: int
    total_tasks: int
    unresolved_ratio: float
    remaining_days: int | None
    is_immediate: bool
    member_with_most_pending: MemberPendingResponseSchema | None
    member_with_most_tasks: MemberPendingResponseSchema | None
    member_task_count_basis: str | None
    productivity: ProductivityAssessmentSchema
    team_recommendations: list[TeamRecommendationSchema]
    reason: str
    recommended_action: str
    agent_message: str
