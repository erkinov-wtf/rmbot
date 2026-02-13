import pytest
from celery.exceptions import Retry

from core.utils.constants import (
    SLAAutomationDeliveryAttemptStatus,
    SLAAutomationEventSeverity,
    SLAAutomationEventStatus,
)
from ticket.models import SLAAutomationDeliveryAttempt, SLAAutomationEvent
from ticket.services_sla_escalation import SLAAutomationEscalationService
from ticket.tasks import deliver_sla_automation_event

pytestmark = pytest.mark.django_db


def _create_event() -> SLAAutomationEvent:
    return SLAAutomationEvent.objects.create(
        rule_key="stockout_open_minutes",
        status=SLAAutomationEventStatus.TRIGGERED,
        severity=SLAAutomationEventSeverity.CRITICAL,
        metric_value=12,
        threshold_value=5,
        payload={"recommended_action": "notify_ops_and_dispatch_recovery"},
    )


def test_delivery_task_retries_with_backoff_and_records_attempt(
    monkeypatch,
    settings,
):
    event = _create_event()
    settings.SLA_ESCALATION_MAX_RETRIES = 2
    settings.SLA_ESCALATION_RETRY_BACKOFF_SECONDS = 7
    settings.SLA_ESCALATION_RETRY_BACKOFF_MAX_SECONDS = 60

    def _fake_deliver_for_event_id(cls, *, event_id: int):
        assert event_id == event.id
        return {
            "event_id": event_id,
            "rule_key": event.rule_key,
            "status": event.status,
            "delivered": False,
            "channels": [
                {
                    "channel": "telegram",
                    "target": "123",
                    "success": False,
                    "retryable": True,
                    "error": "timeout",
                }
            ],
        }

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "deliver_for_event_id",
        classmethod(_fake_deliver_for_event_id),
    )

    with pytest.raises(Retry):
        deliver_sla_automation_event(event_id=event.id)

    attempt = SLAAutomationDeliveryAttempt.objects.get(event=event)
    assert attempt.attempt_number == 1
    assert attempt.status == SLAAutomationDeliveryAttemptStatus.FAILED
    assert attempt.delivered is False
    assert attempt.should_retry is True
    assert attempt.retry_backoff_seconds == 7


def test_delivery_task_non_retryable_failure_records_final_attempt(settings):
    event = _create_event()
    settings.SLA_ESCALATION_MAX_RETRIES = 3
    settings.SLA_ESCALATION_TELEGRAM_CHAT_IDS = ""
    settings.SLA_ESCALATION_EMAIL_RECIPIENTS = ""
    settings.SLA_ESCALATION_OPS_WEBHOOK_URL = ""

    result = deliver_sla_automation_event(event_id=event.id)

    assert result["delivered"] is False
    assert result["reason"] == "no_channels_configured"
    assert result["should_retry"] is False
    assert result["retry_backoff_seconds"] == 0

    attempt = SLAAutomationDeliveryAttempt.objects.get(event=event)
    assert attempt.status == SLAAutomationDeliveryAttemptStatus.FAILED
    assert attempt.reason == "no_channels_configured"
    assert attempt.should_retry is False


def test_delivery_task_skips_when_event_already_delivered(monkeypatch):
    event = _create_event()
    SLAAutomationDeliveryAttempt.objects.create(
        event=event,
        attempt_number=1,
        status=SLAAutomationDeliveryAttemptStatus.SUCCESS,
        delivered=True,
        should_retry=False,
        retry_backoff_seconds=0,
        reason="",
        payload={"channels": [{"channel": "telegram", "success": True}]},
    )

    def _fail_if_deliver_called(cls, *, event):
        pytest.fail("deliver_event should not be called for already delivered events")

    monkeypatch.setattr(
        SLAAutomationEscalationService,
        "deliver_event",
        classmethod(_fail_if_deliver_called),
    )

    result = deliver_sla_automation_event(event_id=event.id)

    assert result["delivered"] is True
    assert result["reason"] == "already_delivered"
    assert result["should_retry"] is False

    attempts = list(
        SLAAutomationDeliveryAttempt.objects.filter(event=event).order_by(
            "attempt_number"
        )
    )
    assert len(attempts) == 2
    assert attempts[1].status == SLAAutomationDeliveryAttemptStatus.SKIPPED
    assert attempts[1].reason == "already_delivered"
    assert attempts[1].delivered is True
