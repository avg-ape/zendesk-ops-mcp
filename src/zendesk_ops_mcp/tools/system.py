"""System tools: macro audit and trigger review."""

from __future__ import annotations

from collections import defaultdict

from zendesk_ops_mcp.models import (
    MacroAuditReport,
    MacroInfo,
    TriggerInfo,
    TriggerReviewReport,
)
from zendesk_ops_mcp.zendesk_client import ZendeskClient


async def macro_audit(client: ZendeskClient) -> MacroAuditReport:
    """Return an audit report for macros: active/inactive counts, duplicates, and unused."""
    raw_macros = await client.get_all("/api/v2/macros.json", data_key="macros")

    macros: list[MacroInfo] = []
    for raw in raw_macros:
        usage_7d = raw.get("usage_7d")
        macros.append(
            MacroInfo(
                id=raw["id"],
                title=raw.get("title") or "",
                active=raw.get("active", True),
                usage_7d=usage_7d,
            )
        )

    active_count = sum(1 for m in macros if m.active)
    inactive_count = sum(1 for m in macros if not m.active)

    # Find duplicates: group by title.lower(), any title appearing more than once
    title_groups: dict[str, list[MacroInfo]] = defaultdict(list)
    for m in macros:
        title_groups[m.title.lower()].append(m)

    duplicates: list[str] = []
    for title_lower, group in title_groups.items():
        if len(group) > 1:
            # Use the original title from the first entry in the group
            original_title = group[0].title
            duplicates.append(f"{original_title} ({len(group)} copies)")

    # Find unused: macros where usage_7d field exists and equals 0
    unused: list[MacroInfo] = [m for m in macros if m.usage_7d is not None and m.usage_7d == 0]

    return MacroAuditReport(
        total=len(macros),
        active_count=active_count,
        inactive_count=inactive_count,
        unused=unused,
        duplicates=duplicates,
    )


def _parse_trigger_info(raw: dict, category: str) -> TriggerInfo:
    """Map a raw trigger or automation dict to TriggerInfo."""
    conditions = raw.get("conditions") or {}
    conditions_count = len(conditions.get("all", [])) + len(conditions.get("any", []))
    return TriggerInfo(
        id=raw["id"],
        title=raw.get("title") or "",
        active=raw.get("active", True),
        conditions_count=conditions_count,
        category=category,
    )


async def trigger_review(
    client: ZendeskClient,
    include_automations: bool = True,
) -> TriggerReviewReport:
    """Return a review report of triggers (and optionally automations)."""
    raw_triggers = await client.get_all("/api/v2/triggers.json", data_key="triggers")

    trigger_infos: list[TriggerInfo] = [
        _parse_trigger_info(t, "trigger") for t in raw_triggers
    ]

    active_triggers = sum(1 for t in trigger_infos if t.active)
    inactive_triggers = sum(1 for t in trigger_infos if not t.active)

    automation_infos: list[TriggerInfo] = []
    active_automations = 0
    inactive_automations = 0
    total_automations = 0

    if include_automations:
        raw_automations = await client.get_all(
            "/api/v2/automations.json", data_key="automations"
        )
        automation_infos = [_parse_trigger_info(a, "automation") for a in raw_automations]
        active_automations = sum(1 for a in automation_infos if a.active)
        inactive_automations = sum(1 for a in automation_infos if not a.active)
        total_automations = len(automation_infos)

    all_infos = trigger_infos + automation_infos

    disabled = [ti for ti in all_infos if not ti.active]
    broad_conditions = [ti for ti in all_infos if ti.conditions_count == 0]

    return TriggerReviewReport(
        total_triggers=len(trigger_infos),
        total_automations=total_automations,
        active_triggers=active_triggers,
        inactive_triggers=inactive_triggers,
        active_automations=active_automations,
        inactive_automations=inactive_automations,
        disabled=disabled,
        broad_conditions=broad_conditions,
    )
