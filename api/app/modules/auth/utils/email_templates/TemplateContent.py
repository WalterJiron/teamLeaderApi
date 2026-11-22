from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateContent:
    subject: str
    message: str
    action_label: str
