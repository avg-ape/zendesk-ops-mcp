"""Unit tests for system tools using respx to mock HTTP calls."""

from __future__ import annotations

import pytest
import respx
import httpx

from zendesk_ops_mcp.zendesk_client import ZendeskClient
from zendesk_ops_mcp.tools.system import macro_audit, trigger_review

BASE_URL = "https://test.zendesk.com"
RATE_LIMIT_HEADERS = {"X-RateLimit-Remaining": "180"}
MACROS_URL = f"{BASE_URL}/api/v2/macros.json"
TRIGGERS_URL = f"{BASE_URL}/api/v2/triggers.json"
AUTOMATIONS_URL = f"{BASE_URL}/api/v2/automations.json"


def make_client() -> ZendeskClient:
    return ZendeskClient(subdomain="test", email="t@t.com", api_token="tok")


# ---------------------------------------------------------------------------
# test_macro_audit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_macro_audit():
    client = make_client()

    macros_payload = {
        "macros": [
            {"id": 1, "title": "Close and redirect", "active": True, "usage_7d": 15},
            {"id": 2, "title": "Close and redirect", "active": True, "usage_7d": 8},
            {"id": 3, "title": "Escalate to T2", "active": False, "usage_7d": 0},
        ],
        "next_page": None,
    }

    respx.get(MACROS_URL).mock(
        return_value=httpx.Response(200, json=macros_payload, headers=RATE_LIMIT_HEADERS)
    )

    report = await macro_audit(client)

    assert report.total == 3
    assert report.active_count == 2
    assert report.inactive_count == 1

    # Duplicates: "Close and redirect" appears twice
    assert len(report.duplicates) == 1
    assert "Close and redirect" in report.duplicates[0]

    # Unused: "Escalate to T2" has usage_7d == 0
    assert len(report.unused) == 1
    assert report.unused[0].title == "Escalate to T2"

    await client.close()


# ---------------------------------------------------------------------------
# test_trigger_review
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_trigger_review():
    client = make_client()

    triggers_payload = {
        "triggers": [
            {"id": 1, "title": "Auto-assign VIP", "active": True, "conditions": {"all": [{"field": "priority"}], "any": []}},
            {"id": 2, "title": "Catch-all", "active": True, "conditions": {"all": [], "any": []}},
            {"id": 3, "title": "Old rule", "active": False, "conditions": {"all": [{"field": "status"}], "any": []}},
        ],
        "next_page": None,
    }

    automations_payload = {
        "automations": [
            {"id": 10, "title": "Auto-close", "active": True, "conditions": {"all": [{"field": "status"}], "any": []}},
        ],
        "next_page": None,
    }

    respx.get(TRIGGERS_URL).mock(
        return_value=httpx.Response(200, json=triggers_payload, headers=RATE_LIMIT_HEADERS)
    )
    respx.get(AUTOMATIONS_URL).mock(
        return_value=httpx.Response(200, json=automations_payload, headers=RATE_LIMIT_HEADERS)
    )

    report = await trigger_review(client, include_automations=True)

    assert report.total_triggers == 3
    assert report.total_automations == 1
    assert report.active_triggers == 2
    assert report.inactive_triggers == 1

    # disabled: only "Old rule" is inactive
    assert len(report.disabled) == 1
    assert report.disabled[0].title == "Old rule"

    # broad_conditions: only "Catch-all" has 0 conditions
    assert len(report.broad_conditions) == 1
    assert report.broad_conditions[0].title == "Catch-all"

    await client.close()
