from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from rules.services import RulesService
from ticket.models import SLAAutomationEvent, StockoutIncident
from ticket.services_sla import SLAAutomationService

pytestmark = pytest.mark.django_db

BUSINESS_TZ = ZoneInfo("Asia/Tashkent")


def _configure_automation(*, actor_user_id: int, cooldown_minutes: int) -> None:
    config = RulesService.get_active_rules_config()
    config["sla"]["automation"] = {
        "enabled": True,
        "cooldown_minutes": cooldown_minutes,
        "max_open_stockout_minutes": 5,
        "max_backlog_black_plus_count": 999,
        "min_first_pass_rate_percent": 0,
        "min_qc_done_tickets": 999,
    }
    RulesService.update_rules_config(
        config=config,
        actor_user_id=actor_user_id,
        reason="SLA automation test config",
    )


def test_sla_automation_creates_trigger_and_resolve_events(user_factory):
    actor = user_factory(
        username="sla_rules_actor",
        first_name="SLA",
        email="sla_rules_actor@example.com",
    )
    _configure_automation(actor_user_id=actor.id, cooldown_minutes=30)

    started_at = datetime(2026, 2, 13, 11, 0, tzinfo=BUSINESS_TZ)
    incident = StockoutIncident.objects.create(
        started_at=started_at,
        is_active=True,
        ready_count_at_start=0,
    )

    first = SLAAutomationService.evaluate_and_act(
        now_utc=started_at + timedelta(minutes=6)
    )
    assert first["enabled"] is True
    assert any(
        row["rule_key"] == SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        and row["event_created"] is True
        and row["event_status"] == "triggered"
        for row in first["results"]
    )

    incident.is_active = False
    incident.ended_at = started_at + timedelta(minutes=10)
    incident.duration_minutes = 10
    incident.ready_count_at_end = 2
    incident.save(
        update_fields=[
            "is_active",
            "ended_at",
            "duration_minutes",
            "ready_count_at_end",
            "updated_at",
        ]
    )

    second = SLAAutomationService.evaluate_and_act(
        now_utc=started_at + timedelta(minutes=12)
    )
    assert any(
        row["rule_key"] == SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        and row["event_created"] is True
        and row["event_status"] == "resolved"
        for row in second["results"]
    )


def test_sla_automation_emits_cooldown_reminder(user_factory):
    actor = user_factory(
        username="sla_rules_actor_2",
        first_name="SLA2",
        email="sla_rules_actor_2@example.com",
    )
    _configure_automation(actor_user_id=actor.id, cooldown_minutes=10)

    started_at = datetime(2026, 2, 13, 12, 0, tzinfo=BUSINESS_TZ)
    StockoutIncident.objects.create(
        started_at=started_at,
        is_active=True,
        ready_count_at_start=0,
    )

    first_eval_time = started_at + timedelta(minutes=6)
    first = SLAAutomationService.evaluate_and_act(now_utc=first_eval_time)
    assert any(
        row["rule_key"] == SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        and row["event_created"] is True
        for row in first["results"]
    )

    no_reminder = SLAAutomationService.evaluate_and_act(
        now_utc=first_eval_time + timedelta(minutes=5)
    )
    assert any(
        row["rule_key"] == SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        and row["event_created"] is False
        for row in no_reminder["results"]
    )

    reminder = SLAAutomationService.evaluate_and_act(
        now_utc=first_eval_time + timedelta(minutes=11)
    )
    assert any(
        row["rule_key"] == SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        and row["event_created"] is True
        and row["event_status"] == "triggered"
        for row in reminder["results"]
    )

    stockout_events = list(
        SLAAutomationEvent.objects.filter(
            rule_key=SLAAutomationService.RULE_STOCKOUT_OPEN_MINUTES
        ).order_by("created_at")
    )
    assert len(stockout_events) == 2
    assert stockout_events[1].payload["repeat"] is True
