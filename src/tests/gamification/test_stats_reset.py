from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from account.models import Role, User
from attendance.models import AttendanceRecord
from core.utils.constants import EmployeeLevel, RoleSlug, TicketStatus
from gamification.models import UserLevelHistoryEvent, UserLevelHistorySource, XPTransaction
from gamification.services import GamificationService, ProgressionService
from inventory.models import Inventory, InventoryItem, InventoryItemCategory
from ticket.models import Ticket
from ticket.services_analytics import TicketAnalyticsService


def _role(*, slug: str) -> Role:
    role, _ = Role.objects.get_or_create(
        slug=slug,
        defaults={"name": slug.replace("_", " ").title()},
    )
    return role


def _user(*, username: str, first_name: str, role_slug: str | None = None) -> User:
    user = User.objects.create_user(
        username=username,
        password="pass1234",
        first_name=first_name,
        is_active=True,
    )
    if role_slug:
        user.roles.add(_role(slug=role_slug))
    return user


def _xp_entry(*, user: User, amount: int, reference_suffix: str) -> XPTransaction:
    return XPTransaction.objects.create(
        user=user,
        amount=amount,
        entry_type="manual_adjustment",
        reference=f"test-reset:{user.id}:{reference_suffix}:{uuid.uuid4().hex[:6]}",
        description="test",
        payload={},
    )


def _done_ticket(*, technician: User, master: User, total_duration: int) -> Ticket:
    suffix = uuid.uuid4().hex[:8]
    inventory = Inventory.objects.create(name=f"Inventory-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"Category-{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"Item-{suffix}",
        serial_number=f"RM-{suffix.upper()}",
    )
    return Ticket.objects.create(
        inventory_item=item,
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        title=f"Done-{suffix}",
        total_duration=total_duration,
        xp_amount=max(total_duration // 10, 1),
        finished_at=timezone.now(),
    )


@pytest.mark.django_db
def test_reset_user_stats_sets_baseline_and_clears_warning():
    actor = _user(username="ops_reset_actor", first_name="Ops")
    technician = _user(
        username="tech_reset_target",
        first_name="Tech",
        role_slug=RoleSlug.TECHNICIAN,
    )
    UserLevelHistoryEvent.objects.create(
        user=technician,
        actor=actor,
        weekly_evaluation=None,
        source=UserLevelHistorySource.MANUAL_OVERRIDE,
        status="warning_enabled",
        previous_level=EmployeeLevel.L2,
        new_level=EmployeeLevel.L2,
        warning_active_before=False,
        warning_active_after=True,
        reference=f"warning-history:{technician.id}:{uuid.uuid4().hex[:6]}",
        note="warning before reset",
        payload={},
    )

    result = GamificationService.reset_user_stats(
        actor_user_id=actor.id,
        target_user_id=technician.id,
        comment="Reset baseline for fresh start",
    )

    technician.refresh_from_db()
    latest_history = (
        UserLevelHistoryEvent.objects.filter(user_id=technician.id)
        .order_by("-created_at", "-id")
        .first()
    )

    assert technician.stats_reset_at is not None
    assert technician.stats_reset_by_id == actor.id
    assert technician.stats_reset_note == "Reset baseline for fresh start"
    assert result["warning_active_before"] is True
    assert result["warning_active_after"] is False
    assert latest_history is not None
    assert latest_history.status == "stats_reset"
    assert latest_history.warning_active_after is False


@pytest.mark.django_db
def test_level_control_overview_ignores_xp_before_reset():
    actor = _user(username="ops_overview_actor", first_name="Ops")
    technician = _user(
        username="tech_overview_target",
        first_name="Tech",
        role_slug=RoleSlug.TECHNICIAN,
    )
    _xp_entry(user=technician, amount=120, reference_suffix="before")

    GamificationService.reset_user_stats(
        actor_user_id=actor.id,
        target_user_id=technician.id,
        comment="Reset before new cycle",
    )
    _xp_entry(user=technician, amount=25, reference_suffix="after")

    today = timezone.localdate()
    overview = ProgressionService.get_level_control_overview(
        date_from=today - timedelta(days=1),
        date_to=today,
    )
    row = next(item for item in overview["rows"] if item["user_id"] == technician.id)

    assert row["cumulative_xp"] == 25
    assert row["range_xp"] == 25
    assert row["warning_active"] is False


@pytest.mark.django_db
def test_public_technician_detail_ignores_pre_reset_xp_and_minutes():
    actor = _user(username="ops_public_actor", first_name="Ops")
    technician = _user(
        username="tech_public_target",
        first_name="Tech",
        role_slug=RoleSlug.TECHNICIAN,
    )
    master = _user(username="master_public", first_name="Master")

    _xp_entry(user=technician, amount=80, reference_suffix="public-before")
    _done_ticket(technician=technician, master=master, total_duration=120)
    AttendanceRecord.objects.create(
        user=technician,
        work_date=timezone.localdate() - timedelta(days=1),
        check_in_at=timezone.now() - timedelta(days=1, hours=3),
        check_out_at=timezone.now() - timedelta(days=1, hours=1),
    )

    GamificationService.reset_user_stats(
        actor_user_id=actor.id,
        target_user_id=technician.id,
        comment="Reset public stats baseline",
    )

    _xp_entry(user=technician, amount=15, reference_suffix="public-after")
    _done_ticket(technician=technician, master=master, total_duration=30)
    check_in_at = timezone.now()
    AttendanceRecord.objects.create(
        user=technician,
        work_date=timezone.localdate(),
        check_in_at=check_in_at,
        check_out_at=check_in_at + timedelta(hours=2),
    )

    detail = TicketAnalyticsService.public_technician_detail(user_id=technician.id)

    assert detail["metrics"]["xp"]["xp_total"] == 15
    assert detail["metrics"]["tickets"]["tickets_done_total"] == 1
    assert detail["metrics"]["tickets"]["average_resolution_minutes"] == 30.0
    assert detail["metrics"]["attendance"]["attendance_days_total"] == 1
    assert detail["metrics"]["attendance"]["average_work_minutes_per_day"] == 120.0
    assert len(detail["recent"]["xp_transactions"]) == 1
    assert len(detail["recent"]["done_tickets"]) == 1
