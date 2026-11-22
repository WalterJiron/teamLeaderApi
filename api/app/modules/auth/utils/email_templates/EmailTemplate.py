from __future__ import annotations

from enum import Enum

from app.modules.auth.utils.email_templates.TemplateContent import TemplateContent


class EmailTemplate(Enum):
    PASSWORD_RESET = TemplateContent(
        subject="Reset your TeamLeader password",
        message="We received a request to reset your password.",
        action_label="Reset password",
    )
    EMAIL_VERIFICATION = TemplateContent(
        subject="Verify your TeamLeader email",
        message="Please confirm your email address to activate all account features.",
        action_label="Verify email",
    )
    EMAIL_CHANGE = TemplateContent(
        subject="Confirm your new TeamLeader email",
        message="Please confirm this email address to finish the change.",
        action_label="Confirm email",
    )
    EMAIL_CHANGED_NOTICE = TemplateContent(
        subject="Your TeamLeader email was changed",
        message=(
            "Your account email address was updated. "
            "If this was not you, contact support immediately."
        ),
        action_label="",
    )
    PASSWORD_CHANGED_NOTICE = TemplateContent(
        subject="Your TeamLeader password was changed",
        message=(
            "Your account password was changed. "
            "If this was not you, contact support immediately."
        ),
        action_label="",
    )
    ACCOUNT_LOCKED_NOTICE = TemplateContent(
        subject="TeamLeader account temporarily locked",
        message=(
            "Your account was temporarily locked after repeated failed sign-in attempts."
        ),
        action_label="",
    )
    INVITATION = TemplateContent(
        subject="You were invited to TeamLeader",
        message="An administrator invited you to join their TeamLeader organization.",
        action_label="Accept invitation",
    )
    RECOVERY_APPROVED = TemplateContent(
        subject="TeamLeader account recovery approved",
        message=(
            "Your account recovery request was approved. "
            "Use the link below to set a new password."
        ),
        action_label="Set new password",
    )
    RECOVERY_EMAIL_VERIFICATION = TemplateContent(
        subject="Verify your TeamLeader recovery email",
        message="Please confirm this recovery email address.",
        action_label="Verify recovery email",
    )
    DEFAULT = TemplateContent(
        subject="TeamLeader notification",
        message="You have a new account notification.",
        action_label="Open TeamLeader",
    )

    content: TemplateContent

    def __init__(self, content: TemplateContent) -> None:
        self.content = content

    @property
    def subject(self) -> str:
        return self.content.subject

    @property
    def message(self) -> str:
        return self.content.message

    @property
    def action_label(self) -> str:
        return self.content.action_label

    @classmethod
    def lookup(cls, key: str) -> EmailTemplate:
        """Returns the member whose name matches key, or DEFAULT.

        Args:
            key (str): Template key name.

        Returns:
            EmailTemplate: Matching template enum member or DEFAULT.
        """
        return cls.__members__.get(key, cls.DEFAULT)
