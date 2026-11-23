import asyncio
import json
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

logger = logging.getLogger(__name__)


class JiraApiClient:

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        page_size: int = 100,
        max_sync_pages: int = 100,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initializes a bounded Jira Cloud REST client.

        Args:
            base_url (str): Jira Cloud tenant URL.
            timeout_seconds (float): Per-request timeout.
            max_retries (int): Maximum retries for transient upstream failures.
            page_size (int): Jira search page size.
            max_sync_pages (int): Maximum pages fetched for one project sync.
            http_client (httpx.AsyncClient | None): Optional injected test client.
        """
        self.base_url = self.validateBaseUrl(base_url)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.page_size = max(1, min(page_size, 100))
        self.max_sync_pages = max(1, max_sync_pages)
        self.http_client = http_client

    @staticmethod
    def validateBaseUrl(base_url: str) -> str:
        """Restricts outbound Jira requests to HTTPS Atlassian Cloud tenants.

        Args:
            base_url (str): User-provided Jira tenant URL.

        Returns:
            str: Canonical tenant origin without a trailing slash.

        Raises:
            BadRequestException: If the URL is not a Jira Cloud tenant origin.
        """
        normalized = base_url.strip().rstrip("/")
        parsed = urlparse(normalized)
        hostname = (parsed.hostname or "").casefold()
        if (
            parsed.scheme != "https"
            or not hostname.endswith(".atlassian.net")
            or hostname == "atlassian.net"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise BadRequestException(
                detail="Jira URL must be an HTTPS Atlassian Cloud tenant origin."
            )
        return f"https://{hostname}"

    @asynccontextmanager
    async def _clientContext(self) -> AsyncIterator[httpx.AsyncClient]:
        if self.http_client is not None:
            yield self.http_client
            return
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=self.timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            yield client

    def _retryAfterSeconds(self, response: httpx.Response) -> float | None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 30.0))
            except ValueError:
                return None
        return None

    def _raiseForStatus(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if status_code < 400:
            return
        if status_code == 401:
            raise UnauthorizedException(
                detail="Jira credentials are invalid or have expired."
            )
        if status_code == 403:
            raise ForbiddenException(
                detail="The Jira account lacks permission for this project operation."
            )
        if status_code == 404:
            raise NotFoundException(
                detail="The Jira project was not found or is not accessible."
            )
        if status_code == 429:
            raise ServiceUnavailableException(
                detail="Jira API rate limit has been exhausted; retry later."
            )
        if 500 <= status_code < 600:
            raise ServiceUnavailableException(
                detail="Jira API is temporarily unavailable."
            )
        raise BadRequestException(
            detail=f"Jira API rejected the request with HTTP {status_code}."
        )

    async def _request(
        self,
        method: str,
        path: str,
        jira_email: str,
        api_token: str,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        async with self._clientContext() as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        auth=(jira_email, api_token),
                        headers={"Accept": "application/json"},
                        json=json_body,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.max_retries:
                        raise ServiceUnavailableException(
                            detail="Jira API request timed out or could not be reached."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt >= self.max_retries:
                        self._raiseForStatus(response)
                    delay = self._retryAfterSeconds(response)
                    if delay is None:
                        delay = float(min(2**attempt, 8))
                    logger.warning(
                        "Retrying Jira API request after upstream status %s.",
                        response.status_code,
                    )
                    await asyncio.sleep(delay)
                    continue

                self._raiseForStatus(response)
                return response

        raise ServiceUnavailableException(
            detail="Jira API is temporarily unavailable."
        )

    def _responseObject(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceUnavailableException(
                detail="Jira returned an invalid JSON response."
            ) from exc
        if not isinstance(payload, dict):
            raise ServiceUnavailableException(
                detail="Jira returned an unexpected response structure."
            )
        return payload

    async def verifyProjectAccess(
        self,
        project_key: str,
        jira_email: str,
        api_token: str,
    ) -> dict[str, str]:
        """Verifies credentials and access to a Jira project.

        Args:
            project_key (str): Jira project key.
            jira_email (str): Atlassian account email.
            api_token (str): Atlassian API token.

        Returns:
            dict[str, str]: Canonical project key and display name.
        """
        path = f"/rest/api/3/project/{quote(project_key, safe='')}"
        response = await self._request(
            "GET",
            path,
            jira_email=jira_email,
            api_token=api_token,
        )
        payload = self._responseObject(response)
        canonical_key = payload.get("key")
        project_name = payload.get("name")
        if not isinstance(canonical_key, str) or not isinstance(project_name, str):
            raise ServiceUnavailableException(
                detail="Jira returned incomplete project details."
            )
        return {"project_key": canonical_key, "project_name": project_name}

    async def fetchProjectIssues(
        self,
        project_key: str,
        jira_email: str,
        api_token: str,
    ) -> list[dict[str, Any]]:
        """Fetches all project issues using Jira's token-based search pagination.

        Args:
            project_key (str): Jira project key.
            jira_email (str): Atlassian account email.
            api_token (str): Atlassian API token.

        Returns:
            list[dict[str, Any]]: Jira issue records.

        Raises:
            ServiceUnavailableException: If paging is incomplete or malformed.
        """
        jql = (
            f'project = "{project_key}" AND issuetype in standardIssueTypes() '
            "ORDER BY key ASC"
        )
        next_page_token: str | None = None
        seen_page_tokens: set[str] = set()
        issues: list[dict[str, Any]] = []

        for _ in range(self.max_sync_pages):
            body: dict[str, Any] = {
                "jql": jql,
                "fields": [
                    "assignee",
                    "created",
                    "duedate",
                    "issuetype",
                    "resolution",
                    "resolutiondate",
                    "status",
                ],
                "maxResults": self.page_size,
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token
            response = await self._request(
                "POST",
                "/rest/api/3/search/jql",
                jira_email=jira_email,
                api_token=api_token,
                json_body=body,
            )
            payload = self._responseObject(response)
            page_issues = payload.get("issues")
            if not isinstance(page_issues, list) or any(
                not isinstance(issue, dict) for issue in page_issues
            ):
                raise ServiceUnavailableException(
                    detail="Jira returned an invalid issue search response."
                )
            issues.extend(page_issues)
            returned_token = payload.get("nextPageToken")
            if returned_token is None and payload.get("isLast") is False:
                raise ServiceUnavailableException(
                    detail="Jira indicated more issues without a pagination token."
                )
            if returned_token is None or returned_token == "":
                return issues
            if (
                not isinstance(returned_token, str)
                or returned_token in seen_page_tokens
            ):
                raise ServiceUnavailableException(
                    detail="Jira returned an invalid pagination token."
                )
            seen_page_tokens.add(returned_token)
            next_page_token = returned_token

        raise ServiceUnavailableException(
            detail=(
                "Jira project exceeds the configured synchronization page limit; "
                "no partial assessment was returned."
            )
        )

    def _validateRoleUrl(self, role_url: str) -> str:
        parsed = urlparse(role_url)
        base = urlparse(self.base_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc.casefold() != base.netloc.casefold()
            or not parsed.path.startswith("/rest/api/3/project/")
        ):
            raise ServiceUnavailableException(
                detail="Jira returned an unsafe project role URL."
            )
        return parsed.path

    async def fetchProjectRoles(
        self,
        project_key: str,
        jira_email: str,
        api_token: str,
    ) -> tuple[dict[str, list[str]], bool]:
        """Fetches project roles by Jira account id when the caller can view them.

        Returns a false availability flag when the credentials can browse the
        project but cannot access project-role administration endpoints.
        """
        path = f"/rest/api/3/project/{quote(project_key, safe='')}/role"
        try:
            response = await self._request(
                "GET",
                path,
                jira_email=jira_email,
                api_token=api_token,
            )
        except (ForbiddenException, NotFoundException):
            return {}, False

        role_links = self._responseObject(response)
        if len(role_links) > 50:
            raise ServiceUnavailableException(
                detail="Jira project has more roles than the synchronization limit."
            )

        user_roles: dict[str, set[str]] = {}
        for role_name, role_url in role_links.items():
            if not isinstance(role_name, str) or not isinstance(role_url, str):
                raise ServiceUnavailableException(
                    detail="Jira returned an invalid project role response."
                )
            role_path = self._validateRoleUrl(role_url)
            try:
                role_response = await self._request(
                    "GET",
                    role_path,
                    jira_email=jira_email,
                    api_token=api_token,
                )
            except (ForbiddenException, NotFoundException):
                return {}, False
            role_payload = self._responseObject(role_response)
            actors = role_payload.get("actors", [])
            if not isinstance(actors, list):
                raise ServiceUnavailableException(
                    detail="Jira returned an invalid project role actor list."
                )
            for actor in actors:
                if not isinstance(actor, dict):
                    continue
                actor_user = actor.get("actorUser")
                if not isinstance(actor_user, dict):
                    continue
                account_id = actor_user.get("accountId")
                if isinstance(account_id, str) and account_id:
                    user_roles.setdefault(account_id, set()).add(role_name)

        return {
            account_id: sorted(roles)
            for account_id, roles in user_roles.items()
        }, True
