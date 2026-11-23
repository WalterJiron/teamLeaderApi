from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from app.core.PostgresManager import Base


class GithubWebhookDeliveryTableDto(Base):
    __tablename__ = "github_webhook_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(String(128), unique=True, nullable=False, index=True)
    integration_id = Column(
        Integer,
        ForeignKey("github_integrations.integration_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_github_webhook_deliveries_integration_processed", "integration_id", "processed_at"),
    )
