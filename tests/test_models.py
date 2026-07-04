"""Smoke tests for all Pydantic models in zendesk_ops_mcp.models."""

import pytest

from zendesk_ops_mcp.models import (
    AgentSummary,
    AgentWorkload,
    BulkCloseResult,
    BulkTagResult,
    CSATSummary,
    GroupDistribution,
    GroupStatus,
    GroupSummary,
    MacroAuditReport,
    MacroInfo,
    ResponseTimeAnalysis,
    SLABreachReport,
    StaleTicketReport,
    TicketSummary,
    TriageReport,
    TriggerInfo,
    TriggerReviewReport,
    WorkloadReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ticket(**overrides) -> TicketSummary:
    defaults = dict(
        id=123,
        subject="Login issue",
        status="open",
        priority="high",
        requester_id=1,
        assignee_id=None,
        group_id=456,
        tags=["vip"],
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-02T00:00:00Z",
    )
    defaults.update(overrides)
    return TicketSummary(**defaults)


def make_agent(**overrides) -> AgentSummary:
    defaults = dict(
        id=10,
        name="Alice Smith",
        email="alice@co.com",
        role="agent",
        default_group_id=1,
        active=True,
    )
    defaults.update(overrides)
    return AgentSummary(**defaults)


# ---------------------------------------------------------------------------
# TicketSummary
# ---------------------------------------------------------------------------

def test_ticket_summary_str_includes_id():
    t = make_ticket()
    assert "123" in str(t)


def test_ticket_summary_str_includes_subject():
    t = make_ticket()
    assert "Login issue" in str(t)


def test_ticket_summary_str_includes_status():
    t = make_ticket()
    assert "open" in str(t)


def test_ticket_summary_str_includes_group():
    t = make_ticket(group_id=456)
    assert "456" in str(t)


def test_ticket_summary_str_no_group():
    t = make_ticket(group_id=None)
    assert "group" not in str(t)


# ---------------------------------------------------------------------------
# AgentSummary
# ---------------------------------------------------------------------------

def test_agent_summary_str_includes_name():
    a = make_agent()
    assert "Alice Smith" in str(a)


def test_agent_summary_str_includes_role():
    a = make_agent()
    assert "agent" in str(a)


def test_agent_summary_str_includes_email():
    a = make_agent()
    assert "alice@co.com" in str(a)


def test_agent_summary_str_active():
    a = make_agent(active=True)
    assert "active" in str(a)


def test_agent_summary_str_inactive():
    a = make_agent(active=False)
    assert "inactive" in str(a)


# ---------------------------------------------------------------------------
# GroupSummary
# ---------------------------------------------------------------------------

def test_group_summary_str():
    g = GroupSummary(id=123, name="Support Tier 1")
    s = str(g)
    assert "Support Tier 1" in s
    assert "123" in s


# ---------------------------------------------------------------------------
# TriageReport
# ---------------------------------------------------------------------------

def test_triage_report_str_includes_count():
    t1 = make_ticket(id=1, subject="Ticket A", assignee_id=None)
    report = TriageReport(
        total_untriaged=3,
        missing_assignee=[t1],
        missing_group=[],
        missing_priority=[],
    )
    s = str(report)
    assert "3" in s


def test_triage_report_str_includes_section_headers():
    report = TriageReport(total_untriaged=0)
    s = str(report)
    assert "Missing Assignee" in s
    assert "Missing Group" in s
    assert "Missing Priority" in s


def test_triage_report_str_lists_tickets():
    t1 = make_ticket(id=99, subject="Broken login")
    report = TriageReport(total_untriaged=1, missing_assignee=[t1])
    s = str(report)
    assert "99" in s
    assert "Broken login" in s


# ---------------------------------------------------------------------------
# StaleTicketReport
# ---------------------------------------------------------------------------

def test_stale_ticket_report_str():
    report = StaleTicketReport(
        total_stale=5,
        threshold_hours=48,
        by_group={"Support": 3},
        by_priority={"high": 2},
        tickets=[make_ticket()],
    )
    s = str(report)
    assert "5" in s
    assert "48" in s
    assert "Support" in s


# ---------------------------------------------------------------------------
# BulkTagResult
# ---------------------------------------------------------------------------

def test_bulk_tag_result_dry_run_prefix():
    result = BulkTagResult(
        query="status:open",
        tags=["vip"],
        affected=[make_ticket()],
        count=1,
        dry_run=True,
    )
    assert "DRY RUN" in str(result)


def test_bulk_tag_result_applied_prefix():
    result = BulkTagResult(
        query="status:open",
        tags=["vip"],
        affected=[],
        count=0,
        dry_run=False,
    )
    assert "APPLIED" in str(result)


# ---------------------------------------------------------------------------
# BulkCloseResult
# ---------------------------------------------------------------------------

def test_bulk_close_result_str():
    result = BulkCloseResult(
        status_filter="solved",
        older_than_days=30,
        closed=[make_ticket()],
        count=1,
        dry_run=True,
    )
    s = str(result)
    assert "DRY RUN" in s
    assert "solved" in s
    assert "30" in s


# ---------------------------------------------------------------------------
# SLABreachReport
# ---------------------------------------------------------------------------

def test_sla_breach_report_str():
    report = SLABreachReport(
        breached=[make_ticket()],
        approaching=[make_ticket(id=200, subject="Other")],
        by_priority={"high": 1},
        by_group={"Tier 1": 1},
    )
    s = str(report)
    assert "Breached" in s
    assert "Approaching" in s
    assert "1" in s


# ---------------------------------------------------------------------------
# CSATSummary
# ---------------------------------------------------------------------------

def test_csat_summary_str():
    report = CSATSummary(
        period_days=30,
        total_responses=100,
        good_count=85,
        bad_count=15,
        satisfaction_rate=0.85,
        by_agent={"Alice Smith": {"good": 40, "bad": 5, "rate": 0.889}},
    )
    s = str(report)
    assert "30" in s
    assert "100" in s
    assert "Alice Smith" in s


# ---------------------------------------------------------------------------
# ResponseTimeAnalysis
# ---------------------------------------------------------------------------

def test_response_time_analysis_str():
    report = ResponseTimeAnalysis(
        period_days=7,
        avg_first_response_hours=2.5,
        avg_resolution_hours=12.0,
        by_priority={"high": {"avg_first_response_hours": 1.0, "avg_resolution_hours": 8.0}},
    )
    s = str(report)
    assert "7" in s
    assert "2.5" in s
    assert "high" in s


# ---------------------------------------------------------------------------
# AgentWorkload & WorkloadReport
# ---------------------------------------------------------------------------

def test_agent_workload_str():
    aw = AgentWorkload(
        agent=make_agent(),
        total_open=10,
        by_priority={"high": 3, "normal": 7},
    )
    s = str(aw)
    assert "Alice Smith" in s
    assert "10" in s


def test_workload_report_str_includes_agent_info():
    agent = make_agent()
    aw = AgentWorkload(agent=agent, total_open=5, by_priority={})
    report = WorkloadReport(agents=[aw], total_agents=1, overloaded=[])
    s = str(report)
    assert "Alice Smith" in s
    assert "1" in s


def test_workload_report_str_overloaded():
    agent = make_agent(name="Bob Jones", email="bob@co.com")
    aw = AgentWorkload(agent=agent, total_open=30, by_priority={"urgent": 10})
    report = WorkloadReport(agents=[aw], total_agents=1, overloaded=[aw])
    s = str(report)
    assert "Overloaded" in s
    assert "Bob Jones" in s


# ---------------------------------------------------------------------------
# GroupStatus & GroupDistribution
# ---------------------------------------------------------------------------

def test_group_status_str():
    gs = GroupStatus(
        name="Tier 1", group_id=10, new_count=2, open_count=5,
        pending_count=1, solved_count=8, total=16,
    )
    s = str(gs)
    assert "Tier 1" in s
    assert "16" in s


def test_group_distribution_str():
    gs = GroupStatus(
        name="Tier 1", group_id=10, new_count=2, open_count=5,
        pending_count=1, solved_count=8, total=16,
    )
    dist = GroupDistribution(groups=[gs], total_tickets=50)
    s = str(dist)
    assert "50" in s
    assert "Tier 1" in s


# ---------------------------------------------------------------------------
# MacroInfo & MacroAuditReport
# ---------------------------------------------------------------------------

def test_macro_info_str():
    m = MacroInfo(id=1, title="Close and tag", active=True, usage_7d=5)
    s = str(m)
    assert "Close and tag" in s
    assert "active" in s


def test_macro_audit_report_str_includes_totals():
    unused = [MacroInfo(id=1, title="Old macro", active=False, usage_7d=0)]
    report = MacroAuditReport(
        total=10, active_count=7, inactive_count=3,
        unused=unused, duplicates=["Close ticket"],
    )
    s = str(report)
    assert "10" in s
    assert "7" in s
    assert "3" in s


def test_macro_audit_report_str_includes_unused():
    unused = [MacroInfo(id=99, title="Old macro", active=False)]
    report = MacroAuditReport(total=5, active_count=4, inactive_count=1, unused=unused)
    s = str(report)
    assert "Old macro" in s
    assert "Unused" in s


# ---------------------------------------------------------------------------
# TriggerInfo & TriggerReviewReport
# ---------------------------------------------------------------------------

def test_trigger_info_str():
    t = TriggerInfo(id=1, title="Notify on new", active=True, conditions_count=3, category="trigger")
    s = str(t)
    assert "Notify on new" in s
    assert "trigger" in s
    assert "3" in s


def test_trigger_review_report_str():
    disabled = [TriggerInfo(id=5, title="Old trigger", active=False, conditions_count=1, category="trigger")]
    report = TriggerReviewReport(
        total_triggers=10,
        total_automations=5,
        active_triggers=8,
        inactive_triggers=2,
        active_automations=4,
        inactive_automations=1,
        disabled=disabled,
        broad_conditions=[],
    )
    s = str(report)
    assert "10" in s
    assert "5" in s
    assert "Disabled" in s
    assert "Old trigger" in s
