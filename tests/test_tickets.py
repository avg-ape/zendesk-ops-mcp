"""Unit tests for ticket tools using respx to mock HTTP calls."""

from __future__ import annotations

import pytest
import respx
import httpx

from zendesk_ops_mcp.zendesk_client import ZendeskClient
from zendesk_ops_mcp.tools.tickets import (
    ticket_triage,
    stale_ticket_report,
    bulk_tag_tickets,
    bulk_close_tickets,
)

BASE_URL = "https://test.zendesk.com"
RATE_LIMIT_HEADERS = {"X-RateLimit-Remaining": "180"}
SEARCH_URL = f"{BASE_URL}/api/v2/search.json"


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
# test_ticket_triage_finds_untriaged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_ticket_triage_finds_untriaged():
    client = make_client()

    ticket1 = _make_ticket(1, subject="No assignee, group, or priority",
                           assignee_id=None, group_id=None, priority=None)
    ticket2 = _make_ticket(2, subject="Has assignee, no priority",
                           assignee_id=500, group_id=300, priority=None)
    ticket3 = _make_ticket(3, subject="Fully triaged",
                           assignee_id=200, group_id=300, priority="normal")

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket1, ticket2, ticket3], "next_page": None, "count": 3},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    report = await ticket_triage(client)

    # Tickets 1 and 2 are untriaged (each missing at least one field)
    assert report.total_untriaged == 2

    # Ticket 1 has no assignee
    missing_assignee_ids = [t.id for t in report.missing_assignee]
    assert 1 in missing_assignee_ids
    assert 2 not in missing_assignee_ids

    # Tickets 1 and 2 have no priority
    missing_priority_ids = [t.id for t in report.missing_priority]
    assert 1 in missing_priority_ids
    assert 2 in missing_priority_ids
    assert 3 not in missing_priority_ids

    await client.close()


# ---------------------------------------------------------------------------
# test_ticket_triage_empty
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_ticket_triage_empty():
    client = make_client()

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [], "next_page": None, "count": 0},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    report = await ticket_triage(client)

    assert report.total_untriaged == 0
    assert report.missing_assignee == []
    assert report.missing_group == []
    assert report.missing_priority == []

    await client.close()


# ---------------------------------------------------------------------------
# test_stale_ticket_report
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_stale_ticket_report():
    client = make_client()

    ticket = _make_ticket(10, subject="Stale ticket", priority="high", group_id=42,
                          updated_at="2025-12-01T00:00:00Z")

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket], "next_page": None, "count": 1},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    report = await stale_ticket_report(client, hours=48)

    assert report.total_stale == 1
    assert report.threshold_hours == 48
    assert "high" in report.by_priority
    assert report.by_priority["high"] == 1

    await client.close()


# ---------------------------------------------------------------------------
# test_bulk_tag_dry_run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_bulk_tag_dry_run():
    client = make_client()

    ticket1 = _make_ticket(20, subject="Ticket A")
    ticket2 = _make_ticket(21, subject="Ticket B")

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket1, ticket2], "next_page": None, "count": 2},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    result = await bulk_tag_tickets(client, query="type:ticket tag:needs-review",
                                    tags=["reviewed"], dry_run=True)

    assert result.count == 2
    assert result.dry_run is True

    # Verify no PUT was made
    put_calls = [call for call in respx.calls if call.request.method == "PUT"]
    assert len(put_calls) == 0

    await client.close()


# ---------------------------------------------------------------------------
# test_bulk_close_dry_run
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_bulk_close_dry_run():
    client = make_client()

    ticket1 = _make_ticket(30, subject="Old solved ticket A", status="solved")
    ticket2 = _make_ticket(31, subject="Old solved ticket B", status="solved")

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket1, ticket2], "next_page": None, "count": 2},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    result = await bulk_close_tickets(
        client,
        status_filter="solved",
        older_than_days=30,
        dry_run=True,
    )

    assert result.count == 2
    assert result.dry_run is True

    # Verify no PUT was made
    put_calls = [call for call in respx.calls if call.request.method == "PUT"]
    assert len(put_calls) == 0

    await client.close()


# ---------------------------------------------------------------------------
# test_bulk_tag_applies_tags
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_bulk_tag_applies_tags():
    client = make_client()

    ticket = _make_ticket(100, subject="Needs escalation")

    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"results": [ticket], "next_page": None, "count": 1},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    update_many_url = f"{BASE_URL}/api/v2/tickets/update_many.json"
    respx.put(url__regex=r".*/api/v2/tickets/update_many\.json.*").mock(
        return_value=httpx.Response(
            200,
            json={"job_status": {"id": "abc"}},
            headers=RATE_LIMIT_HEADERS,
        )
    )

    result = await bulk_tag_tickets(
        client,
        query="type:ticket tag:needs-escalation",
        tags=["escalated"],
        dry_run=False,
    )

    assert result.count == 1
    assert result.dry_run is False

    # Verify the PUT was actually called
    assert respx.calls.call_count >= 2

    await client.close()
