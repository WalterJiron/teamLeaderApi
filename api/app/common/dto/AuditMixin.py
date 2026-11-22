from sqlalchemy import Column, DateTime, Integer, func


class AuditMixin:

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)
    deleted_by = Column(Integer, nullable=True)
