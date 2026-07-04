"""Unit tests for ZendeskClient using respx to mock HTTP calls."""

from __future__ import annotations

import os

import pytest
import respx
import httpx

from zendesk_ops_mcp.zendesk_client import ZendeskClient, ZendeskAPIError

RATE_LIMIT_HEADERS = {"X-RateLimit-Remaining": "180"}
BASE_URL = "https://test.zendesk.com"


def make_client() -> ZendeskClient:
    return ZendeskClient(subdomain="test", email="test@test.com", api_token="tok")


# ---------------------------------------------------------------------------
# 1. Successful GET returns JSON and updates rate limit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_get_returns_json():
    client = make_client()
    respx.get(f"{BASE_URL}/api/v2/groups.json").mock(
        return_value=httpx.Response(200, json={"groups": [{"id": 1}]}, headers=RATE_LIMIT_HEADERS)
    )

    result = await client.get("/api/v2/groups.json")

    assert result == {"groups": [{"id": 1}]}
    assert client.rate_limit_remaining == 180
    await client.close()


# ---------------------------------------------------------------------------
# 2. 401 raises auth error
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_401_raises_auth_error():
    client = make_client()
    respx.get(f"{BASE_URL}/api/v2/groups.json").mock(
        return_value=httpx.Response(401, text="Unauthorized", headers=RATE_LIMIT_HEADERS)
    )

    with pytest.raises(ZendeskAPIError) as exc_info:
        await client.get("/api/v2/groups.json")

    assert "Invalid credentials" in exc_info.value.message
    assert exc_info.value.status_code == 401
    await client.close()


# ---------------------------------------------------------------------------
# 3. 404 raises not found error
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_404_raises_not_found():
    client = make_client()
    respx.get(f"{BASE_URL}/api/v2/tickets/99999.json").mock(
        return_value=httpx.Response(404, text="Not Found", headers=RATE_LIMIT_HEADERS)
    )

    with pytest.raises(ZendeskAPIError) as exc_info:
        await client.get("/api/v2/tickets/99999.json")

    assert "Resource not found" in exc_info.value.message
    assert exc_info.value.status_code == 404
    await client.close()


# ---------------------------------------------------------------------------
# 4. 429 raises rate limit error with Retry-After
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_429_rate_limit_raises():
    client = make_client()
    respx.get(f"{BASE_URL}/api/v2/groups.json").mock(
        return_value=httpx.Response(
            429,
            text="Too Many Requests",
            headers={"Retry-After": "30", **RATE_LIMIT_HEADERS},
        )
    )

    with pytest.raises(ZendeskAPIError) as exc_info:
        await client.get("/api/v2/groups.json")

    assert "Rate limit exceeded" in exc_info.value.message
    assert "30" in exc_info.value.message
    assert exc_info.value.status_code == 429
    await client.close()


# ---------------------------------------------------------------------------
# 5. Unconfigured client raises on get()
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unconfigured_raises():
    client = ZendeskClient(subdomain="", email="", api_token="")

    with pytest.raises(ZendeskAPIError) as exc_info:
        await client.get("/api/v2/groups.json")

    assert "not configured" in exc_info.value.message.lower()
    await client.close()


# ---------------------------------------------------------------------------
# 6. get_all follows pagination across multiple pages
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_get_all_follows_pagination():
    client = make_client()

    # Register page=2 route BEFORE the generic users.json route
    respx.get(f"{BASE_URL}/api/v2/users.json", params={"page": "2"}).mock(
        return_value=httpx.Response(
            200,
            json={"users": [{"id": 2}], "next_page": None},
            headers=RATE_LIMIT_HEADERS,
        )
    )
    respx.get(f"{BASE_URL}/api/v2/users.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "users": [{"id": 1}],
                "next_page": f"{BASE_URL}/api/v2/users.json?page=2",
            },
            headers=RATE_LIMIT_HEADERS,
        )
    )

    results = await client.get_all("/api/v2/users.json", data_key="users")

    assert len(results) == 2
    assert results[0] == {"id": 1}
    assert results[1] == {"id": 2}
    await client.close()


# ---------------------------------------------------------------------------
# 7. get_all with a single page (no next_page)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_get_all_single_page():
    client = make_client()
    respx.get(f"{BASE_URL}/api/v2/macros.json").mock(
        return_value=httpx.Response(
            200,
            json={"macros": [{"id": 10}, {"id": 11}], "next_page": None},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    results = await client.get_all("/api/v2/macros.json", data_key="macros")

    assert results == [{"id": 10}, {"id": 11}]
    await client.close()


# ---------------------------------------------------------------------------
# 8. search follows pagination across multiple pages
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_search_follows_pagination():
    client = make_client()

    page2_url = f"{BASE_URL}/api/v2/search.json?page=2"

    # Register page 2 first (more specific)
    respx.get(page2_url).mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"id": 2, "type": "ticket"}], "next_page": None},
            headers=RATE_LIMIT_HEADERS,
        )
    )
    # Generic search route (page 1)
    respx.get(f"{BASE_URL}/api/v2/search.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [{"id": 1, "type": "ticket"}],
                "next_page": page2_url,
            },
            headers=RATE_LIMIT_HEADERS,
        )
    )

    results = await client.search("type:ticket status:open")

    assert len(results) == 2
    assert results[0] == {"id": 1, "type": "ticket"}
    assert results[1] == {"id": 2, "type": "ticket"}
    await client.close()


# ---------------------------------------------------------------------------
# 9. is_configured() checks environment variables
# ---------------------------------------------------------------------------
def test_is_configured_checks_env():
    # Ensure the vars are NOT set
    for var in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_API_TOKEN"):
        os.environ.pop(var, None)

    assert ZendeskClient.is_configured() is False

    # Set all three
    os.environ["ZENDESK_SUBDOMAIN"] = "myco"
    os.environ["ZENDESK_EMAIL"] = "admin@myco.com"
    os.environ["ZENDESK_API_TOKEN"] = "secret"

    assert ZendeskClient.is_configured() is True

    # Remove one — should be False again
    del os.environ["ZENDESK_API_TOKEN"]
    assert ZendeskClient.is_configured() is False

    # Clean up
    for var in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_API_TOKEN"):
        os.environ.pop(var, None)
