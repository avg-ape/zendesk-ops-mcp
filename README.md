# zendesk-ops-mcp

An MCP server that provides operational tooling over the Zendesk Support API — ticket triage, SLA monitoring, agent workload analysis, and system health audits. Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or Claude Desktop, it gives support ops teams a conversational interface to automate the manual toil of managing Zendesk workflows.

## Quick Start

```bash
git clone https://github.com/avg-ape/zendesk-ops-mcp.git
cd zendesk-ops-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Configure your Zendesk credentials:

```bash
cp .env.example .env
# Edit .env with your subdomain, email, and API token
```

You can get a free Zendesk trial at [zendesk.com/register](https://www.zendesk.com/register/). Enable API tokens in Admin Center > Apps & Integrations > APIs.

### Use with Claude Code

Add to your Claude Code MCP config (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "zendesk-ops": {
      "command": "/path/to/zendesk-ops-mcp/.venv/bin/python",
      "args": ["-m", "zendesk_ops_mcp.server"],
      "env": {
        "ZENDESK_SUBDOMAIN": "your-subdomain",
        "ZENDESK_EMAIL": "your-email@example.com",
        "ZENDESK_API_TOKEN": "your-api-token"
      }
    }
  }
}
```

Then ask Claude things like:
- "Triage open tickets — what's missing assignees or priorities?"
- "Show me tickets that have gone stale in the last 12 hours"
- "What's the CSAT score over the last 30 days, broken down by agent?"
- "Audit our macros — are there any duplicates or unused ones?"
- "Which agents are overloaded right now?"

## Tools

| Tool | Description |
|------|-------------|
| `ticket_triage` | Find tickets missing assignees, groups, or priorities |
| `stale_ticket_report` | Tickets with no update in N hours, grouped by group/priority |
| `bulk_tag_tickets` | Tag tickets matching a search query (dry-run by default) |
| `bulk_close_tickets` | Close old solved/pending tickets (dry-run by default) |
| `sla_breach_report` | Tickets breaching or approaching SLA targets |
| `csat_summary` | Satisfaction scores over a period, by agent |
| `response_time_analysis` | First-response and resolution time averages |
| `agent_workload` | Open tickets per agent with priority breakdown |
| `group_distribution` | Ticket volume and status breakdown across groups |
| `macro_audit` | Find unused or duplicate macros |
| `trigger_review` | Audit active triggers and automations |

## Architecture

**Zendesk Client (`zendesk_client.py`):** Async HTTP client built on `httpx` with Basic auth (API token). Handles both offset pagination (`next_page`) and cursor pagination for search endpoints. Rate limit tracking via `X-RateLimit-Remaining` headers.

**Pydantic Models (`models.py`):** All tool outputs are typed Pydantic models with human-readable `__str__` methods. Claude gets structured data to reason about, not raw JSON.

**Dual Pagination:** Zendesk uses offset pagination for list endpoints (`/api/v2/tickets.json`) and search-specific pagination. The client handles both transparently via `get_all()` and `search()` methods.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run unit tests
pytest tests/ -v

# Run integration tests (requires Zendesk credentials)
pytest tests/ -v --integration
```

## License

MIT
