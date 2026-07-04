from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from zendesk_ops_mcp.zendesk_client import ZendeskClient, ZendeskAPIError
from zendesk_ops_mcp.tools import tickets, performance, agents, system

load_dotenv()

mcp = FastMCP("zendesk-ops")


def _error(message: str) -> str:
    return f"Error: {message}"


@mcp.tool()
async def ticket_triage(status: str = "new,open") -> str:
    """Find tickets missing assignees, groups, or priorities. Surfaces untriaged work."""
    client = ZendeskClient()
    try:
        report = await tickets.ticket_triage(client, status)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def stale_ticket_report(hours: int = 24, priority: str | None = None) -> str:
    """Find tickets with no update in N hours, grouped by group and priority."""
    client = ZendeskClient()
    try:
        report = await tickets.stale_ticket_report(client, hours, priority)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def bulk_tag_tickets(query: str, tags: list[str], dry_run: bool = True) -> str:
    """Tag tickets matching a Zendesk search query. Defaults to dry-run mode."""
    client = ZendeskClient()
    try:
        result = await tickets.bulk_tag_tickets(client, query, tags, dry_run)
        return str(result)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def bulk_close_tickets(status_filter: str, older_than_days: int, comment: str | None = None, dry_run: bool = True) -> str:
    """Close old solved/pending tickets. Defaults to dry-run mode."""
    client = ZendeskClient()
    try:
        result = await tickets.bulk_close_tickets(client, status_filter, older_than_days, comment, dry_run)
        return str(result)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def sla_breach_report(hours_ahead: int = 4) -> str:
    """Find tickets breaching or approaching SLA targets."""
    client = ZendeskClient()
    try:
        report = await performance.sla_breach_report(client, hours_ahead)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def csat_summary(days: int = 30) -> str:
    """Satisfaction scores over a period, broken down by agent."""
    client = ZendeskClient()
    try:
        report = await performance.csat_summary(client, days)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def response_time_analysis(days: int = 7) -> str:
    """Average first-response and resolution times, by priority and group."""
    client = ZendeskClient()
    try:
        report = await performance.response_time_analysis(client, days)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def agent_workload(group_id: int | None = None) -> str:
    """Open tickets per agent with priority breakdown. Highlights overloaded agents."""
    client = ZendeskClient()
    try:
        report = await agents.agent_workload(client, group_id)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def group_distribution() -> str:
    """Ticket volume and status breakdown across support groups."""
    client = ZendeskClient()
    try:
        report = await agents.group_distribution(client)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def macro_audit() -> str:
    """Find unused or duplicate macros that should be cleaned up."""
    client = ZendeskClient()
    try:
        report = await system.macro_audit(client)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


@mcp.tool()
async def trigger_review(include_automations: bool = True) -> str:
    """Audit active triggers and automations for issues."""
    client = ZendeskClient()
    try:
        report = await system.trigger_review(client, include_automations)
        return str(report)
    except ZendeskAPIError as e:
        return _error(e.message)
    finally:
        await client.close()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
