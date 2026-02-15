import pytest
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import (
    PayrollAllowanceDecision,
    RoleSlug,
    SLAAutomationEventSeverity,
    SLAAutomationEventStatus,
    TicketStatus,
    TicketTransitionAction,
    XPLedgerEntryType,
)
from gamification.models import XPLedger
from payroll.models import PayrollAllowanceGateDecision, PayrollMonthly
from ticket.models import SLAAutomationEvent, TicketTransition

pytestmark = pytest.mark.django_db


AUDIT_FEED_URL = "/api/v1/misc/audit-feed/"


@pytest.fixture
def audit_feed_context(
    user_factory, assign_roles, inventory_item_factory, ticket_factory
):
    ops = user_factory(
        username="audit_ops",
        first_name="Ops",
        email="audit_ops@example.com",
    )
    regular = user_factory(
        username="audit_regular",
        first_name="Regular",
        email="audit_regular@example.com",
    )
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    inventory_item = inventory_item_factory(serial_number="RM-AUD-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=ops,
        technician=ops,
        status=TicketStatus.DONE,
        title="Audit ticket",
    )
    TicketTransition.objects.create(
        ticket=ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=ops,
    )
    XPLedger.objects.create(
        user=ops,
        amount=2,
        entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
        reference="audit_feed_test_xp",
        payload={},
    )
    AttendanceRecord.objects.create(
        user=ops,
        work_date=timezone.localdate(),
        check_in_at=timezone.now(),
    )
    payroll_month = PayrollMonthly.objects.create(
        month=timezone.localdate().replace(day=1),
        status="closed",
    )
    PayrollAllowanceGateDecision.objects.create(
        payroll_monthly=payroll_month,
        decision=PayrollAllowanceDecision.KEEP_GATED,
        decided_by=ops,
        affected_lines_count=1,
        total_allowance_delta=0,
        note="Keep gate",
        payload={},
    )
    SLAAutomationEvent.objects.create(
        rule_key="stockout_open_minutes",
        status=SLAAutomationEventStatus.TRIGGERED,
        severity=SLAAutomationEventSeverity.CRITICAL,
        metric_value=25,
        threshold_value=15,
        payload={"recommended_action": "notify_ops_and_dispatch_recovery"},
    )

    return {
        "ops": ops,
        "regular": regular,
    }


def test_requires_ops_or_super_admin(authed_client_factory, audit_feed_context):
    client = authed_client_factory(audit_feed_context["regular"])
    resp = client.get(AUDIT_FEED_URL)
    assert resp.status_code == 403


def test_returns_mixed_event_feed(authed_client_factory, audit_feed_context):
    client = authed_client_factory(audit_feed_context["ops"])
    resp = client.get(f"{AUDIT_FEED_URL}?per_page=20")

    assert resp.status_code == 200
    feed = resp.data["results"]
    assert len(feed) >= 3

    event_types = {event["event_type"] for event in feed}
    assert "ticket_transition" in event_types
    assert "xp_ledger" in event_types
    assert "attendance_check_in" in event_types
    assert "allowance_gate_decision" in event_types
    assert "sla_automation" in event_types


def test_pagination_works(authed_client_factory, audit_feed_context):
    client = authed_client_factory(audit_feed_context["ops"])

    limited = client.get(f"{AUDIT_FEED_URL}?per_page=1&page=1")
    assert limited.status_code == 200
    assert limited.data["per_page"] == 1
    assert limited.data["page"] == 1
    assert len(limited.data["results"]) == 1
