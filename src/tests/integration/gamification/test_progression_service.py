from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.utils.constants import EmployeeLevel, XPTransactionEntryType
from gamification.models import LevelUpCouponEvent, WeeklyLevelEvaluation, XPTransaction
from gamification.services import ProgressionService
from rules.services import RulesService

pytestmark = pytest.mark.django_db


def _configure_progression_rules(*, actor_user_id: int) -> None:
    config = RulesService.get_active_rules_config()
    config["progression"] = {
        "level_thresholds": {
            "1": 0,
            "2": 100,
            "3": 200,
            "4": 300,
            "5": 400,
        },
        "weekly_coupon_amount": 250_000,
    }
    RulesService.update_rules_config(
        config=config,
        actor_user_id=actor_user_id,
        reason="Progression test override",
    )


def _create_xp_entry(
    *, user_id: int, amount: int, reference: str, created_at: datetime
) -> None:
    entry = XPTransaction.objects.create(
        user_id=user_id,
        amount=amount,
        entry_type=XPTransactionEntryType.ATTENDANCE_PUNCTUALITY,
        reference=reference,
        payload={},
    )
    XPTransaction.all_objects.filter(pk=entry.pk).update(
        created_at=created_at,
        updated_at=created_at,
    )


def test_map_raw_xp_to_level_uses_threshold_boundaries():
    thresholds = {
        int(EmployeeLevel.L1): 0,
        int(EmployeeLevel.L2): 100,
        int(EmployeeLevel.L3): 200,
        int(EmployeeLevel.L4): 300,
        int(EmployeeLevel.L5): 400,
    }

    assert ProgressionService.map_raw_xp_to_level(
        raw_xp=-10, level_thresholds=thresholds
    ) == int(EmployeeLevel.L1)
    assert ProgressionService.map_raw_xp_to_level(
        raw_xp=0, level_thresholds=thresholds
    ) == int(EmployeeLevel.L1)
    assert ProgressionService.map_raw_xp_to_level(
        raw_xp=100, level_thresholds=thresholds
    ) == int(EmployeeLevel.L2)
    assert ProgressionService.map_raw_xp_to_level(
        raw_xp=299, level_thresholds=thresholds
    ) == int(EmployeeLevel.L3)
    assert ProgressionService.map_raw_xp_to_level(
        raw_xp=400, level_thresholds=thresholds
    ) == int(EmployeeLevel.L5)


def test_weekly_level_evaluation_levels_up_and_creates_coupon(user_factory):
    actor = user_factory(
        username="progression_actor",
        first_name="Progression",
    )
    technician = user_factory(
        username="progression_tech",
        first_name="Technician",
        level=EmployeeLevel.L1,
    )
    _configure_progression_rules(actor_user_id=actor.id)

    week_start = date(2026, 1, 5)
    _create_xp_entry(
        user_id=technician.id,
        amount=150,
        reference="progression_eval_xp_1",
        created_at=datetime(2026, 1, 10, 12, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    summary = ProgressionService.run_weekly_level_evaluation(
        week_start=week_start,
        actor_user_id=actor.id,
    )
    technician.refresh_from_db()

    assert summary["evaluations_created"] == 1
    assert summary["evaluations_skipped"] == 0
    assert summary["level_ups"] == 1
    assert summary["coupon_events_created"] == 1
    assert technician.level == EmployeeLevel.L2

    evaluation = WeeklyLevelEvaluation.objects.get(
        user=technician, week_start=week_start
    )
    assert evaluation.raw_xp == 150
    assert evaluation.previous_level == EmployeeLevel.L1
    assert evaluation.new_level == EmployeeLevel.L2
    assert evaluation.is_level_up is True
    assert evaluation.evaluated_by_id == actor.id

    coupon = LevelUpCouponEvent.objects.get(evaluation=evaluation)
    assert coupon.amount == 250_000
    assert (
        coupon.reference == f"level_up_coupon:{week_start.isoformat()}:{technician.id}"
    )

    rerun_summary = ProgressionService.run_weekly_level_evaluation(
        week_start=week_start,
        actor_user_id=actor.id,
    )
    assert rerun_summary["evaluations_created"] == 0
    assert rerun_summary["evaluations_skipped"] == 1
    assert rerun_summary["level_ups"] == 0
    assert rerun_summary["coupon_events_created"] == 0
    assert WeeklyLevelEvaluation.objects.count() == 1
    assert LevelUpCouponEvent.objects.count() == 1


def test_weekly_level_evaluation_does_not_downgrade_existing_user_level(user_factory):
    actor = user_factory(
        username="progression_actor_two",
        first_name="Progression",
    )
    technician = user_factory(
        username="progression_l3_tech",
        first_name="L3 Tech",
        level=EmployeeLevel.L3,
    )
    _configure_progression_rules(actor_user_id=actor.id)

    week_start = date(2026, 1, 12)
    _create_xp_entry(
        user_id=technician.id,
        amount=120,
        reference="progression_eval_xp_2",
        created_at=datetime(2026, 1, 14, 9, 0, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    summary = ProgressionService.run_weekly_level_evaluation(
        week_start=week_start,
        actor_user_id=actor.id,
    )
    technician.refresh_from_db()

    assert summary["evaluations_created"] == 1
    assert summary["level_ups"] == 0
    assert summary["coupon_events_created"] == 0
    assert technician.level == EmployeeLevel.L3

    evaluation = WeeklyLevelEvaluation.objects.get(
        user=technician, week_start=week_start
    )
    assert evaluation.previous_level == EmployeeLevel.L3
    assert evaluation.new_level == EmployeeLevel.L3
    assert evaluation.is_level_up is False
    assert LevelUpCouponEvent.objects.count() == 0
