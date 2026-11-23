from cryptography.fernet import Fernet, InvalidToken
from app.core.AppConfig import AppConfig


class SecretEncryptionHelper:

    _KNOWN_PREFIXES: tuple[str, ...] = (
        "github_pat_",
        "ghp_",
        "gho_",
        "ghu_",
        "ghs_",
        "ghr_",
    )

    def __init__(self, encryption_key: str | None = None) -> None:
        """Initializes the helper with the credentials encryption key.

        Args:
            encryption_key (str | None, optional): Explicit Fernet key. Defaults to the configured credentials key.

        Raises:
            RuntimeError: If no key is configured or the key is invalid.
        """
        resolved_key = encryption_key or AppConfig.CREDENTIALS_ENCRYPTION_KEY or AppConfig.DATA_ENCRYPTION_KEY
        if not resolved_key:
            raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY must be configured.")
        try:
            self._fernet = Fernet(resolved_key.encode("utf-8"))
        except Exception as exc:
            raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY is not a valid Fernet key.") from exc

    def encryptSecret(self, plain_secret: str) -> str:
        """Encrypts a plain-text credential for storage at rest.

        Args:
            plain_secret (str): Raw credential value.

        Returns:
            str: URL-safe Fernet token.

        Raises:
            ValueError: If the credential is empty.
        """
        if not plain_secret:
            raise ValueError("Secret value cannot be empty.")
        return self._fernet.encrypt(plain_secret.encode("utf-8")).decode("utf-8")

    def decryptSecret(self, encrypted_secret: str) -> str:
        """Decrypts a credential previously produced by encryptSecret().

        Args:
            encrypted_secret (str): URL-safe Fernet token.

        Returns:
            str: Original plain-text credential.

        Raises:
            ValueError: If the token is empty or cannot be decrypted with the configured key.
        """
        if not encrypted_secret:
            raise ValueError("Encrypted secret value cannot be empty.")
        try:
            return self._fernet.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Encrypted credential could not be decrypted.") from exc

    def maskSecret(self, plain_secret: str) -> str:
        """Builds a safe masked preview of a credential for UI display.

        Args:
            plain_secret (str): Raw credential value.

        Returns:
            str: Masked preview such as 'ghp_****89a'.
        """
        if not plain_secret:
            return "****"
        visible_prefix = ""
        for prefix in self._KNOWN_PREFIXES:
            if plain_secret.startswith(prefix):
                visible_prefix = prefix
                break
        if not visible_prefix:
            visible_prefix = plain_secret[:4]
        if len(plain_secret) <= len(visible_prefix) + 3:
            return "****"
        return f"{visible_prefix}****{plain_secret[-3:]}"
