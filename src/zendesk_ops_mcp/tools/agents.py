"""Agent tools: workload report and group distribution."""

from __future__ import annotations

from zendesk_ops_mcp.models import (
    AgentSummary,
    AgentWorkload,
    GroupDistribution,
    GroupStatus,
    WorkloadReport,
)
from zendesk_ops_mcp.zendesk_client import ZendeskClient


def _parse_agent(raw: dict) -> AgentSummary:
    """Map a Zendesk API user JSON dict to an AgentSummary."""
    return AgentSummary(
        id=raw["id"],
        name=raw.get("name") or "",
        email=raw.get("email") or "",
        role=raw.get("role") or "",
        default_group_id=raw.get("default_group_id"),
        active=raw.get("active", True),
    )


async def agent_workload(
    client: ZendeskClient,
    group_id: int | None = None,
) -> WorkloadReport:
    """Return a workload report for agents, optionally filtered by group."""
    raw_users = await client.get_all(
        "/api/v2/users.json",
        params={"role": "agent"},
        data_key="users",
    )

    agents = [_parse_agent(u) for u in raw_users]

    if group_id is not None:
        agents = [a for a in agents if a.default_group_id == group_id]

    # Cap to first 20 agents to avoid excessive API calls
    agents = agents[:20]

    agent_workloads: list[AgentWorkload] = []

    for agent in agents:
        tickets = await client.search(f"type:ticket status:open assignee:{agent.id}")

        by_priority: dict[str, int] = {}
        for ticket in tickets:
            priority = ticket.get("priority") or "none"
            by_priority[priority] = by_priority.get(priority, 0) + 1

        agent_workloads.append(
            AgentWorkload(
                agent=agent,
                total_open=len(tickets),
                by_priority=by_priority,
            )
        )

    overloaded = [aw for aw in agent_workloads if aw.total_open > 25]

    return WorkloadReport(
        agents=agent_workloads,
        total_agents=len(agent_workloads),
        overloaded=overloaded,
    )


async def group_distribution(client: ZendeskClient) -> GroupDistribution:
    """Return ticket distribution across all groups by status."""
    raw_groups = await client.get_all("/api/v2/groups.json", data_key="groups")

    group_statuses: list[GroupStatus] = []
    total_tickets = 0

    for raw_group in raw_groups:
        group_id = raw_group["id"]
        name = raw_group.get("name") or ""

        new_tickets = await client.search(f"type:ticket group:{group_id} status:new")
        open_tickets = await client.search(f"type:ticket group:{group_id} status:open")
        pending_tickets = await client.search(f"type:ticket group:{group_id} status:pending")
        solved_tickets = await client.search(f"type:ticket group:{group_id} status:solved")

        new_count = len(new_tickets)
        open_count = len(open_tickets)
        pending_count = len(pending_tickets)
        solved_count = len(solved_tickets)
        total = new_count + open_count + pending_count + solved_count

        total_tickets += total

        group_statuses.append(
            GroupStatus(
                name=name,
                group_id=group_id,
                new_count=new_count,
                open_count=open_count,
                pending_count=pending_count,
                solved_count=solved_count,
                total=total,
            )
        )

    return GroupDistribution(
        groups=group_statuses,
        total_tickets=total_tickets,
    )
