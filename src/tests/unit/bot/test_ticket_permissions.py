import pytest

from bot.permissions import resolve_ticket_bot_permissions
from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db


def test_permission_resolver_returns_all_false_for_missing_user():
    resolved = resolve_ticket_bot_permissions(user=None)
    assert resolved.can_create is False
    assert resolved.can_review is False
    assert resolved.can_assign is False
    assert resolved.can_manual_metrics is False
    assert resolved.can_qc is False
    assert resolved.can_open_review_panel is False
    assert resolved.can_approve_and_assign is False


def test_master_role_has_ticket_create_and_review_permissions(
    user_factory,
    assign_roles,
):
    master = user_factory(username="perm_master", first_name="Master")
    assign_roles(master, RoleSlug.MASTER)

    resolved = resolve_ticket_bot_permissions(user=master)
    assert resolved.can_create is True
    assert resolved.can_review is True
    assert resolved.can_assign is True
    assert resolved.can_manual_metrics is True
    assert resolved.can_qc is False
    assert resolved.can_open_review_panel is True
    assert resolved.can_approve_and_assign is True


def test_ops_manager_role_uses_api_ticket_create_permission_map(
    user_factory,
    assign_roles,
):
    ops = user_factory(username="perm_ops", first_name="Ops")
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    resolved = resolve_ticket_bot_permissions(user=ops)
    assert resolved.can_create is True
    assert resolved.can_review is True
    assert resolved.can_assign is True
    assert resolved.can_manual_metrics is True
    assert resolved.can_qc is False


def test_technician_role_has_no_review_or_create_permissions(
    user_factory,
    assign_roles,
):
    technician = user_factory(username="perm_tech", first_name="Tech")
    assign_roles(technician, RoleSlug.TECHNICIAN)

    resolved = resolve_ticket_bot_permissions(user=technician)
    assert resolved.can_create is False
    assert resolved.can_review is False
    assert resolved.can_assign is False
    assert resolved.can_manual_metrics is False
    assert resolved.can_qc is False
    assert resolved.can_open_review_panel is False
    assert resolved.can_approve_and_assign is False


def test_qc_inspector_role_has_qc_permission(
    user_factory,
    assign_roles,
):
    qc = user_factory(username="perm_qc", first_name="QC")
    assign_roles(qc, RoleSlug.QC_INSPECTOR)

    resolved = resolve_ticket_bot_permissions(user=qc)
    assert resolved.can_create is False
    assert resolved.can_review is False
    assert resolved.can_assign is False
    assert resolved.can_manual_metrics is False
    assert resolved.can_qc is True
