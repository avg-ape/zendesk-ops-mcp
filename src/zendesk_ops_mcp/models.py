"""Pydantic models for Zendesk Ops MCP tool inputs and outputs."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------


class TicketSummary(BaseModel):
    id: int
    subject: str
    status: str
    priority: str | None = None
    requester_id: int | None = None
    assignee_id: int | None = None
    group_id: int | None = None
    tags: list[str] = []
    created_at: str
    updated_at: str

    def __str__(self) -> str:
        group_part = f", group: {self.group_id}" if self.group_id is not None else ""
        priority_part = self.priority or "none"
        return f"#{self.id} {self.subject} ({self.status}, {priority_part}{group_part})"


class AgentSummary(BaseModel):
    id: int
    name: str
    email: str
    role: str
    default_group_id: int | None = None
    active: bool

    def __str__(self) -> str:
        status = "active" if self.active else "inactive"
        return f"{self.name} ({self.email}, {self.role}, {status})"


class GroupSummary(BaseModel):
    id: int
    name: str

    def __str__(self) -> str:
        return f"{self.name} (id: {self.id})"


# ---------------------------------------------------------------------------
# Ticket tool outputs
# ---------------------------------------------------------------------------


class TriageReport(BaseModel):
    total_untriaged: int
    missing_assignee: list[TicketSummary] = []
    missing_group: list[TicketSummary] = []
    missing_priority: list[TicketSummary] = []

    def __str__(self) -> str:
        lines: list[str] = [f"Triage Report — {self.total_untriaged} untriaged ticket(s)"]
        lines.append("")

        lines.append(f"Missing Assignee ({len(self.missing_assignee)}):")
        for t in self.missing_assignee:
            lines.append(f"  {t}")

        lines.append("")
        lines.append(f"Missing Group ({len(self.missing_group)}):")
        for t in self.missing_group:
            lines.append(f"  {t}")

        lines.append("")
        lines.append(f"Missing Priority ({len(self.missing_priority)}):")
        for t in self.missing_priority:
            lines.append(f"  {t}")

        return "\n".join(lines)


class StaleTicketReport(BaseModel):
    total_stale: int
    threshold_hours: int
    by_group: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    tickets: list[TicketSummary] = []

    def __str__(self) -> str:
        lines: list[str] = [
            f"Stale Ticket Report — {self.total_stale} ticket(s) older than {self.threshold_hours}h"
        ]
        if self.by_group:
            lines.append("By Group: " + ", ".join(f"{k}: {v}" for k, v in self.by_group.items()))
        if self.by_priority:
            lines.append(
                "By Priority: " + ", ".join(f"{k}: {v}" for k, v in self.by_priority.items())
            )
        for t in self.tickets:
            lines.append(f"  {t}")
        return "\n".join(lines)


class BulkTagResult(BaseModel):
    query: str
    tags: list[str]
    affected: list[TicketSummary] = []
    count: int
    dry_run: bool

    def __str__(self) -> str:
        prefix = "DRY RUN" if self.dry_run else "APPLIED"
        tag_str = ", ".join(self.tags)
        lines: list[str] = [
            f"[{prefix}] Bulk Tag — query: {self.query!r}, tags: [{tag_str}], {self.count} ticket(s)"
        ]
        for t in self.affected:
            lines.append(f"  {t}")
        return "\n".join(lines)


class BulkCloseResult(BaseModel):
    status_filter: str
    older_than_days: int
    closed: list[TicketSummary] = []
    count: int
    dry_run: bool

    def __str__(self) -> str:
        prefix = "DRY RUN" if self.dry_run else "APPLIED"
        lines: list[str] = [
            f"[{prefix}] Bulk Close — status: {self.status_filter!r}, "
            f"older than {self.older_than_days} day(s), {self.count} ticket(s)"
        ]
        for t in self.closed:
            lines.append(f"  {t}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Performance tool outputs
# ---------------------------------------------------------------------------


class SLABreachReport(BaseModel):
    breached: list[TicketSummary] = []
    approaching: list[TicketSummary] = []
    by_priority: dict[str, int] = {}
    by_group: dict[str, int] = {}

    def __str__(self) -> str:
        lines: list[str] = [
            f"SLA Breach Report — {len(self.breached)} breached, {len(self.approaching)} approaching"
        ]
        lines.append(f"\nBreached ({len(self.breached)}):")
        for t in self.breached:
            lines.append(f"  {t}")
        lines.append(f"\nApproaching ({len(self.approaching)}):")
        for t in self.approaching:
            lines.append(f"  {t}")
        if self.by_priority:
            lines.append(
                "\nBy Priority: " + ", ".join(f"{k}: {v}" for k, v in self.by_priority.items())
            )
        if self.by_group:
            lines.append(
                "By Group: " + ", ".join(f"{k}: {v}" for k, v in self.by_group.items())
            )
        return "\n".join(lines)


class CSATSummary(BaseModel):
    period_days: int
    total_responses: int
    good_count: int
    bad_count: int
    satisfaction_rate: float
    # by_agent: agent name -> {good, bad, rate}
    by_agent: dict[str, dict] = {}

    def __str__(self) -> str:
        lines: list[str] = [
            f"CSAT Summary — {self.period_days}-day period",
            f"Responses: {self.total_responses} total, {self.good_count} good, {self.bad_count} bad",
            f"Satisfaction rate: {self.satisfaction_rate:.1%}",
        ]
        if self.by_agent:
            lines.append("By Agent:")
            for agent, stats in self.by_agent.items():
                rate = stats.get("rate", 0)
                lines.append(
                    f"  {agent}: {stats.get('good', 0)} good, {stats.get('bad', 0)} bad, {rate:.1%}"
                )
        return "\n".join(lines)


class ResponseTimeAnalysis(BaseModel):
    period_days: int
    avg_first_response_hours: float
    avg_resolution_hours: float
    # by_priority / by_group: key -> {avg_first_response_hours, avg_resolution_hours}
    by_priority: dict[str, dict] = {}
    by_group: dict[str, dict] = {}

    def __str__(self) -> str:
        lines: list[str] = [
            f"Response Time Analysis — {self.period_days}-day period",
            f"Avg first response: {self.avg_first_response_hours:.1f}h",
            f"Avg resolution: {self.avg_resolution_hours:.1f}h",
        ]
        if self.by_priority:
            lines.append("By Priority:")
            for key, stats in self.by_priority.items():
                lines.append(
                    f"  {key}: first {stats.get('avg_first_response_hours', 0):.1f}h, "
                    f"resolution {stats.get('avg_resolution_hours', 0):.1f}h"
                )
        if self.by_group:
            lines.append("By Group:")
            for key, stats in self.by_group.items():
                lines.append(
                    f"  {key}: first {stats.get('avg_first_response_hours', 0):.1f}h, "
                    f"resolution {stats.get('avg_resolution_hours', 0):.1f}h"
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent tool outputs
# ---------------------------------------------------------------------------


class AgentWorkload(BaseModel):
    agent: AgentSummary
    total_open: int
    by_priority: dict[str, int] = {}

    def __str__(self) -> str:
        priority_str = ", ".join(f"{k}: {v}" for k, v in self.by_priority.items())
        return f"{self.agent.name} — {self.total_open} open [{priority_str}]"


class WorkloadReport(BaseModel):
    agents: list[AgentWorkload] = []
    total_agents: int
    overloaded: list[AgentWorkload] = []  # >25 open tickets

    def __str__(self) -> str:
        lines: list[str] = [
            f"Workload Report — {self.total_agents} agent(s), {len(self.overloaded)} overloaded"
        ]
        lines.append("")
        lines.append("All Agents:")
        for aw in self.agents:
            lines.append(f"  {aw}")
        if self.overloaded:
            lines.append("")
            lines.append("Overloaded (>25 open):")
            for aw in self.overloaded:
                lines.append(f"  {aw}")
        return "\n".join(lines)


class GroupStatus(BaseModel):
    name: str
    group_id: int
    new_count: int
    open_count: int
    pending_count: int
    solved_count: int
    total: int

    def __str__(self) -> str:
        return (
            f"{self.name} (id: {self.group_id}) — "
            f"new: {self.new_count}, open: {self.open_count}, "
            f"pending: {self.pending_count}, solved: {self.solved_count}, total: {self.total}"
        )


class GroupDistribution(BaseModel):
    groups: list[GroupStatus] = []
    total_tickets: int

    def __str__(self) -> str:
        lines: list[str] = [f"Group Distribution — {self.total_tickets} total ticket(s)"]
        for g in self.groups:
            lines.append(f"  {g}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# System tool outputs
# ---------------------------------------------------------------------------


class MacroInfo(BaseModel):
    id: int
    title: str
    active: bool
    usage_7d: int | None = None

    def __str__(self) -> str:
        status = "active" if self.active else "inactive"
        usage = f", {self.usage_7d} uses/7d" if self.usage_7d is not None else ""
        return f"#{self.id} {self.title} ({status}{usage})"


class MacroAuditReport(BaseModel):
    total: int
    active_count: int
    inactive_count: int
    unused: list[MacroInfo] = []
    duplicates: list[str] = []

    def __str__(self) -> str:
        lines: list[str] = [
            f"Macro Audit Report — {self.total} total, {self.active_count} active, "
            f"{self.inactive_count} inactive"
        ]
        lines.append(f"Unused ({len(self.unused)}):")
        for m in self.unused:
            lines.append(f"  {m}")
        if self.duplicates:
            lines.append(f"Possible duplicates ({len(self.duplicates)}):")
            for d in self.duplicates:
                lines.append(f"  {d}")
        return "\n".join(lines)


class TriggerInfo(BaseModel):
    id: int
    title: str
    active: bool
    conditions_count: int
    category: str  # "trigger" or "automation"

    def __str__(self) -> str:
        status = "active" if self.active else "inactive"
        return (
            f"#{self.id} {self.title} ({self.category}, {status}, "
            f"{self.conditions_count} condition(s))"
        )


class TriggerReviewReport(BaseModel):
    total_triggers: int
    total_automations: int
    active_triggers: int
    inactive_triggers: int
    active_automations: int
    inactive_automations: int
    disabled: list[TriggerInfo] = []
    broad_conditions: list[TriggerInfo] = []

    def __str__(self) -> str:
        lines: list[str] = [
            f"Trigger Review Report",
            f"Triggers: {self.total_triggers} total ({self.active_triggers} active, "
            f"{self.inactive_triggers} inactive)",
            f"Automations: {self.total_automations} total ({self.active_automations} active, "
            f"{self.inactive_automations} inactive)",
        ]
        if self.disabled:
            lines.append(f"\nDisabled ({len(self.disabled)}):")
            for t in self.disabled:
                lines.append(f"  {t}")
        if self.broad_conditions:
            lines.append(f"\nBroad Conditions ({len(self.broad_conditions)}):")
            for t in self.broad_conditions:
                lines.append(f"  {t}")
        return "\n".join(lines)
