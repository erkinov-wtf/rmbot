import pytest

from core.utils.constants import RoleSlug, XPLedgerEntryType
from gamification.models import XPLedger


pytestmark = pytest.mark.django_db


LEDGER_URL = "/api/v1/xp/ledger/"


@pytest.fixture
def ledger_context(user_factory, assign_roles):
    tech_one = user_factory(
        username="xp_api_tech_one",
        first_name="Tech One",
        email="xp_api_tech_one@example.com",
    )
    tech_two = user_factory(
        username="xp_api_tech_two",
        first_name="Tech Two",
        email="xp_api_tech_two@example.com",
    )
    ops = user_factory(
        username="xp_api_ops",
        first_name="Ops",
        email="xp_api_ops@example.com",
    )
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    XPLedger.objects.create(
        user=tech_one,
        amount=3,
        entry_type=XPLedgerEntryType.TICKET_BASE_XP,
        reference="ticket_base_xp:101",
        payload={"ticket_id": 101},
    )
    XPLedger.objects.create(
        user=tech_one,
        amount=1,
        entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS,
        reference="ticket_qc_first_pass_bonus:101",
        payload={"ticket_id": 101},
    )
    XPLedger.objects.create(
        user=tech_one,
        amount=2,
        entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
        reference="attendance_checkin:tech_one:2026-02-11",
        payload={},
    )
    XPLedger.objects.create(
        user=tech_two,
        amount=4,
        entry_type=XPLedgerEntryType.TICKET_BASE_XP,
        reference="ticket_base_xp:202",
        payload={"ticket_id": 202},
    )

    return {
        "tech_one": tech_one,
        "tech_two": tech_two,
        "ops": ops,
    }


def test_regular_user_sees_only_own_entries(authed_client_factory, ledger_context):
    client = authed_client_factory(ledger_context["tech_one"])
    resp = client.get(LEDGER_URL)

    assert resp.status_code == 200
    entries = resp.data["data"]
    assert len(entries) == 3
    assert all(item["user"] == ledger_context["tech_one"].id for item in entries)


def test_regular_user_cannot_read_other_user_entries(authed_client_factory, ledger_context):
    client = authed_client_factory(ledger_context["tech_one"])
    resp = client.get(f"{LEDGER_URL}?user_id={ledger_context['tech_two'].id}")

    assert resp.status_code == 403
    assert resp.data["success"] is False


def test_ops_can_filter_by_user_and_ticket(authed_client_factory, ledger_context):
    client = authed_client_factory(ledger_context["ops"])

    by_user = client.get(f"{LEDGER_URL}?user_id={ledger_context['tech_two'].id}")
    assert by_user.status_code == 200
    assert len(by_user.data["data"]) == 1
    assert by_user.data["data"][0]["user"] == ledger_context["tech_two"].id

    by_ticket = client.get(f"{LEDGER_URL}?user_id={ledger_context['tech_one'].id}&ticket_id=101")
    assert by_ticket.status_code == 200
    assert len(by_ticket.data["data"]) == 2
    refs = {item["reference"] for item in by_ticket.data["data"]}
    assert "ticket_base_xp:101" in refs
    assert "ticket_qc_first_pass_bonus:101" in refs


def test_invalid_filters_return_400(authed_client_factory, ledger_context):
    client = authed_client_factory(ledger_context["ops"])

    invalid_limit = client.get(f"{LEDGER_URL}?limit=abc")
    assert invalid_limit.status_code == 400

    invalid_ticket = client.get(f"{LEDGER_URL}?ticket_id=-1")
    assert invalid_ticket.status_code == 400

    invalid_entry_type = client.get(f"{LEDGER_URL}?entry_type=unknown_entry")
    assert invalid_entry_type.status_code == 400
