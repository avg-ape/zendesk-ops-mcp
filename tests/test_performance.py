"""Unit tests for performance tools using respx to mock HTTP calls."""

from __future__ import annotations

import pytest
import respx
import httpx

from zendesk_ops_mcp.zendesk_client import ZendeskClient
from zendesk_ops_mcp.tools.performance import (
    sla_breach_report,
    csat_summary,
    response_time_analysis,
)

BASE_URL = "https://test.zendesk.com"
RATE_LIMIT_HEADERS = {"X-RateLimit-Remaining": "180"}
SEARCH_URL = f"{BASE_URL}/api/v2/search.json"
CSAT_URL = f"{BASE_URL}/api/v2/satisfaction_ratings.json"


def make_client() -> ZendeskClient:
    return ZendeskClient(subdomain="test", email="t@t.com", api_token="tok")


def _make_ticket(
    id: int,
    subject: str = "Test ticket",
    status: str = "open",
    priority: str | None = "normal",
    requester_id: int = 100,
    assignee_id: int | None = 200,
    group_id: int | None = 300,
    tags: list[str] | None = None,
    created_at: str = "2026-01-01T00:00:00Z",
    updated_at: str = "2026-01-01T01:00:00Z",
) -> dict:
    return {
        "id": id,
        "subject": subject,
        "status": status,
        "priority": priority,
        "requester_id": requester_id,
        "assignee_id": assignee_id,
        "group_id": group_id,
        "tags": tags or [],
        "created_at": created_at,
        "updated_at": updated_at,
    }


# ---------------------------------------------------------------------------
# test_csat_summary
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_csat_summary():
    client = make_client()

    ratings_payload = {
        "satisfaction_ratings": [
            {"id": 1, "score": "good", "assignee_id": 100, "ticket_id": 10},
            {"id": 2, "score": "bad", "assignee_id": 100, "ticket_id": 11},
            {"id": 3, "score": "good", "assignee_id": 200, "ticket_id": 12},
        ],
        "next_page": None,
    }

    respx.get(CSAT_URL).mock(
        return_value=httpx.Response(200, json=ratings_payload, headers=RATE_LIMIT_HEADERS)
    )

    result = await csat_summary(client, days=30)

    assert result.total_responses == 3
    assert result.good_count == 2
    assert result.bad_count == 1
    assert abs(result.satisfaction_rate - 2 / 3) < 0.001
    assert len(result.by_agent) == 2

    await client.close()


# ---------------------------------------------------------------------------
# test_csat_summary_no_ratings
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_csat_summary_no_ratings():
    client = make_client()

    respx.get(CSAT_URL).mock(
        return_value=httpx.Response(
            200,
            json={"satisfaction_ratings": [], "next_page": None},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    result = await csat_summary(client, days=30)

    assert result.total_responses == 0
    assert result.good_count == 0
    assert result.bad_count == 0
    assert result.satisfaction_rate == 0.0

    await client.close()


# ---------------------------------------------------------------------------
# test_response_time_analysis
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_response_time_analysis():
    client = make_client()

    ticket = _make_ticket(100, status="solved", priority="high", group_id=10)

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket], "next_page": None, "count": 1},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    metrics_payload = {
        "ticket_metric": {
            "reply_time_in_minutes": {"calendar": 60},
            "full_resolution_time_in_minutes": {"calendar": 180},
        }
    }

    respx.get(f"{BASE_URL}/api/v2/tickets/100/metrics.json").mock(
        return_value=httpx.Response(200, json=metrics_payload, headers=RATE_LIMIT_HEADERS)
    )

    result = await response_time_analysis(client, days=7)

    assert result.avg_first_response_hours == 1.0
    assert result.avg_resolution_hours == 3.0
    assert "high" in result.by_priority
    assert result.by_priority["high"]["avg_first_response_hours"] == 1.0
    assert result.by_priority["high"]["avg_resolution_hours"] == 3.0

    await client.close()
