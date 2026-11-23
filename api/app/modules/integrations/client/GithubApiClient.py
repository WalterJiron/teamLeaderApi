import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote, urlparse
import httpx
from app.common.exceptions.AppExceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.core.AppConfig import AppConfig

logger = logging.getLogger(__name__)


class GithubApiClient:

    def __init__(
        self,
        api_base_url: str | None = None,
        api_version: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        page_size: int | None = None,
        max_sync_pages: int | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initializes the GitHub REST client with bounded transport settings.

        Args:
            api_base_url (str | None, optional): GitHub API base URL. Defaults to configuration.
            api_version (str | None, optional): GitHub REST API version header. Defaults to configuration.
            timeout_seconds (float | None, optional): Connection and read timeout. Defaults to configuration.
            max_retries (int | None, optional): Maximum bounded retries. Defaults to configuration.
            page_size (int | None, optional): Issues page size. Defaults to configuration.
            max_sync_pages (int | None, optional): Maximum paginated pages per sync. Defaults to configuration.
            http_client (httpx.AsyncClient | None, optional): Injected HTTP client for testing. Defaults to None.

        Raises:
            RuntimeError: If the API base URL does not use HTTPS.
        """
        self.api_base_url = (api_base_url or AppConfig.GITHUB_API_BASE_URL).rstrip("/")
        self.api_version = api_version or AppConfig.GITHUB_API_VERSION
        self.timeout_seconds = timeout_seconds or AppConfig.GITHUB_API_TIMEOUT_SECONDS
        self.max_retries = max(0, max_retries if max_retries is not None else AppConfig.GITHUB_API_MAX_RETRIES)
        self.page_size = max(1, min(page_size or AppConfig.GITHUB_SYNC_PAGE_SIZE, 100))
        self.max_sync_pages = max(1, max_sync_pages or AppConfig.GITHUB_MAX_SYNC_PAGES)
        self.http_client = http_client
        parsed_base_url = urlparse(self.api_base_url)
        if parsed_base_url.scheme != "https" or not parsed_base_url.netloc:
            raise RuntimeError("GITHUB_API_BASE_URL must use HTTPS.")

    def _buildHeaders(self, access_token: str) -> dict[str, str]:
        """Builds authenticated GitHub REST request headers.

        Args:
            access_token (str): Decrypted GitHub access token.

        Returns:
            dict[str, str]: Request headers accepted by the GitHub REST API.
        """
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": "teamleader-api",
        }

    @asynccontextmanager
    async def _clientContext(self) -> AsyncIterator[httpx.AsyncClient]:
        """Yields an HTTP client for a single GitHub operation.

        Yields:
            AsyncIterator[httpx.AsyncClient]: Managed or injected asynchronous HTTP client.
        """
        if self.http_client is not None:
            yield self.http_client
            return
        timeout = httpx.Timeout(self.timeout_seconds, connect=self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            yield client

    def _backoffDelay(self, attempt: int) -> float:
        """Computes a bounded exponential backoff delay.

        Args:
            attempt (int): Zero-based retry attempt.

        Returns:
            float: Delay in seconds capped at eight seconds.
        """
        return float(min(2 ** attempt, 8))

    def _retryAfterSeconds(self, response: httpx.Response) -> float | None:
        """Extracts a bounded retry delay from GitHub rate-limit headers.

        Args:
            response (httpx.Response): GitHub API response.

        Returns:
            float | None: Retry delay in seconds, or None when no header is present.
        """
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(max(0.0, min(float(retry_after), 30.0)))
            except ValueError:
                return None
        remaining = response.headers.get("x-ratelimit-remaining")
        reset = response.headers.get("x-ratelimit-reset")
        if remaining == "0" and reset:
            try:
                return float(max(0.0, min(float(int(reset) - int(time.time())), 30.0)))
            except ValueError:
                return None
        return None

    def _raiseForStatus(self, response: httpx.Response) -> None:
        """Maps GitHub HTTP error responses to structured application exceptions.

        Args:
            response (httpx.Response): GitHub API response.

        Raises:
            UnauthorizedException: If GitHub rejects the access token.
            ForbiddenException: If the token lacks repository permissions.
            NotFoundException: If the repository is unavailable.
            ServiceUnavailableException: If GitHub rate limits or fails upstream.
            BadRequestException: If GitHub rejects the request for another reason.
        """
        status_code = response.status_code
        if status_code < 400:
            return
        if status_code == 401:
            raise UnauthorizedException(detail="GitHub credentials are invalid or have expired.")
        if status_code == 403:
            if response.headers.get("x-ratelimit-remaining") == "0" or response.headers.get("retry-after"):
                raise ServiceUnavailableException(detail="GitHub API rate limit has been exhausted.")
            raise ForbiddenException(detail="GitHub access is forbidden for the requested repository.")
        if status_code == 404:
            raise NotFoundException(detail="GitHub repository was not found or is not accessible.")
        if status_code == 429:
            raise ServiceUnavailableException(detail="GitHub API rate limit has been exhausted.")
        if 500 <= status_code < 600:
            raise ServiceUnavailableException(detail="GitHub API is temporarily unavailable.")
        raise BadRequestException(detail=f"GitHub API rejected the request with HTTP {status_code}.")

    def _isAllowedUrl(self, url: str) -> bool:
        """Validates that a pagination URL remains on the configured GitHub host.

        Args:
            url (str): Absolute URL supplied by a GitHub Link header.

        Returns:
            bool: True when the URL uses HTTPS and matches the configured API host.
        """
        parsed_url = urlparse(url)
        parsed_base = urlparse(self.api_base_url)
        if parsed_url.scheme != "https" or parsed_url.netloc != parsed_base.netloc:
            return False
        base_path = parsed_base.path.rstrip("/")
        if base_path and not (
            parsed_url.path == base_path or parsed_url.path.startswith(f"{base_path}/")
        ):
            return False
        return True

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Executes a GitHub REST request with bounded retries and rate-limit handling.

        Args:
            method (str): HTTP method.
            path (str): Relative API path or absolute GitHub URL.
            access_token (str): Decrypted GitHub access token.
            params (dict[str, Any] | None, optional): Query parameters. Defaults to None.

        Returns:
            httpx.Response: Successful GitHub API response.

        Raises:
            ServiceUnavailableException: If GitHub is unreachable or rate limited after retries.
        """
        url = path if path.startswith("http") else f"{self.api_base_url}{path}"
        headers = self._buildHeaders(access_token)
        async with self._clientContext() as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(method, url, params=params, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.max_retries:
                        raise ServiceUnavailableException(
                            detail="GitHub API request timed out or could not be reached."
                        ) from exc
                    await asyncio.sleep(self._backoffDelay(attempt))
                    continue

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt >= self.max_retries:
                        self._raiseForStatus(response)
                    retry_delay = self._retryAfterSeconds(response) or self._backoffDelay(attempt)
                    logger.warning(
                        "Retrying GitHub API request after upstream status %s.",
                        response.status_code,
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                self._raiseForStatus(response)
                return response

        raise ServiceUnavailableException(detail="GitHub API is temporarily unavailable.")

    async def fetchRepositoryIssues(
        self,
        owner: str,
        repo: str,
        access_token: str,
        state: str = "all",
        include_pull_requests: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetches paginated repository issues while excluding pull requests by default.

        Args:
            owner (str): GitHub repository owner.
            repo (str): GitHub repository name.
            access_token (str): Decrypted GitHub access token.
            state (str, optional): Issue state filter. Defaults to "all".
            include_pull_requests (bool, optional): Whether to include pull request records. Defaults to False.

        Returns:
            list[dict[str, Any]]: Normalized GitHub issue payloads.

        Raises:
            BadRequestException: If the state filter is invalid.
            ServiceUnavailableException: If GitHub returns malformed data or exhausts pagination quota.
        """
        if state not in {"open", "closed", "all"}:
            raise BadRequestException(detail="GitHub issue state must be one of: open, closed, all.")

        url = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/issues"
        params: dict[str, Any] | None = {
            "state": state,
            "per_page": self.page_size,
            "page": 1,
        }
        issues: list[dict[str, Any]] = []
        pages_read = 0

        while url and pages_read < self.max_sync_pages:
            response = await self._request("GET", url, access_token, params=params)
            pages_read += 1
            try:
                payload = response.json()
            except ValueError as exc:
                raise ServiceUnavailableException(
                    detail="GitHub API returned an invalid JSON response."
                ) from exc
            if not isinstance(payload, list):
                raise ServiceUnavailableException(detail="GitHub API returned an unexpected issues payload.")

            for item in payload:
                if not isinstance(item, dict):
                    continue
                if not include_pull_requests and "pull_request" in item:
                    continue
                issues.append(item)

            next_link = response.links.get("next")
            if isinstance(next_link, dict):
                next_url = next_link.get("url")
            else:
                next_url = getattr(next_link, "url", None)
            if not next_url:
                break
            if not self._isAllowedUrl(next_url):
                logger.warning("Discarding an unexpected GitHub pagination link.")
                break
            if response.headers.get("x-ratelimit-remaining") == "0":
                raise ServiceUnavailableException(
                    detail="GitHub API rate limit has been exhausted before pagination completed."
                )
            url = next_url
            params = None

        return issues

    async def verifyRepositoryAccess(
        self,
        owner: str,
        repo: str,
        access_token: str,
    ) -> dict[str, Any]:
        """Validates read-only repository connectivity during integration setup.

        Args:
            owner (str): GitHub repository owner.
            repo (str): GitHub repository name.
            access_token (str): Decrypted GitHub access token.

        Returns:
            dict[str, Any]: GitHub repository metadata.

        Raises:
            ServiceUnavailableException: If GitHub returns a malformed repository payload.
        """
        url = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
        response = await self._request("GET", url, access_token)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ServiceUnavailableException(
                detail="GitHub API returned an invalid repository response."
            ) from exc
        if not isinstance(payload, dict):
            raise ServiceUnavailableException(detail="GitHub API returned an unexpected repository payload.")
        return payload
