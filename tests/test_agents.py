"""Unit tests for agent tools using respx to mock HTTP calls."""

from __future__ import annotations

import pytest
import respx
import httpx

from zendesk_ops_mcp.zendesk_client import ZendeskClient
from zendesk_ops_mcp.tools.agents import agent_workload, group_distribution

BASE_URL = "https://test.zendesk.com"
RATE_LIMIT_HEADERS = {"X-RateLimit-Remaining": "180"}
SEARCH_URL = f"{BASE_URL}/api/v2/search.json"
USERS_URL = f"{BASE_URL}/api/v2/users.json"
GROUPS_URL = f"{BASE_URL}/api/v2/groups.json"


def make_client() -> ZendeskClient:
    return ZendeskClient(subdomain="test", email="t@t.com", api_token="tok")


def _make_search_response(results: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"results": results, "next_page": None, "count": len(results)},
        headers=RATE_LIMIT_HEADERS,
    )


# ---------------------------------------------------------------------------
# test_agent_workload
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_agent_workload():
    client = make_client()

    users_payload = {
        "users": [
            {"id": 1, "name": "Alice", "email": "a@t.com", "role": "agent", "default_group_id": 10, "active": True},
            {"id": 2, "name": "Bob", "email": "b@t.com", "role": "agent", "default_group_id": 10, "active": True},
        ],
        "next_page": None,
    }

    respx.get(USERS_URL).mock(
        return_value=httpx.Response(200, json=users_payload, headers=RATE_LIMIT_HEADERS)
    )

    # Search results: agent 1 has 2 tickets (high and normal priority), agent 2 has 0
    agent1_tickets = [
        {"id": 101, "priority": "high", "status": "open"},
        {"id": 102, "priority": "normal", "status": "open"},
    ]
    agent2_tickets: list[dict] = []

    search_call_count = 0

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal search_call_count
        query = dict(request.url.params).get("query", "")
        if "assignee:1" in query:
            results = agent1_tickets
        elif "assignee:2" in query:
            results = agent2_tickets
        else:
            results = []
        search_call_count += 1
        return _make_search_response(results)

    respx.get(SEARCH_URL).mock(side_effect=search_side_effect)

    report = await agent_workload(client)

    assert report.total_agents == 2
    assert report.agents[0].total_open == 2
    assert report.agents[1].total_open == 0
    assert report.overloaded == []

    await client.close()


# ---------------------------------------------------------------------------
# test_group_distribution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_group_distribution():
    client = make_client()

    groups_payload = {
        "groups": [{"id": 10, "name": "Support"}],
        "next_page": None,
    }

    respx.get(GROUPS_URL).mock(
        return_value=httpx.Response(200, json=groups_payload, headers=RATE_LIMIT_HEADERS)
    )

    # Return 2, 3, 1, 5 results for new, open, pending, solved respectively
    status_counts = {"new": 2, "open": 3, "pending": 1, "solved": 5}

    def search_side_effect(request: httpx.Request) -> httpx.Response:
        query = dict(request.url.params).get("query", "")
        results = []
        for status, count in status_counts.items():
            if f"status:{status}" in query:
                results = [{"id": i, "status": status} for i in range(count)]
                break
        return _make_search_response(results)

    respx.get(SEARCH_URL).mock(side_effect=search_side_effect)

    report = await group_distribution(client)

    assert len(report.groups) == 1
    group = report.groups[0]
    assert group.new_count == 2
    assert group.open_count == 3
    assert group.pending_count == 1
    assert group.solved_count == 5
    assert group.total == 11
    assert report.total_tickets == 11

    await client.close()
