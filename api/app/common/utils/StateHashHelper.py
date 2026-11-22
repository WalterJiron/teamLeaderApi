import hashlib
import json
from typing import Any


class StateHashHelper:

    @staticmethod
    def buildSnapshotHash(payload: dict[str, Any]) -> str:
        """Generates a deterministic SHA-256 hash from normalized area snapshot metrics.

        Args:
            payload (dict[str, Any]): Dictionary containing deterministic area metrics.

        Returns:
            str: Hexadecimal SHA-256 digest used to cache agent responses.
        """
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
