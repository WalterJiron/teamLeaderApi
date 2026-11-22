from __future__ import annotations

from html import escape
from typing import Any

from app.modules.auth.utils.email_templates.EmailTemplate import EmailTemplate


class EmailTemplates:
    @staticmethod
    def render(template: str, payload: dict[str, Any]) -> tuple[str, str, str]:
        """Renders a transactional email template into subject, HTML, and text.

        Args:
            template (str): Template identifier.
            payload (dict[str, Any]): Template variables.

        Returns:
            tuple[str, str, str]: Subject, HTML body, and plain-text body.
        """
        name: str = escape(str(payload.get("full_name", "there")))
        action_url: str = escape(str(payload.get("action_url", "")))
        expires: str = escape(str(payload.get("expires_in", "")))
        extra: str = escape(str(payload.get("extra", "")))

        tpl: EmailTemplate = EmailTemplate.lookup(template)

        action_block: str = ""
        if action_url and tpl.action_label:
            action_block = (
                f'<p><a href="{action_url}" '
                'style="display:inline-block;padding:12px 20px;background:#0f766e;'
                f'color:#ffffff;text-decoration:none;border-radius:6px;">'
                f'{tpl.action_label}</a></p>'
                f'<p style="font-size:12px;color:#64748b;">'
                f'Or copy this link: {action_url}</p>'
            )

        expiry_block: str = ""
        if action_url:
            expiry_block = (
                f'<p style="font-size:12px;color:#64748b;">'
                f'This link expires in {expires}.</p>'
            )

        html: str = (
            '<html><body style="font-family:Arial,sans-serif;color:#0f172a;">'
            f"<p>Hello {name},</p><p>{tpl.message}</p>{action_block}"
            f"<p>{extra}</p>{expiry_block}"
            "<p>If you did not request this action, you can ignore this email.</p>"
            "</body></html>"
        )

        text_parts: list[str] = [
            f"Hello {payload.get('full_name', 'there')},",
            tpl.message,
        ]
        if action_url:
            text_parts.append(action_url)
            text_parts.append(
                f"This link expires in {payload.get('expires_in', '')}."
            )
        if extra:
            text_parts.append(str(extra))
        text_parts.append(
            "If you did not request this action, you can ignore this email."
        )

        return tpl.subject, html, "\n\n".join(text_parts)
