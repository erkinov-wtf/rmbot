from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from ticket.models import SLAAutomationEvent

logger = logging.getLogger(__name__)


class SLAAutomationEscalationService:
    DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0

    @staticmethod
    def _split_csv(raw: str | None) -> list[str]:
        if not isinstance(raw, str):
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @classmethod
    def _request_timeout_seconds(cls) -> float:
        raw = getattr(settings, "SLA_ESCALATION_REQUEST_TIMEOUT_SECONDS", 5)
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            parsed = cls.DEFAULT_REQUEST_TIMEOUT_SECONDS
        return max(parsed, 1.0)

    @classmethod
    def _telegram_bot_token(cls) -> str:
        dedicated_token = getattr(settings, "SLA_ESCALATION_TELEGRAM_BOT_TOKEN", "")
        if dedicated_token:
            return str(dedicated_token).strip()
        return str(getattr(settings, "BOT_TOKEN", "")).strip()

    @classmethod
    def _telegram_chat_ids(cls) -> list[str]:
        return cls._split_csv(getattr(settings, "SLA_ESCALATION_TELEGRAM_CHAT_IDS", ""))

    @classmethod
    def _email_recipients(cls) -> list[str]:
        return cls._split_csv(getattr(settings, "SLA_ESCALATION_EMAIL_RECIPIENTS", ""))

    @classmethod
    def _ops_webhook_url(cls) -> str:
        return str(getattr(settings, "SLA_ESCALATION_OPS_WEBHOOK_URL", "")).strip()

    @classmethod
    def _ops_webhook_token(cls) -> str:
        return str(getattr(settings, "SLA_ESCALATION_OPS_WEBHOOK_TOKEN", "")).strip()

    @staticmethod
    def _event_payload(event: SLAAutomationEvent) -> dict[str, Any]:
        return event.payload if isinstance(event.payload, dict) else {}

    @classmethod
    def _build_subject(cls, *, event: SLAAutomationEvent) -> str:
        prefix = str(
            getattr(
                settings, "SLA_ESCALATION_EMAIL_SUBJECT_PREFIX", "[Rent Market SLA]"
            )
        ).strip()
        core = f"{event.status.upper()} {event.rule_key}"
        return f"{prefix} {core}".strip()

    @classmethod
    def _build_message(cls, *, event: SLAAutomationEvent) -> str:
        payload = cls._event_payload(event)
        created_at = event.created_at or timezone.now()
        local_created_at = timezone.localtime(created_at)

        lines = [
            "Rent Market SLA automation event",
            f"event_id: {event.id}",
            f"status: {event.status}",
            f"severity: {event.severity}",
            f"rule_key: {event.rule_key}",
            f"metric_value: {event.metric_value}",
            f"threshold_value: {event.threshold_value}",
            f"recommended_action: {payload.get('recommended_action', '')}",
            f"evaluated_at: {payload.get('evaluated_at', local_created_at.isoformat())}",
        ]
        if payload.get("repeat") is True:
            lines.append("repeat: true")
        if payload.get("resolved_from_event_id") is not None:
            lines.append(
                f"resolved_from_event_id: {payload.get('resolved_from_event_id')}"
            )
        return "\n".join(lines)

    @classmethod
    def _build_ops_payload(cls, *, event: SLAAutomationEvent) -> dict[str, Any]:
        payload = cls._event_payload(event)
        return {
            "event_id": event.id,
            "rule_key": event.rule_key,
            "status": event.status,
            "severity": event.severity,
            "metric_value": event.metric_value,
            "threshold_value": event.threshold_value,
            "payload": payload,
            "created_at": (
                event.created_at.isoformat()
                if event.created_at
                else timezone.now().isoformat()
            ),
        }

    @staticmethod
    def _post_json(
        *,
        url: str,
        payload: dict[str, Any],
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        return requests.post(
            url,
            json=payload,
            timeout=timeout_seconds,
            headers=headers,
        )

    @classmethod
    def _send_telegram_message(
        cls,
        *,
        bot_token: str,
        chat_id: str,
        message: str,
    ) -> dict[str, Any]:
        try:
            response = cls._post_json(
                url=f"https://api.telegram.org/bot{bot_token}/sendMessage",
                payload={"chat_id": chat_id, "text": message},
                timeout_seconds=cls._request_timeout_seconds(),
            )
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError:
                body = {}
            if isinstance(body, dict) and body.get("ok") is False:
                raise RuntimeError(
                    str(body.get("description") or "Telegram API returned ok=false")
                )
            return {
                "channel": "telegram",
                "target": chat_id,
                "success": True,
            }
        except Exception as exc:
            logger.exception(
                "Failed to send SLA escalation Telegram message for chat_id=%s.",
                chat_id,
            )
            return {
                "channel": "telegram",
                "target": chat_id,
                "success": False,
                "error": str(exc),
            }

    @classmethod
    def _send_email(
        cls,
        *,
        recipients: list[str],
        subject: str,
        message: str,
    ) -> dict[str, Any]:
        try:
            delivered_count = send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=recipients,
                fail_silently=False,
            )
            if delivered_count <= 0:
                raise RuntimeError("Email backend returned zero delivered messages.")
            return {
                "channel": "email",
                "target": ",".join(recipients),
                "success": True,
                "delivered_count": int(delivered_count),
            }
        except Exception as exc:
            logger.exception(
                "Failed to send SLA escalation email to recipients=%s.",
                recipients,
            )
            return {
                "channel": "email",
                "target": ",".join(recipients),
                "success": False,
                "error": str(exc),
            }

    @classmethod
    def _send_ops_webhook(
        cls,
        *,
        webhook_url: str,
        webhook_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if webhook_token:
            headers["Authorization"] = f"Bearer {webhook_token}"
        try:
            response = cls._post_json(
                url=webhook_url,
                payload=payload,
                timeout_seconds=cls._request_timeout_seconds(),
                headers=headers or None,
            )
            response.raise_for_status()
            return {
                "channel": "ops_webhook",
                "target": webhook_url,
                "success": True,
            }
        except Exception as exc:
            logger.exception(
                "Failed to send SLA escalation webhook payload to url=%s.",
                webhook_url,
            )
            return {
                "channel": "ops_webhook",
                "target": webhook_url,
                "success": False,
                "error": str(exc),
            }

    @classmethod
    def deliver_event(cls, *, event: SLAAutomationEvent) -> dict[str, Any]:
        message = cls._build_message(event=event)
        subject = cls._build_subject(event=event)
        webhook_payload = cls._build_ops_payload(event=event)

        channels: list[dict[str, Any]] = []
        bot_token = cls._telegram_bot_token()
        chat_ids = cls._telegram_chat_ids()
        if chat_ids and not bot_token:
            channels.append(
                {
                    "channel": "telegram",
                    "target": ",".join(chat_ids),
                    "success": False,
                    "error": "SLA_ESCALATION_TELEGRAM_BOT_TOKEN/BOT_TOKEN is not configured.",
                }
            )
        elif bot_token:
            for chat_id in chat_ids:
                channels.append(
                    cls._send_telegram_message(
                        bot_token=bot_token,
                        chat_id=chat_id,
                        message=message,
                    )
                )

        email_recipients = cls._email_recipients()
        if email_recipients:
            channels.append(
                cls._send_email(
                    recipients=email_recipients,
                    subject=subject,
                    message=message,
                )
            )

        webhook_url = cls._ops_webhook_url()
        if webhook_url:
            channels.append(
                cls._send_ops_webhook(
                    webhook_url=webhook_url,
                    webhook_token=cls._ops_webhook_token(),
                    payload=webhook_payload,
                )
            )

        delivered = any(channel.get("success") is True for channel in channels)
        response = {
            "event_id": event.id,
            "rule_key": event.rule_key,
            "status": event.status,
            "delivered": delivered,
            "channels": channels,
        }
        if not channels:
            response["reason"] = "no_channels_configured"
        return response

    @classmethod
    def deliver_for_event_id(cls, *, event_id: int) -> dict[str, Any]:
        event = SLAAutomationEvent.objects.filter(pk=event_id).first()
        if event is None:
            return {
                "event_id": event_id,
                "delivered": False,
                "channels": [],
                "reason": "event_not_found",
            }
        return cls.deliver_event(event=event)
