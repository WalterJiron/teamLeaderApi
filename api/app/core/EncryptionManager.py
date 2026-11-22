from cryptography.fernet import Fernet, InvalidToken
from app.core.AppConfig import AppConfig


class EncryptionManager:

    _fernet: Fernet | None = None

    @classmethod
    def _getFernet(cls) -> Fernet:
        """Builds and returns the configured Fernet cipher.

        Returns:
            Fernet: Symmetric cipher used for sensitive values at rest.

        Raises:
            RuntimeError: If DATA_ENCRYPTION_KEY is missing or invalid.
        """
        if cls._fernet is None:
            if not AppConfig.DATA_ENCRYPTION_KEY:
                raise RuntimeError("DATA_ENCRYPTION_KEY must be configured.")
            try:
                cls._fernet = Fernet(AppConfig.DATA_ENCRYPTION_KEY.encode("utf-8"))
            except Exception as exc:
                raise RuntimeError("DATA_ENCRYPTION_KEY is not a valid Fernet key.") from exc
        return cls._fernet

    @classmethod
    def encrypt(cls, value: str) -> str:
        """Encrypts a plain-text value with the application data key.

        Args:
            value (str): Sensitive plain-text value.

        Returns:
            str: URL-safe encrypted token.
        """
        return cls._getFernet().encrypt(value.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt(cls, token: str) -> str:
        """Decrypts a value previously produced by encrypt().

        Args:
            token (str): Encrypted URL-safe token.

        Returns:
            str: Original plain-text value.

        Raises:
            ValueError: If the token cannot be decrypted with the configured key.
        """
        try:
            return cls._getFernet().decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Encrypted value could not be decrypted.") from exc
