from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from app.core.PostgresManager import Base


class AgentCacheTableDto(Base):
    __tablename__ = "agent_cache"

    cache_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area_id = Column(
        Integer,
        ForeignKey("areas.area_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    state_hash = Column(String(64), nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_agent_cache_area_state_hash", "area_id", "state_hash"),
    )
