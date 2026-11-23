from sqlalchemy import Column, ForeignKey, Integer, String, Text
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class ProjectTableDto(Base, AuditMixin):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
