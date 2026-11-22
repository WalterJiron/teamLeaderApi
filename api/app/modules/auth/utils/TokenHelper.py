import hashlib
import secrets
from uuid import uuid4


class TokenHelper:

    @staticmethod
    def newId() -> str:
        """Generates a new UUIDv4 identifier.

        Returns:
            str: UUID string.
        """
        return str(uuid4())

    @staticmethod
    def generateToken(nbytes: int = 32) -> str:
        """Generates a cryptographically secure URL-safe token.

        Args:
            nbytes (int, optional): Number of random bytes. Defaults to 32.

        Returns:
            str: URL-safe random token.
        """
        return secrets.token_urlsafe(nbytes)

    @staticmethod
    def hashToken(token: str) -> str:
        """Computes the SHA-256 digest used to store tokens at rest.

        Args:
            token (str): Raw token.

        Returns:
            str: Hexadecimal SHA-256 digest.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def hashEmail(email: str) -> str:
        """Computes a deterministic SHA-256 digest of a normalized email.

        Args:
            email (str): Email address.

        Returns:
            str: Hexadecimal SHA-256 digest.
        """
        return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
