from datetime import timedelta

import pytest
from django.utils import timezone

from rules.services import RulesService
from ticket.models import StockoutIncident
from ticket.services_sla_escalation import SLAAutomationEscalationService
from ticket.tasks import evaluate_sla_automation

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

    def _fake_deliver_for_event_id(cls, *, event_id: int):
        called_event_ids.append(event_id)
        return {
            "event_id": event_id,
            "delivered": True,
            "channels": [{"channel": "telegram", "success": True}],
        }

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "deliver_for_event_id",
        classmethod(_fake_deliver_for_event_id),
    )

    result = evaluate_sla_automation()
    assert result["enabled"] is True

    created_event_ids = [
        row["event_id"]
        for row in result["results"]
        if row.get("event_created") is True and isinstance(row.get("event_id"), int)
    ]
    assert created_event_ids
    assert called_event_ids == created_event_ids
    assert [row["event_id"] for row in result["delivery"]] == created_event_ids


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

    called_event_ids: list[int] = []

    def _fake_deliver_for_event_id(cls, *, event_id: int):
        called_event_ids.append(event_id)
        return {"event_id": event_id, "delivered": True, "channels": []}

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "deliver_for_event_id",
        classmethod(_fake_deliver_for_event_id),
    )

    result = evaluate_sla_automation()
    assert result["enabled"] is True
    assert result["delivery"] == []
    assert called_event_ids == []
