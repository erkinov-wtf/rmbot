import pytest

from core.utils.constants import SLAAutomationEventSeverity, SLAAutomationEventStatus
from rules.services import RulesService
from ticket.models import SLAAutomationEvent
from ticket.services_sla_escalation import SLAAutomationEscalationService

pytestmark = pytest.mark.django_db


def _configure_escalation(*, actor_user_id: int, escalation_config: dict) -> None:
    config = RulesService.get_active_rules_config()
    config["sla"]["escalation"] = escalation_config
    RulesService.update_rules_config(
        config=config,
        actor_user_id=actor_user_id,
        reason="SLA escalation routing test config",
    )


def test_escalation_routing_uses_matching_route_channels(
    user_factory,
    monkeypatch,
    settings,
):
    actor = user_factory(
        username="sla_routing_actor_1",
        first_name="SLA",
        email="sla_routing_actor_1@example.com",
    )
    _configure_escalation(
        actor_user_id=actor.id,
        escalation_config={
            "enabled": True,
            "default_channels": [],
            "routes": [
                {
                    "rule_keys": ["stockout_open_minutes"],
                    "severities": ["critical"],
                    "statuses": ["triggered"],
                    "channels": ["ops_webhook"],
                }
            ],
        },
    )

    event = SLAAutomationEvent.objects.create(
        rule_key="stockout_open_minutes",
        status=SLAAutomationEventStatus.TRIGGERED,
        severity=SLAAutomationEventSeverity.CRITICAL,
        metric_value=12,
        threshold_value=5,
        payload={"recommended_action": "notify_ops_and_dispatch_recovery"},
    )

    settings.SLA_ESCALATION_OPS_WEBHOOK_URL = "https://example.com/webhook"

    def _fail_if_called(*args, **kwargs):
        pytest.fail("Unexpected channel delivery call.")

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_telegram_message",
        classmethod(_fail_if_called),
    )
    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_email",
        classmethod(_fail_if_called),
    )

    ops_calls: list[dict] = []

    def _fake_ops_webhook(
        cls,
        *,
        webhook_url: str,
        webhook_token: str,
        payload: dict,
    ):
        ops_calls.append(
            {"url": webhook_url, "token": webhook_token, "payload": payload}
        )
        return {
            "channel": "ops_webhook",
            "target": webhook_url,
            "success": True,
            "retryable": False,
        }

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_ops_webhook",
        classmethod(_fake_ops_webhook),
    )

    result = SLAAutomationEscalationService.deliver_for_event_id(event_id=event.id)
    assert result["delivered"] is True
    assert [row.get("channel") for row in result["channels"]] == ["ops_webhook"]
    assert len(ops_calls) == 1


def test_escalation_routing_falls_back_to_default_channels(
    user_factory,
    monkeypatch,
    settings,
):
    actor = user_factory(
        username="sla_routing_actor_2",
        first_name="SLA2",
        email="sla_routing_actor_2@example.com",
    )
    _configure_escalation(
        actor_user_id=actor.id,
        escalation_config={
            "enabled": True,
            "default_channels": ["email"],
            "routes": [
                {
                    "rule_keys": ["stockout_open_minutes"],
                    "repeat": True,
                    "channels": ["ops_webhook"],
                }
            ],
        },
    )

    event = SLAAutomationEvent.objects.create(
        rule_key="stockout_open_minutes",
        status=SLAAutomationEventStatus.TRIGGERED,
        severity=SLAAutomationEventSeverity.CRITICAL,
        metric_value=12,
        threshold_value=5,
        payload={"recommended_action": "notify_ops_and_dispatch_recovery"},
    )

    settings.SLA_ESCALATION_EMAIL_RECIPIENTS = "ops@example.com"

    def _fail_if_called(*args, **kwargs):
        pytest.fail("Unexpected channel delivery call.")

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_telegram_message",
        classmethod(_fail_if_called),
    )
    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_ops_webhook",
        classmethod(_fail_if_called),
    )

    email_calls: list[dict] = []

    def _fake_send_email(
        cls,
        *,
        recipients: list[str],
        subject: str,
        message: str,
    ):
        email_calls.append(
            {"recipients": recipients, "subject": subject, "message": message}
        )
        return {
            "channel": "email",
            "target": ",".join(recipients),
            "success": True,
            "delivered_count": 1,
            "retryable": False,
        }

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "_send_email",
        classmethod(_fake_send_email),
    )

    result = SLAAutomationEscalationService.deliver_for_event_id(event_id=event.id)
    assert result["delivered"] is True
    assert [row.get("channel") for row in result["channels"]] == ["email"]
    assert len(email_calls) == 1
