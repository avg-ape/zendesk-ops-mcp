"""Performance tools: SLA breach report, CSAT summary, response time analysis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zendesk_ops_mcp.models import (
    CSATSummary,
    ResponseTimeAnalysis,
    SLABreachReport,
    TicketSummary,
)
from zendesk_ops_mcp.tools.tickets import _parse_ticket
from zendesk_ops_mcp.zendesk_client import ZendeskAPIError, ZendeskClient

UTC = timezone.utc


async def sla_breach_report(client: ZendeskClient, hours_ahead: int = 4) -> SLABreachReport:
    """Return an SLA breach report for open/new tickets.

    Fetches up to 50 tickets, checks their reply_time_in_minutes.calendar metric,
    and classifies each as breached (>480 min) or approaching (within hours_ahead
    of the 480-minute threshold).
    """
    raw_tickets = await client.search("type:ticket status:open status:new")
    raw_tickets = raw_tickets[:50]

    breach_threshold = 480  # 8 hours in minutes
    approach_threshold = breach_threshold - hours_ahead * 60

    breached: list[TicketSummary] = []
    approaching: list[TicketSummary] = []
    by_priority: dict[str, int] = {}
    by_group: dict[str, int] = {}

    for raw in raw_tickets:
        ticket = _parse_ticket(raw)

        try:
            metrics_resp = await client.get(f"/api/v2/tickets/{ticket.id}/metrics.json")
            metric = metrics_resp.get("ticket_metric", {})
            reply_time_obj = metric.get("reply_time_in_minutes")
            if reply_time_obj is None:
                continue
            reply_time = reply_time_obj.get("calendar")
            if reply_time is None:
                continue
        except (ZendeskAPIError, Exception):
            continue

        priority_key = ticket.priority if ticket.priority is not None else "none"
        group_key = str(ticket.group_id) if ticket.group_id is not None else "none"

        if reply_time > breach_threshold:
            breached.append(ticket)
            by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
            by_group[group_key] = by_group.get(group_key, 0) + 1
        elif reply_time > approach_threshold:
            approaching.append(ticket)
            by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
            by_group[group_key] = by_group.get(group_key, 0) + 1

    return SLABreachReport(
        breached=breached,
        approaching=approaching,
        by_priority=by_priority,
        by_group=by_group,
    )


async def csat_summary(client: ZendeskClient, days: int = 30) -> CSATSummary:
    """Return a CSAT summary for the given period.

    Fetches satisfaction ratings since (now - days), counts good/bad responses,
    and groups results by assignee_id.
    """
    start_time = int((datetime.now(UTC) - timedelta(days=days)).timestamp())

    ratings = await client.get_all(
        "/api/v2/satisfaction_ratings.json",
        params={"start_time": start_time},
        data_key="satisfaction_ratings",
    )

    good_count = 0
    bad_count = 0
    # by_agent: str(assignee_id) -> {"good": int, "bad": int, "rate": float}
    by_agent: dict[str, dict] = {}

    for rating in ratings:
        score = rating.get("score")
        if score not in ("good", "bad"):
            continue

        assignee_id = rating.get("assignee_id")
        agent_key = str(assignee_id) if assignee_id is not None else "none"

        if agent_key not in by_agent:
            by_agent[agent_key] = {"good": 0, "bad": 0, "rate": 0.0}

        if score == "good":
            good_count += 1
            by_agent[agent_key]["good"] += 1
        else:
            bad_count += 1
            by_agent[agent_key]["bad"] += 1

    # Compute per-agent satisfaction rates
    for stats in by_agent.values():
        total = stats["good"] + stats["bad"]
        stats["rate"] = stats["good"] / total if total > 0 else 0.0

    total_responses = good_count + bad_count
    satisfaction_rate = good_count / total_responses if total_responses > 0 else 0.0

    return CSATSummary(
        period_days=days,
        total_responses=total_responses,
        good_count=good_count,
        bad_count=bad_count,
        satisfaction_rate=satisfaction_rate,
        by_agent=by_agent,
    )


async def response_time_analysis(client: ZendeskClient, days: int = 7) -> ResponseTimeAnalysis:
    """Return response time analysis for solved tickets in the given period.

    Fetches up to 50 solved tickets and their metrics, computing average first
    response and resolution times overall and broken down by priority and group.
    """
    cutoff_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    raw_tickets = await client.search(f"type:ticket status:solved solved>{cutoff_date}")
    raw_tickets = raw_tickets[:50]

    first_response_hours: list[float] = []
    resolution_hours: list[float] = []

    # priority_key -> {"first": [float], "resolution": [float]}
    priority_data: dict[str, dict[str, list[float]]] = {}
    # group_key -> {"first": [float], "resolution": [float]}
    group_data: dict[str, dict[str, list[float]]] = {}

    for raw in raw_tickets:
        ticket = _parse_ticket(raw)

        try:
            metrics_resp = await client.get(f"/api/v2/tickets/{ticket.id}/metrics.json")
            metric = metrics_resp.get("ticket_metric", {})

            reply_obj = metric.get("reply_time_in_minutes")
            resolution_obj = metric.get("full_resolution_time_in_minutes")

            if reply_obj is None or resolution_obj is None:
                continue

            reply_min = reply_obj.get("calendar")
            resolution_min = resolution_obj.get("calendar")

            if reply_min is None or resolution_min is None:
                continue
        except (ZendeskAPIError, Exception):
            continue

        first_h = round(reply_min / 60.0, 1)
        resolution_h = round(resolution_min / 60.0, 1)

        first_response_hours.append(first_h)
        resolution_hours.append(resolution_h)

        priority_key = ticket.priority if ticket.priority is not None else "none"
        if priority_key not in priority_data:
            priority_data[priority_key] = {"first": [], "resolution": []}
        priority_data[priority_key]["first"].append(first_h)
        priority_data[priority_key]["resolution"].append(resolution_h)

        group_key = str(ticket.group_id) if ticket.group_id is not None else "none"
        if group_key not in group_data:
            group_data[group_key] = {"first": [], "resolution": []}
        group_data[group_key]["first"].append(first_h)
        group_data[group_key]["resolution"].append(resolution_h)

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    avg_first_response_hours = _avg(first_response_hours)
    avg_resolution_hours = _avg(resolution_hours)

    by_priority: dict[str, dict] = {
        k: {
            "avg_first_response_hours": _avg(v["first"]),
            "avg_resolution_hours": _avg(v["resolution"]),
        }
        for k, v in priority_data.items()
    }

    by_group: dict[str, dict] = {
        k: {
            "avg_first_response_hours": _avg(v["first"]),
            "avg_resolution_hours": _avg(v["resolution"]),
        }
        for k, v in group_data.items()
    }

    return ResponseTimeAnalysis(
        period_days=days,
        avg_first_response_hours=avg_first_response_hours,
        avg_resolution_hours=avg_resolution_hours,
        by_priority=by_priority,
        by_group=by_group,
    )
