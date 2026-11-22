from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.core.PostgresManager import Base


class EmailOutboxTableDto(Base):
    __tablename__ = "email_outbox"

    outbox_id = Column(String(36), primary_key=True)
    organization_id = Column(Integer, nullable=True, index=True)
    recipient = Column(String(180), nullable=False, index=True)
    template = Column(String(64), nullable=False)
    subject = Column(String(200), nullable=False)
    payload_encrypted = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
