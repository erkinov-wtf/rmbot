from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.utils.constants import (
    EmployeeLevel,
    PayrollMonthStatus,
    RoleSlug,
    XPLedgerEntryType,
)
from gamification.models import XPLedger
from payroll.models import PayrollMonthly

pytestmark = pytest.mark.django_db


BUSINESS_TZ = ZoneInfo("Asia/Tashkent")


@pytest.fixture
def payroll_context(user_factory, assign_roles):
    ops = user_factory(
        username="payroll_ops",
        first_name="Payroll Ops",
        email="payroll_ops@example.com",
    )
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    regular = user_factory(
        username="payroll_regular",
        first_name="Regular",
        email="payroll_regular@example.com",
    )
    tech_l1 = user_factory(
        username="payroll_tech_l1",
        first_name="Tech L1",
        email="payroll_tech_l1@example.com",
        level=EmployeeLevel.L1,
    )
    tech_l3 = user_factory(
        username="payroll_tech_l3",
        first_name="Tech L3",
        email="payroll_tech_l3@example.com",
        level=EmployeeLevel.L3,
    )

    def create_xp(*, user, amount: int, reference: str, created_at: datetime):
        entry = XPLedger.objects.create(
            user=user,
            amount=amount,
            entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
            reference=reference,
            payload={},
        )
        XPLedger.all_objects.filter(pk=entry.pk).update(
            created_at=created_at, updated_at=created_at
        )

    create_xp(
        user=tech_l1,
        amount=120,
        reference="payroll:l1:jan:a",
        created_at=datetime(2026, 1, 10, 11, 0, tzinfo=BUSINESS_TZ),
    )
    create_xp(
        user=tech_l1,
        amount=80,
        reference="payroll:l1:jan:b",
        created_at=datetime(2026, 1, 20, 12, 0, tzinfo=BUSINESS_TZ),
    )
    create_xp(
        user=tech_l3,
        amount=250,
        reference="payroll:l3:jan:a",
        created_at=datetime(2026, 1, 7, 15, 0, tzinfo=BUSINESS_TZ),
    )
    create_xp(
        user=tech_l3,
        amount=200,
        reference="payroll:l3:jan:b",
        created_at=datetime(2026, 1, 24, 18, 0, tzinfo=BUSINESS_TZ),
    )
    create_xp(
        user=tech_l1,
        amount=999,
        reference="payroll:l1:feb:out_of_range",
        created_at=datetime(2026, 2, 1, 10, 0, tzinfo=BUSINESS_TZ),
    )

    return {
        "ops": ops,
        "regular": regular,
        "tech_l1": tech_l1,
        "tech_l3": tech_l3,
    }


def test_payroll_close_applies_level_caps_and_totals(
    authed_client_factory, payroll_context
):
    client = authed_client_factory(payroll_context["ops"])

    resp = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["status"] == PayrollMonthStatus.CLOSED
    assert payload["month_key"] == "2026-01"
    assert payload["total_raw_xp"] == 650
    assert payload["total_paid_xp"] == 567
    assert payload["total_bonus_amount"] == 1_701_000
    assert payload["total_allowance_amount"] == 1_300_000
    assert payload["total_fix_salary"] == 6_000_000
    assert payload["total_payout_amount"] == 9_001_000

    lines_by_user = {line["user"]: line for line in payload["lines"]}

    l1 = lines_by_user[payroll_context["tech_l1"].id]
    assert l1["level"] == EmployeeLevel.L1
    assert l1["raw_xp"] == 200
    assert l1["paid_xp_cap"] == 167
    assert l1["paid_xp"] == 167
    assert l1["allowance_amount"] == 0
    assert l1["bonus_amount"] == 501_000
    assert l1["total_amount"] == 3_501_000

    l3 = lines_by_user[payroll_context["tech_l3"].id]
    assert l3["level"] == EmployeeLevel.L3
    assert l3["raw_xp"] == 450
    assert l3["paid_xp_cap"] == 400
    assert l3["paid_xp"] == 400
    assert l3["allowance_amount"] == 1_300_000
    assert l3["bonus_amount"] == 1_200_000
    assert l3["total_amount"] == 5_500_000


def test_payroll_close_requires_privileged_role(authed_client_factory, payroll_context):
    client = authed_client_factory(payroll_context["regular"])
    resp = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")
    assert resp.status_code == 403


def test_payroll_close_rejects_invalid_or_repeated_month(
    authed_client_factory, payroll_context
):
    client = authed_client_factory(payroll_context["ops"])

    invalid = client.post("/api/v1/payroll/2026-13/close/", {}, format="json")
    assert invalid.status_code == 400

    first = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")
    assert first.status_code == 200

    duplicate = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")
    assert duplicate.status_code == 400
    assert "already closed" in duplicate.data["error"]["detail"].lower()


def test_payroll_approve_requires_closed_month(authed_client_factory, payroll_context):
    client = authed_client_factory(payroll_context["ops"])

    not_closed = client.post("/api/v1/payroll/2026-01/approve/", {}, format="json")
    assert not_closed.status_code == 400
    assert "not closed yet" in not_closed.data["error"]["detail"].lower()


def test_payroll_approve_flow(authed_client_factory, payroll_context):
    client = authed_client_factory(payroll_context["ops"])

    close_resp = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")
    assert close_resp.status_code == 200

    approve_resp = client.post("/api/v1/payroll/2026-01/approve/", {}, format="json")
    assert approve_resp.status_code == 200
    assert approve_resp.data["data"]["status"] == PayrollMonthStatus.APPROVED
    assert approve_resp.data["data"]["approved_by"] == payroll_context["ops"].id
    assert approve_resp.data["data"]["approved_at"] is not None

    payroll_month = PayrollMonthly.objects.get(month="2026-01-01")
    assert payroll_month.status == PayrollMonthStatus.APPROVED

    duplicate = client.post("/api/v1/payroll/2026-01/approve/", {}, format="json")
    assert duplicate.status_code == 400
    assert "already approved" in duplicate.data["error"]["detail"].lower()
