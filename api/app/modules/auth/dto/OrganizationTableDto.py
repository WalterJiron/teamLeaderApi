from sqlalchemy import Column, Integer, String
from app.common.dto.AuditMixin import AuditMixin
from app.core.PostgresManager import Base


class OrganizationTableDto(Base, AuditMixin):
    __tablename__ = "organizations"

    organization_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(160), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
