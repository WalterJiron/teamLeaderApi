import hashlib
import hmac
import secrets
from passlib.context import CryptContext
from app.core.AppConfig import AppConfig


class PasswordHelper:

    _pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

    _COMMON_PASSWORDS = {
        "password",
        "password1",
        "password123",
        "123456789012",
        "1234567890123",
        "qwertyuiop",
        "qwerty123456",
        "letmein12345",
        "welcome12345",
        "admin123456",
        "iloveyou1234",
        "changeme1234",
    }

    @classmethod
    def hashPassword(cls, plain_password: str) -> str:
        """Hashes a plain-text password using the configured adaptive algorithm.

        Args:
            plain_password (str): Raw password provided by the user.

        Returns:
            str: Salted Argon2id or bcrypt password hash.
        """
        return cls._pwd_context.hash(plain_password)

    @classmethod
    def verifyPassword(cls, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain-text password against a stored hash.

        Args:
            plain_password (str): Raw password provided by the user.
            hashed_password (str): Stored password hash.

        Returns:
            bool: True if the password matches the stored hash.
        """
        try:
            return cls._pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    @classmethod
    def needsRehash(cls, hashed_password: str) -> bool:
        """Checks whether a stored hash should be upgraded to the current algorithm.

        Args:
            hashed_password (str): Stored password hash.

        Returns:
            bool: True when the hash uses a deprecated algorithm or parameters.
        """
        try:
            return cls._pwd_context.needs_update(hashed_password)
        except Exception:
            return True

    @staticmethod
    def getAlgorithm(hashed_password: str) -> str:
        """Detects the password hashing algorithm from a stored hash prefix.

        Args:
            hashed_password (str): Stored password hash.

        Returns:
            str: Detected algorithm name.
        """
        if hashed_password.startswith("$argon2"):
            return "argon2id"
        if hashed_password.startswith("$2"):
            return "bcrypt"
        return "unknown"

    @classmethod
    def isCommonPassword(cls, plain_password: str) -> bool:
        """Checks a password against a small built-in common-password denylist.

        Args:
            plain_password (str): Raw password to inspect.

        Returns:
            bool: True when the password is considered commonly breached.
        """
        return plain_password.strip().lower() in cls._COMMON_PASSWORDS

    @staticmethod
    def generateOpaqueToken(nbytes: int = 32) -> str:
        """Generates a cryptographically secure opaque token.

        Args:
            nbytes (int, optional): Number of random bytes. Defaults to 32.

        Returns:
            str: URL-safe random token.
        """
        return secrets.token_urlsafe(nbytes)

    @staticmethod
    def hashOpaqueToken(token: str) -> str:
        """Computes the SHA-256 digest used to store opaque tokens at rest.

        Args:
            token (str): Raw opaque token.

        Returns:
            str: Hexadecimal SHA-256 digest.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def generateRecoveryCode() -> str:
        """Generates a human-readable one-time recovery code.

        Returns:
            str: Recovery code formatted as XXXX-XXXX-XXXX-XXXX.
        """
        raw = secrets.token_hex(8).upper()
        return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}"

    @staticmethod
    def normalizeRecoveryCode(code: str) -> str:
        """Normalizes a recovery code by removing separators and uppercasing it.

        Args:
            code (str): User-provided recovery code.

        Returns:
            str: Normalized recovery code.
        """
        return code.strip().upper().replace("-", "").replace(" ", "")

    @staticmethod
    def hashRecoveryCode(code: str) -> str:
        """Computes a keyed digest for a recovery code using the application secret.

        Args:
            code (str): User-provided recovery code.

        Returns:
            str: Hexadecimal HMAC-SHA256 digest.
        """
        normalized = PasswordHelper.normalizeRecoveryCode(code)
        return hmac.new(
            AppConfig.JWT_SECRET_KEY.encode("utf-8"),
            normalized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
