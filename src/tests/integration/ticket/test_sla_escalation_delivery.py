from datetime import timedelta

import pytest
from django.utils import timezone

from rules.services import RulesService
from ticket.models import StockoutIncident
from ticket.tasks import deliver_sla_automation_event, evaluate_sla_automation

pytestmark = pytest.mark.django_db


def _configure_automation(*, actor_user_id: int) -> None:
    config = RulesService.get_active_rules_config()
    config["sla"]["automation"] = {
        "enabled": True,
        "cooldown_minutes": 30,
        "max_open_stockout_minutes": 5,
        "max_backlog_black_plus_count": 999,
        "min_first_pass_rate_percent": 0,
        "min_qc_done_tickets": 999,
    }
    RulesService.update_rules_config(
        config=config,
        actor_user_id=actor_user_id,
        reason="SLA escalation delivery test config",
    )


def test_evaluate_sla_automation_task_dispatches_delivery(
    user_factory,
    monkeypatch,
):
    actor = user_factory(
        username="sla_delivery_actor",
        first_name="SLA",
        email="sla_delivery_actor@example.com",
    )
    _configure_automation(actor_user_id=actor.id)

    now = timezone.now()
    StockoutIncident.objects.create(
        started_at=now - timedelta(minutes=8),
        is_active=True,
        ready_count_at_start=0,
    )

    called_event_ids: list[int] = []

    def _fake_delay(*args, **kwargs):
        event_id = kwargs.get("event_id")
        if event_id is None and args:
            event_id = args[0]
        if isinstance(event_id, int):
            called_event_ids.append(event_id)

    monkeypatch.setattr(deliver_sla_automation_event, "delay", _fake_delay)

    result = evaluate_sla_automation()
    assert result["enabled"] is True

    created_event_ids = [
        row["event_id"]
        for row in result["results"]
        if row.get("event_created") is True and isinstance(row.get("event_id"), int)
    ]
    assert created_event_ids
    assert called_event_ids == created_event_ids
    assert result["delivery"] == [
        {"event_id": event_id, "queued": True} for event_id in created_event_ids
    ]


def test_evaluate_sla_automation_task_skips_delivery_without_events(
    user_factory,
    monkeypatch,
):
    actor = user_factory(
        username="sla_delivery_actor_2",
        first_name="SLA2",
        email="sla_delivery_actor_2@example.com",
    )
    _configure_automation(actor_user_id=actor.id)

    called_count = 0

    def _fake_delay(*args, **kwargs):
        nonlocal called_count
        called_count += 1

    monkeypatch.setattr(deliver_sla_automation_event, "delay", _fake_delay)

    result = evaluate_sla_automation()
    assert result["enabled"] is True
    assert result["delivery"] == []
    assert called_count == 0


def test_evaluate_sla_automation_task_marks_enqueue_errors(
    user_factory,
    monkeypatch,
):
    actor = user_factory(
        username="sla_delivery_actor_3",
        first_name="SLA3",
        email="sla_delivery_actor_3@example.com",
    )
    _configure_automation(actor_user_id=actor.id)

    now = timezone.now()
    StockoutIncident.objects.create(
        started_at=now - timedelta(minutes=8),
        is_active=True,
        ready_count_at_start=0,
    )

    def _fake_delay(*args, **kwargs):
        raise RuntimeError("queue down")

    monkeypatch.setattr(deliver_sla_automation_event, "delay", _fake_delay)

    result = evaluate_sla_automation()
    created_event_ids = [
        row["event_id"]
        for row in result["results"]
        if row.get("event_created") is True and isinstance(row.get("event_id"), int)
    ]
    assert result["delivery"] == [
        {
            "event_id": event_id,
            "queued": False,
            "reason": "delivery_enqueue_error",
        }
        for event_id in created_event_ids
    ]
