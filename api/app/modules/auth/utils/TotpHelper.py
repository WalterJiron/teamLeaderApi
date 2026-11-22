import pyotp
from app.core.AppConfig import AppConfig


class TotpHelper:

    @staticmethod
    def generateSecret() -> str:
        """Generates a random Base32 TOTP secret.

        Returns:
            str: Base32-encoded TOTP secret.
        """
        return pyotp.random_base32()

    @staticmethod
    def buildProvisioningUri(secret: str, account_name: str) -> str:
        """Builds an otpauth provisioning URI for authenticator applications.

        Args:
            secret (str): Base32 TOTP secret.
            account_name (str): User email or account label.

        Returns:
            str: otpauth:// provisioning URI.
        """
        return pyotp.TOTP(secret).provisioning_uri(
            name=account_name,
            issuer_name=AppConfig.MFA_ISSUER_NAME,
        )

    @staticmethod
    def verifyCode(secret: str, code: str) -> bool:
        """Verifies a six-digit TOTP code with a one-step clock tolerance.

        Args:
            secret (str): Base32 TOTP secret.
            code (str): User-provided TOTP code.

        Returns:
            bool: True when the code is valid.
        """
        try:
            return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
        except Exception:
            return False
