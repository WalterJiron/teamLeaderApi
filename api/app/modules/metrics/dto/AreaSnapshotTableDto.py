from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from app.core.PostgresManager import Base


class AreaSnapshotTableDto(Base):
    __tablename__ = "area_snapshots"

    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area_id = Column(
        Integer,
        ForeignKey("areas.area_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_tasks = Column(Integer, nullable=False, default=0)
    completed_tasks = Column(Integer, nullable=False, default=0)
    blocked_tasks = Column(Integer, nullable=False, default=0)
    remaining_days = Column(Integer, nullable=False, default=0)
    deadline_probability = Column(Float, nullable=False, default=0.0)
    health_status = Column(String(16), nullable=False, default="CRITICAL")
    state_hash = Column(String(64), nullable=False, index=True)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_area_snapshots_area_captured", "area_id", "captured_at"),
    )
