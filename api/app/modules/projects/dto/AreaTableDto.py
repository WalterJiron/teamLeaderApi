from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class AreaTableDto(Base, AuditMixin):
    __tablename__ = "areas"

    area_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_areas_project_name"),
    )
