from dataclasses import dataclass
from typing import Any
from app.modules.auth.dto.UserTableDto import UserTableDto


@dataclass
class AuthContext:

    user: UserTableDto
    session_id: str
    claims: dict[str, Any]
