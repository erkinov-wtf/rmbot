import pytest
from django.core.cache import cache

from core.utils.constants import RoleSlug, TicketStatus
from gamification.models import XPTransaction
from rules.models import RulesConfigVersion
from rules.services import RulesService
from ticket.services_workflow import TicketWorkflowService

pytestmark = pytest.mark.django_db


RULES_CONFIG_URL = "/api/v1/rules/config/"
RULES_HISTORY_URL = "/api/v1/rules/config/history/"
RULES_ROLLBACK_URL = "/api/v1/rules/config/rollback/"


@pytest.fixture
def rules_context(user_factory, assign_roles):
    super_admin = user_factory(
        username="rules_super_admin",
        first_name="Rules",
    )
    assign_roles(super_admin, RoleSlug.SUPER_ADMIN)

    ops = user_factory(
        username="rules_ops",
        first_name="Ops",
    )
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    regular = user_factory(
        username="rules_regular",
        first_name="Regular",
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
    assert payload["config"]["ticket_xp"]["qc_status_update_xp"] == 1
    assert payload["config"]["work_session"]["daily_pause_limit_minutes"] == 30
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


def test_update_persists_work_session_pause_limit(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["super_admin"])
    base = client.get(RULES_CONFIG_URL).data["data"]["config"]
    updated = {
        **base,
        "work_session": {
            **base["work_session"],
            "daily_pause_limit_minutes": 45,
        },
    }

    resp = client.put(
        RULES_CONFIG_URL,
        {"config": updated, "reason": "Adjust pause limit"},
        format="json",
    )
    assert resp.status_code == 200
    assert (
        resp.data["data"]["config"]["work_session"]["daily_pause_limit_minutes"] == 45
    )


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

    history_resp = client.get(f"{RULES_HISTORY_URL}?per_page=2")
    assert history_resp.status_code == 200
    items = history_resp.data["results"]
    assert len(items) >= 2
    assert items[0]["action"] == "update"
    assert items[0]["source_version_number"] == 1
    assert "ticket_xp.base_divisor" in items[0]["diff"]["changes"]


def test_update_rotates_cached_rules_config(rules_context):
    actor = rules_context["super_admin"]
    state_before = RulesService.get_active_rules_state()
    config_before = RulesService.get_active_rules_config()
    old_cache_key = RulesService._cache_storage_key(state_before.cache_key)
    assert (
        cache.get(old_cache_key)["ticket_xp"]["base_divisor"]
        == config_before["ticket_xp"]["base_divisor"]
    )

    updated = RulesService.get_active_rules_config()
    updated["ticket_xp"]["base_divisor"] = 13
    RulesService.update_rules_config(
        config=updated,
        actor_user_id=actor.id,
        reason="Cache rotation check",
    )
    state_after = RulesService.get_active_rules_state()
    new_cache_key = RulesService._cache_storage_key(state_after.cache_key)

    assert state_after.cache_key != state_before.cache_key
    assert cache.get(old_cache_key) is None
    assert cache.get(new_cache_key)["ticket_xp"]["base_divisor"] == 13


def test_rollback_restores_previous_version(authed_client_factory, rules_context):
    client = authed_client_factory(rules_context["super_admin"])
    base = client.get(RULES_CONFIG_URL).data["data"]["config"]

    cfg_v2 = {
        **base,
        "progression": {**base["progression"], "weekly_coupon_amount": 200000},
    }
    resp_v2 = client.put(
        RULES_CONFIG_URL,
        {"config": cfg_v2, "reason": "Raise coupon amount"},
        format="json",
    )
    assert resp_v2.status_code == 200
    assert resp_v2.data["data"]["active_version"] == 2

    cfg_v3 = {
        **cfg_v2,
        "progression": {**cfg_v2["progression"], "weekly_coupon_amount": 300000},
    }
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
    assert data["config"]["progression"]["weekly_coupon_amount"] == 200000

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
            "work_session": {
                "daily_pause_limit_minutes": 30,
                "timezone": "Asia/Tashkent",
            },
            "progression": {
                "level_thresholds": {
                    "1": 0,
                    "2": 200,
                    "3": 450,
                    "4": 750,
                    "5": 1100,
                },
                "weekly_coupon_amount": 100000,
            },
        }
    }
    resp = client.put(RULES_CONFIG_URL, bad_payload, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False


def test_ticket_xp_formula_uses_active_rules(
    rules_context, inventory_item_factory, ticket_factory, user_factory
):
    actor = rules_context["super_admin"]
    current = RulesService.get_active_rules_config()
    current["ticket_xp"]["base_divisor"] = 10
    current["ticket_xp"]["first_pass_bonus"] = 2
    current["ticket_xp"]["qc_status_update_xp"] = 3

    RulesService.update_rules_config(
        config=current, actor_user_id=actor.id, reason="Formula override"
    )

    technician = user_factory(
        username="rules_xp_tech",
        first_name="Rules Tech",
    )
    inventory_item = inventory_item_factory(serial_number="RM-RULES-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=actor,
        technician=technician,
        status=TicketStatus.WAITING_QC,
        total_duration=45,
        title="Rules ticket XP",
    )

    TicketWorkflowService.qc_pass_ticket(ticket=ticket, actor_user_id=actor.id)

    base_entry = XPTransaction.objects.get(reference=f"ticket_base_xp:{ticket.id}")
    bonus_entry = XPTransaction.objects.get(
        reference=f"ticket_qc_first_pass_bonus:{ticket.id}"
    )
    assert base_entry.amount == 5  # ceil(45/10)
    assert bonus_entry.amount == 2
