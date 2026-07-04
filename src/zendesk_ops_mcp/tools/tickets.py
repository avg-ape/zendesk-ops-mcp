"""Ticket tools: triage, stale report, bulk tag, bulk close."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zendesk_ops_mcp.models import (
    BulkCloseResult,
    BulkTagResult,
    StaleTicketReport,
    TicketSummary,
    TriageReport,
)
from zendesk_ops_mcp.zendesk_client import ZendeskClient

UTC = timezone.utc


def _parse_ticket(raw: dict) -> TicketSummary:
    """Map a Zendesk API ticket JSON dict to a TicketSummary."""
    return TicketSummary(
        id=raw["id"],
        subject=raw.get("subject") or "",
        status=raw.get("status") or "",
        priority=raw.get("priority"),
        requester_id=raw.get("requester_id"),
        assignee_id=raw.get("assignee_id"),
        group_id=raw.get("group_id"),
        tags=raw.get("tags") or [],
        created_at=raw.get("created_at") or "",
        updated_at=raw.get("updated_at") or "",
    )


async def ticket_triage(client: ZendeskClient, status: str = "new,open") -> TriageReport:
    """Return a triage report highlighting tickets missing assignee, group, or priority."""
    status_parts = " ".join(f"status:{s.strip()}" for s in status.split(","))
    query = f"type:ticket {status_parts}"

    raw_results = await client.search(query)
    tickets = [_parse_ticket(r) for r in raw_results]

    missing_assignee = [t for t in tickets if t.assignee_id is None]
    missing_group = [t for t in tickets if t.group_id is None]
    missing_priority = [t for t in tickets if t.priority is None]

    # total_untriaged = unique ticket IDs across all three lists
    untriaged_ids = (
        {t.id for t in missing_assignee}
        | {t.id for t in missing_group}
        | {t.id for t in missing_priority}
    )

    return TriageReport(
        total_untriaged=len(untriaged_ids),
        missing_assignee=missing_assignee,
        missing_group=missing_group,
        missing_priority=missing_priority,
    )


async def stale_ticket_report(
    client: ZendeskClient,
    hours: int = 24,
    priority: str | None = None,
) -> StaleTicketReport:
    """Return a report of open/new tickets not updated within the given hours."""
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = f"type:ticket status:open status:new updated<{cutoff}"
    if priority:
        query += f" priority:{priority}"

    raw_results = await client.search(query)
    tickets = [_parse_ticket(r) for r in raw_results]

    by_group: dict[str, int] = {}
    by_priority: dict[str, int] = {}

    for t in tickets:
        group_key = str(t.group_id) if t.group_id is not None else "unassigned"
        by_group[group_key] = by_group.get(group_key, 0) + 1

        priority_key = t.priority if t.priority is not None else "unassigned"
        by_priority[priority_key] = by_priority.get(priority_key, 0) + 1

    return StaleTicketReport(
        total_stale=len(tickets),
        threshold_hours=hours,
        by_group=by_group,
        by_priority=by_priority,
        tickets=tickets,
    )


async def bulk_tag_tickets(
    client: ZendeskClient,
    query: str,
    tags: list[str],
    dry_run: bool = True,
) -> BulkTagResult:
    """Search for tickets and apply additional tags, optionally as a dry run."""
    raw_results = await client.search(query)
    tickets = [_parse_ticket(r) for r in raw_results]

    if not dry_run and tickets:
        ids = ",".join(str(t.id) for t in tickets)
        await client.put(
            f"/api/v2/tickets/update_many.json?ids={ids}",
            json={"ticket": {"additional_tags": tags}},
        )

    return BulkTagResult(
        query=query,
        tags=tags,
        affected=tickets,
        count=len(tickets),
        dry_run=dry_run,
    )


async def bulk_close_tickets(
    client: ZendeskClient,
    status_filter: str,
    older_than_days: int,
    comment: str | None = None,
    dry_run: bool = True,
) -> BulkCloseResult:
    """Search for tickets and close them, optionally as a dry run."""
    cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).strftime("%Y-%m-%d")
    query = f"type:ticket status:{status_filter} updated<{cutoff}"

    raw_results = await client.search(query)
    tickets = [_parse_ticket(r) for r in raw_results]

    if not dry_run and tickets:
        ids = ",".join(str(t.id) for t in tickets)
        ticket_update: dict = {"status": "closed"}
        if comment:
            ticket_update["comment"] = {"body": comment, "public": False}
        await client.put(
            f"/api/v2/tickets/update_many.json?ids={ids}",
            json={"ticket": ticket_update},
        )

    return BulkCloseResult(
        status_filter=status_filter,
        older_than_days=older_than_days,
        closed=tickets,
        count=len(tickets),
        dry_run=dry_run,
    )
