import json
import logging
from datetime import datetime, timezone
from email.message import EmailMessage
import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.AppConfig import AppConfig
from app.core.EncryptionManager import EncryptionManager
from app.modules.auth.OutboxRepository import OutboxRepository
from app.modules.auth.dto.EmailOutboxTableDto import EmailOutboxTableDto
from app.modules.auth.utils.email_templates import EmailTemplates
from app.modules.auth.utils.TokenHelper import TokenHelper

logger = logging.getLogger(__name__)


class EmailService:

    @staticmethod
    async def enqueueEmail(
        outbox_repository: OutboxRepository,
        recipient: str,
        template: str,
        payload: dict,
        organization_id: int | None = None,
    ) -> EmailOutboxTableDto:
        """Queues a transactional email for asynchronous delivery.

        Args:
            outbox_repository (OutboxRepository): Email outbox persistence repository.
            recipient (str): Destination email address.
            template (str): Template identifier.
            payload (dict): Template variables, including action_url.
            organization_id (int | None, optional): Tenant identifier. Defaults to None.

        Returns:
            EmailOutboxTableDto: Queued outbox entity.
        """
        subject, _, _ = EmailTemplates.render(template, payload)
        encrypted_payload = EncryptionManager.encrypt(json.dumps(payload, default=str))
        email = EmailOutboxTableDto(
            outbox_id=TokenHelper.newId(),
            organization_id=organization_id,
            recipient=recipient.strip().lower(),
            template=template,
            subject=subject,
            payload_encrypted=encrypted_payload,
            status="PENDING",
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc),
        )
        return await outbox_repository.addEmail(email)

    @staticmethod
    async def _send(recipient: str, subject: str, html: str, text: str) -> None:
        """Sends a single email through the configured SMTP transport.

        Args:
            recipient (str): Destination email address.
            subject (str): Email subject.
            html (str): HTML body.
            text (str): Plain-text body.

        Raises:
            RuntimeError: If SMTP delivery fails.
        """
        if AppConfig.EMAIL_PROVIDER == "console" or not AppConfig.SMTP_HOST:
            logger.info("Email provider is console; email to %s was not sent.", recipient)
            return

        message = EmailMessage()
        message["From"] = f"{AppConfig.SMTP_FROM_NAME} <{AppConfig.SMTP_FROM_EMAIL}>"
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=AppConfig.SMTP_HOST,
            port=AppConfig.SMTP_PORT,
            username=AppConfig.SMTP_USERNAME or None,
            password=AppConfig.SMTP_PASSWORD or None,
            start_tls=AppConfig.SMTP_USE_TLS,
            use_tls=AppConfig.SMTP_USE_SSL,
            timeout=20,
        )

    @staticmethod
    async def processOutbox(db_session: AsyncSession, outbox_repository: OutboxRepository, limit: int = 20) -> int:
        """Delivers pending emails and updates their outbox status.

        Args:
            db_session (AsyncSession): Active database session.
            outbox_repository (OutboxRepository): Outbox persistence repository.
            limit (int, optional): Maximum emails to process. Defaults to 20.

        Returns:
            int: Number of processed emails.
        """
        pending = await outbox_repository.getPending(limit)
        for email in pending:
            try:
                payload = json.loads(EncryptionManager.decrypt(email.payload_encrypted))
                _, html, text = EmailTemplates.render(email.template, payload)
                await EmailService._send(email.recipient, email.subject, html, text)
                await outbox_repository.markSent(email)
            except Exception as exc:
                logger.exception("Email delivery failed for outbox entry %s.", email.outbox_id)
                await outbox_repository.markFailed(email, str(exc))
        return len(pending)
