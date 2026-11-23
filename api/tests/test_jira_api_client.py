import json

import httpx
import pytest

from app.common.exceptions.AppExceptions import (
    BadRequestException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.modules.integrations.client.JiraApiClient import JiraApiClient
from app.modules.integrations.schemas.JiraIntegrationSchema import (
    JiraIntegrationCreateSchema,
)


def test_jira_integration_request_normalizes_project_key_and_keeps_token_secret():
    payload = JiraIntegrationCreateSchema(
        project_id=1,
        jira_base_url="https://Tenant.atlassian.net/",
        jira_project_key="team",
        jira_email="developer@example.com",
        api_token="plain-api-token-value",
    )

    assert payload.jira_base_url == "https://tenant.atlassian.net"
    assert payload.jira_project_key == "TEAM"
    assert payload.api_token.get_secret_value() == "plain-api-token-value"
    assert "plain-api-token-value" not in payload.model_dump_json()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://tenant.atlassian.net",
        "https://tenant.atlassian.net.evil.example",
        "https://127.0.0.1",
        "https://tenant.atlassian.net/path",
    ],
)
def test_jira_client_rejects_non_cloud_or_non_origin_urls(base_url):
    with pytest.raises(BadRequestException):
        JiraApiClient(base_url=base_url)


@pytest.mark.asyncio
async def test_fetch_project_issues_follows_search_tokens_and_uses_basic_auth():
    seen_bodies = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "tenant.atlassian.net"
        assert request.headers["Authorization"].startswith("Basic ")
        body = json.loads(request.content)
        seen_bodies.append(body)
        if "nextPageToken" not in body:
            return httpx.Response(
                200,
                json={
                    "issues": [{"key": "TEAM-1", "fields": {}}],
                    "nextPageToken": "next-page",
                },
            )
        return httpx.Response(
            200,
            json={"issues": [{"key": "TEAM-2", "fields": {}}], "isLast": True},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_request)
    ) as http_client:
        jira_client = JiraApiClient(
            base_url="https://tenant.atlassian.net",
            http_client=http_client,
        )
        issues = await jira_client.fetchProjectIssues(
            project_key="TEAM",
            jira_email="developer@example.com",
            api_token="test-api-token",
        )

    assert [issue["key"] for issue in issues] == ["TEAM-1", "TEAM-2"]
    assert len(seen_bodies) == 2
    assert "nextPageToken" not in seen_bodies[0]
    assert seen_bodies[1]["nextPageToken"] == "next-page"
    assert "standardIssueTypes()" in seen_bodies[0]["jql"]


@pytest.mark.asyncio
async def test_jira_client_maps_invalid_credentials_to_unauthorized():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"errorMessages": ["private detail"]})
        )
    ) as http_client:
        jira_client = JiraApiClient(
            base_url="https://tenant.atlassian.net",
            http_client=http_client,
            max_retries=0,
        )
        with pytest.raises(UnauthorizedException) as exception:
            await jira_client.verifyProjectAccess(
                project_key="TEAM",
                jira_email="developer@example.com",
                api_token="invalid-api-token",
            )

    assert "private detail" not in str(exception.value.detail)


@pytest.mark.asyncio
async def test_jira_client_rejects_partial_result_when_page_limit_is_reached():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "issues": [{"key": "TEAM-1", "fields": {}}],
                    "nextPageToken": "more",
                },
            )
        )
    ) as http_client:
        jira_client = JiraApiClient(
            base_url="https://tenant.atlassian.net",
            http_client=http_client,
            max_sync_pages=1,
        )
        with pytest.raises(ServiceUnavailableException, match="no partial assessment"):
            await jira_client.fetchProjectIssues(
                project_key="TEAM",
                jira_email="developer@example.com",
                api_token="test-api-token",
            )
