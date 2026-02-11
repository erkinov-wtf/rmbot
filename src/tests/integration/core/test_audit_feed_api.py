import pytest
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import (
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
    XPLedgerEntryType,
)
from gamification.models import XPLedger
from ticket.models import TicketTransition

pytestmark = pytest.mark.django_db


AUDIT_FEED_URL = "/api/v1/misc/audit-feed/"


@pytest.fixture
def audit_feed_context(user_factory, assign_roles, bike_factory, ticket_factory):
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

    bike = bike_factory(bike_code="RM-AUD-0001")
    ticket = ticket_factory(
        bike=bike,
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
    resp = client.get(f"{AUDIT_FEED_URL}?limit=20")

    assert resp.status_code == 200
    feed = resp.data["data"]
    assert len(feed) >= 3

    event_types = {event["event_type"] for event in feed}
    assert "ticket_transition" in event_types
    assert "xp_ledger" in event_types
    assert "attendance_check_in" in event_types


def test_limit_and_validation(authed_client_factory, audit_feed_context):
    client = authed_client_factory(audit_feed_context["ops"])

    invalid = client.get(f"{AUDIT_FEED_URL}?limit=abc")
    assert invalid.status_code == 400
    assert invalid.data["success"] is False

    limited = client.get(f"{AUDIT_FEED_URL}?limit=1")
    assert limited.status_code == 200
    assert len(limited.data["data"]) == 1
