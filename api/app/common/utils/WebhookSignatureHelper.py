import hashlib
import hmac


class WebhookSignatureHelper:

    @staticmethod
    def verifyGithubSignature(raw_body: bytes, signature_header: str, secret: str) -> bool:
        """Validates the X-Hub-Signature-256 HMAC header sent by GitHub webhooks.

        Args:
            raw_body (bytes): Raw request payload bytes.
            signature_header (str): Signature header value formatted as 'sha256=<digest>'.
            secret (str): Configured GitHub webhook secret.

        Returns:
            bool: True if the signature matches the expected HMAC digest, False otherwise.
        """
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)
