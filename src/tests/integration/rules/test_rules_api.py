from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.utils.constants import RoleSlug, TicketStatus, XPLedgerEntryType
from gamification.models import XPLedger
from payroll.models import PayrollMonthly
from rules.models import RulesConfigVersion
from rules.services import RulesService
from ticket.services import TicketService

pytestmark = pytest.mark.django_db


RULES_CONFIG_URL = "/api/v1/rules/config/"
RULES_HISTORY_URL = "/api/v1/rules/config/history/"
RULES_ROLLBACK_URL = "/api/v1/rules/config/rollback/"


@pytest.fixture
def rules_context(user_factory, assign_roles):
    super_admin = user_factory(
        username="rules_super_admin",
        first_name="Rules",
        email="rules_super_admin@example.com",
    )
    assign_roles(super_admin, RoleSlug.SUPER_ADMIN)

    ops = user_factory(
        username="rules_ops",
        first_name="Ops",
        email="rules_ops@example.com",
    )
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    regular = user_factory(
        username="rules_regular",
        first_name="Regular",
        email="rules_regular@example.com",
    )
    return {
        "super_admin": super_admin,
        "ops": ops,
        "regular": regular,
    }


def test_get_config_bootstraps_defaults(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["ops"])

    resp = client.get(RULES_CONFIG_URL)

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["active_version"] == 1
    assert payload["config"]["ticket_xp"]["base_divisor"] == 20
    assert payload["config"]["ticket_xp"]["first_pass_bonus"] == 1
    assert payload["config"]["payroll"]["bonus_rate"] == 3000
    assert payload["config"]["progression"]["weekly_coupon_amount"] == 100000


def test_permissions_for_config_mutation(authed_client_factory, rules_context):
    ops_client = authed_client_factory(rules_context["ops"])
    super_admin_client = authed_client_factory(rules_context["super_admin"])

    base_config = super_admin_client.get(RULES_CONFIG_URL).data["data"]["config"]
    mutated = dict(base_config)
    mutated["ticket_xp"] = dict(base_config["ticket_xp"])
    mutated["ticket_xp"]["base_divisor"] = 15

    forbidden = ops_client.put(RULES_CONFIG_URL, {"config": mutated}, format="json")
    assert forbidden.status_code == 403

    allowed = super_admin_client.put(
        RULES_CONFIG_URL, {"config": mutated, "reason": "Tune divisor"}, format="json"
    )
    assert allowed.status_code == 200
    assert allowed.data["data"]["active_version"] == 2


def test_update_changes_cache_key_and_history(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["super_admin"])
    before = client.get(RULES_CONFIG_URL).data["data"]

    config = before["config"]
    updated = {
        **config,
        "ticket_xp": {
            **config["ticket_xp"],
            "base_divisor": 10,
            "first_pass_bonus": 2,
        },
    }
    after_resp = client.put(
        RULES_CONFIG_URL,
        {"config": updated, "reason": "More aggressive XP"},
        format="json",
    )
    assert after_resp.status_code == 200

    after = after_resp.data["data"]
    assert after["active_version"] == before["active_version"] + 1
    assert after["cache_key"] != before["cache_key"]
    assert after["config"]["ticket_xp"]["base_divisor"] == 10
    assert after["config"]["ticket_xp"]["first_pass_bonus"] == 2

    history_resp = client.get(f"{RULES_HISTORY_URL}?limit=2")
    assert history_resp.status_code == 200
    items = history_resp.data["data"]
    assert len(items) >= 2
    assert items[0]["action"] == "update"
    assert items[0]["source_version_number"] == 1
    assert "ticket_xp.base_divisor" in items[0]["diff"]["changes"]


def test_rollback_restores_previous_version(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["super_admin"])
    base = client.get(RULES_CONFIG_URL).data["data"]["config"]

    cfg_v2 = {**base, "payroll": {**base["payroll"], "bonus_rate": 4500}}
    resp_v2 = client.put(
        RULES_CONFIG_URL,
        {"config": cfg_v2, "reason": "Raise bonus rate"},
        format="json",
    )
    assert resp_v2.status_code == 200
    assert resp_v2.data["data"]["active_version"] == 2

    cfg_v3 = {**cfg_v2, "payroll": {**cfg_v2["payroll"], "bonus_rate": 5000}}
    resp_v3 = client.put(
        RULES_CONFIG_URL, {"config": cfg_v3, "reason": "Raise again"}, format="json"
    )
    assert resp_v3.status_code == 200
    assert resp_v3.data["data"]["active_version"] == 3

    rollback = client.post(
        RULES_ROLLBACK_URL,
        {"target_version": 2, "reason": "Revert accidental bump"},
        format="json",
    )
    assert rollback.status_code == 200
    data = rollback.data["data"]
    assert data["active_version"] == 4
    assert data["config"]["payroll"]["bonus_rate"] == 4500

    latest = RulesConfigVersion.objects.order_by("-version").first()
    assert latest is not None
    assert latest.action == "rollback"
    assert latest.source_version is not None
    assert latest.source_version.version == 2


def test_invalid_config_rejected(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["super_admin"])

    bad_payload = {
        "config": {
            "ticket_xp": {"base_divisor": 0, "first_pass_bonus": 1},
            "attendance": {
                "on_time_xp": 2,
                "grace_xp": 0,
                "late_xp": -1,
                "on_time_cutoff": "10:00",
                "grace_cutoff": "10:20",
                "timezone": "Asia/Tashkent",
            },
            "payroll": {
                "fix_salary": 3000000,
                "bonus_rate": 3000,
                "level_caps": {"1": 100},
                "level_allowances": {"1": 0},
            },
        }
    }
    resp = client.put(RULES_CONFIG_URL, bad_payload, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False


def test_ticket_xp_formula_uses_active_rules(
    rules_context, bike_factory, ticket_factory, user_factory
):
    actor = rules_context["super_admin"]
    current = RulesService.get_active_rules_config()
    current["ticket_xp"]["base_divisor"] = 10
    current["ticket_xp"]["first_pass_bonus"] = 2

    RulesService.update_rules_config(
        config=current, actor_user_id=actor.id, reason="Formula override"
    )

    technician = user_factory(
        username="rules_xp_tech",
        first_name="Rules Tech",
        email="rules_xp_tech@example.com",
    )
    bike = bike_factory(bike_code="RM-RULES-0001")
    ticket = ticket_factory(
        bike=bike,
        master=actor,
        technician=technician,
        status=TicketStatus.WAITING_QC,
        srt_total_minutes=45,
        title="Rules ticket XP",
    )

    TicketService.qc_pass_ticket(ticket=ticket, actor_user_id=actor.id)

    base_entry = XPLedger.objects.get(reference=f"ticket_base_xp:{ticket.id}")
    bonus_entry = XPLedger.objects.get(
        reference=f"ticket_qc_first_pass_bonus:{ticket.id}"
    )
    assert base_entry.amount == 5  # ceil(45/10)
    assert bonus_entry.amount == 2


def test_payroll_formula_uses_active_rules(
    authed_client_factory, rules_context, user_factory
):
    actor = rules_context["super_admin"]
    current = RulesService.get_active_rules_config()
    current["payroll"]["bonus_rate"] = 100
    current["payroll"]["fix_salary"] = 1_000
    current["payroll"]["level_caps"]["1"] = 50
    current["payroll"]["level_allowances"]["1"] = 10

    RulesService.update_rules_config(
        config=current, actor_user_id=actor.id, reason="Payroll override"
    )

    tech = user_factory(
        username="rules_payroll_l1",
        first_name="Rules L1",
        email="rules_payroll_l1@example.com",
        level=1,
    )
    XPLedger.objects.create(
        user=tech,
        amount=120,
        entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
        reference="rules_payroll_xp_1",
        payload={},
    )
    XPLedger.all_objects.filter(reference="rules_payroll_xp_1").update(
        created_at=datetime(2026, 1, 11, 11, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
        updated_at=datetime(2026, 1, 11, 11, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    client = authed_client_factory(actor)
    resp = client.post("/api/v1/payroll/2026-01/close/", {}, format="json")

    assert resp.status_code == 200
    line = resp.data["data"]["lines"][0]
    assert line["raw_xp"] == 120
    assert line["paid_xp"] == 50
    assert line["bonus_amount"] == 5000
    assert line["fix_salary"] == 1000
    assert line["allowance_amount"] == 10
    assert line["total_amount"] == 6010

    payroll_month = PayrollMonthly.objects.get(month="2026-01-01")
    assert payroll_month.rules_snapshot["version"] >= 2
