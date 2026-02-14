from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from rules.services import RulesService
from ticket.models import SLAAutomationDeliveryAttempt, SLAAutomationEvent

logger = logging.getLogger(__name__)


class SLAAutomationEscalationService:
    """Delivers SLA events to external channels with retry-safe attempt tracking."""

    DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BACKOFF_SECONDS = 60
    DEFAULT_RETRY_BACKOFF_MAX_SECONDS = 900
    NON_RETRYABLE_REASONS = {
        "event_not_found",
        "no_channels_configured",
        "already_delivered",
        "no_channels_routed",
        "routing_disabled",
    }
    ALLOWED_CHANNELS = ("telegram", "email", "ops_webhook")

    @staticmethod
    def _parse_int(value: Any, *, default: int, min_value: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(parsed, min_value)

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
    def max_retries(cls) -> int:
        return cls._parse_int(
            getattr(settings, "SLA_ESCALATION_MAX_RETRIES", cls.DEFAULT_MAX_RETRIES),
            default=cls.DEFAULT_MAX_RETRIES,
            min_value=0,
        )

    @classmethod
    def _retry_backoff_base_seconds(cls) -> int:
        return cls._parse_int(
            getattr(
                settings,
                "SLA_ESCALATION_RETRY_BACKOFF_SECONDS",
                cls.DEFAULT_RETRY_BACKOFF_SECONDS,
            ),
            default=cls.DEFAULT_RETRY_BACKOFF_SECONDS,
            min_value=1,
        )

    @classmethod
    def _retry_backoff_max_seconds(cls) -> int:
        return cls._parse_int(
            getattr(
                settings,
                "SLA_ESCALATION_RETRY_BACKOFF_MAX_SECONDS",
                cls.DEFAULT_RETRY_BACKOFF_MAX_SECONDS,
            ),
            default=cls.DEFAULT_RETRY_BACKOFF_MAX_SECONDS,
            min_value=1,
        )

    @classmethod
    def retry_backoff_seconds(cls, *, retry_index: int) -> int:
        # retry_index is 1-based (first retry after first failed attempt).
        normalized_retry_index = max(int(retry_index), 1)
        base = cls._retry_backoff_base_seconds()
        max_backoff = max(cls._retry_backoff_max_seconds(), base)
        backoff = base * (2 ** (normalized_retry_index - 1))
        return min(backoff, max_backoff)

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
        return event.payload_data()

    @classmethod
    def _routing_config(cls) -> dict[str, Any]:
        default = RulesService.default_rules_config()["sla"].get("escalation", {})
        if not isinstance(default, dict):
            default = {}

        rules_config = RulesService.get_active_rules_config()
        raw = rules_config.get("sla", {}).get("escalation", {})
        if not isinstance(raw, dict):
            raw = {}

        enabled = raw.get("enabled", default.get("enabled", True))
        if not isinstance(enabled, bool):
            enabled = bool(default.get("enabled", True))

        default_channels = raw.get(
            "default_channels", default.get("default_channels", [])
        )
        if not isinstance(default_channels, list):
            default_channels = list(default.get("default_channels", []))

        routes = raw.get("routes", default.get("routes", []))
        if not isinstance(routes, list):
            routes = list(default.get("routes", []))

        return {
            "enabled": enabled,
            "default_channels": [
                str(item).strip().lower()
                for item in default_channels
                if isinstance(item, str) and item.strip()
            ],
            "routes": routes,
        }

    @staticmethod
    def _event_is_repeat(event: SLAAutomationEvent) -> bool:
        return event.is_repeat()

    @classmethod
    def _select_channels_for_event(cls, *, event: SLAAutomationEvent) -> dict[str, Any]:
        config = cls._routing_config()
        if config.get("enabled") is not True:
            return {"enabled": False, "channels": [], "source": "disabled"}

        event_repeat = cls._event_is_repeat(event)
        event_status = str(event.status or "").strip().lower()
        event_severity = str(event.severity or "").strip().lower()
        event_rule_key = str(event.rule_key or "").strip()

        # First matching route wins; fallback goes to default channels.
        for idx, raw_route in enumerate(config.get("routes") or []):
            if not isinstance(raw_route, dict):
                continue

            channels = raw_route.get("channels")
            if not isinstance(channels, list):
                continue
            normalized_channels = [
                str(ch).strip().lower()
                for ch in channels
                if isinstance(ch, str) and ch.strip()
            ]

            rule_keys = raw_route.get("rule_keys")
            if isinstance(rule_keys, list):
                normalized_rule_keys = [
                    str(rk).strip()
                    for rk in rule_keys
                    if isinstance(rk, str) and rk.strip()
                ]
                if normalized_rule_keys and event_rule_key not in normalized_rule_keys:
                    continue

            statuses = raw_route.get("statuses")
            if isinstance(statuses, list):
                normalized_statuses = [
                    str(st).strip().lower()
                    for st in statuses
                    if isinstance(st, str) and st.strip()
                ]
                if normalized_statuses and event_status not in normalized_statuses:
                    continue

            severities = raw_route.get("severities")
            if isinstance(severities, list):
                normalized_severities = [
                    str(sev).strip().lower()
                    for sev in severities
                    if isinstance(sev, str) and sev.strip()
                ]
                if (
                    normalized_severities
                    and event_severity not in normalized_severities
                ):
                    continue

            repeat = raw_route.get("repeat")
            if isinstance(repeat, bool) and repeat != event_repeat:
                continue

            return {
                "enabled": True,
                "channels": normalized_channels,
                "source": "route",
                "route_index": idx,
            }

        default_channels = config.get("default_channels") or []
        return {
            "enabled": True,
            "channels": default_channels,
            "source": "default",
        }

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
                "retryable": False,
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
                "retryable": True,
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
                "retryable": False,
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
                "retryable": True,
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
                "retryable": False,
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
                "retryable": True,
            }

    @classmethod
    def deliver_event(cls, *, event: SLAAutomationEvent) -> dict[str, Any]:
        routing = cls._select_channels_for_event(event=event)
        if routing.get("enabled") is False:
            return {
                "event_id": event.id,
                "rule_key": event.rule_key,
                "status": event.status,
                "delivered": False,
                "channels": [],
                "reason": "routing_disabled",
            }

        selected_channels = [
            ch for ch in (routing.get("channels") or []) if ch in cls.ALLOWED_CHANNELS
        ]
        if not selected_channels:
            return {
                "event_id": event.id,
                "rule_key": event.rule_key,
                "status": event.status,
                "delivered": False,
                "channels": [],
                "reason": "no_channels_routed",
            }

        message = cls._build_message(event=event)
        subject = cls._build_subject(event=event)
        webhook_payload = cls._build_ops_payload(event=event)

        channels: list[dict[str, Any]] = []
        routing_source = str(routing.get("source") or "default")

        if "telegram" in selected_channels:
            bot_token = cls._telegram_bot_token()
            chat_ids = cls._telegram_chat_ids()
            if chat_ids and not bot_token:
                channels.append(
                    {
                        "channel": "telegram",
                        "target": ",".join(chat_ids),
                        "success": False,
                        "error": "SLA_ESCALATION_TELEGRAM_BOT_TOKEN/BOT_TOKEN is not configured.",
                        "retryable": False,
                    }
                )
            elif bot_token and chat_ids:
                for chat_id in chat_ids:
                    channels.append(
                        cls._send_telegram_message(
                            bot_token=bot_token,
                            chat_id=chat_id,
                            message=message,
                        )
                    )
            elif routing_source == "route":
                channels.append(
                    {
                        "channel": "telegram",
                        "target": "",
                        "success": False,
                        "error": "SLA_ESCALATION_TELEGRAM_CHAT_IDS is not configured.",
                        "retryable": False,
                    }
                )

        if "email" in selected_channels:
            email_recipients = cls._email_recipients()
            if email_recipients:
                channels.append(
                    cls._send_email(
                        recipients=email_recipients,
                        subject=subject,
                        message=message,
                    )
                )
            elif routing_source == "route":
                channels.append(
                    {
                        "channel": "email",
                        "target": "",
                        "success": False,
                        "error": "SLA_ESCALATION_EMAIL_RECIPIENTS is not configured.",
                        "retryable": False,
                    }
                )

        if "ops_webhook" in selected_channels:
            webhook_url = cls._ops_webhook_url()
            if webhook_url:
                channels.append(
                    cls._send_ops_webhook(
                        webhook_url=webhook_url,
                        webhook_token=cls._ops_webhook_token(),
                        payload=webhook_payload,
                    )
                )
            elif routing_source == "route":
                channels.append(
                    {
                        "channel": "ops_webhook",
                        "target": "",
                        "success": False,
                        "error": "SLA_ESCALATION_OPS_WEBHOOK_URL is not configured.",
                        "retryable": False,
                    }
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
    def _already_delivered(cls, *, event_id: int) -> bool:
        return SLAAutomationDeliveryAttempt.domain.has_success_for_event(
            event_id=event_id
        )

    @classmethod
    def is_retryable_failure(cls, *, response: dict[str, Any]) -> bool:
        if response.get("delivered") is True:
            return False
        reason = response.get("reason")
        if isinstance(reason, str) and reason in cls.NON_RETRYABLE_REASONS:
            return False
        channels = response.get("channels")
        if not isinstance(channels, list):
            return False
        for channel in channels:
            if (
                isinstance(channel, dict)
                and channel.get("success") is False
                and channel.get("retryable") is True
            ):
                return True
        return False

    @classmethod
    def record_attempt(
        cls,
        *,
        event_id: int,
        attempt_number: int,
        task_id: str,
        response: dict[str, Any],
        should_retry: bool,
        retry_backoff_seconds: int,
    ) -> SLAAutomationDeliveryAttempt | None:
        event = SLAAutomationEvent.domain.get_by_id(event_id=event_id)
        if event is None:
            return None
        return SLAAutomationDeliveryAttempt.create_from_delivery_response(
            event=event,
            attempt_number=attempt_number,
            task_id=task_id,
            response=response,
            should_retry=should_retry,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    @classmethod
    def deliver_for_event_id(cls, *, event_id: int) -> dict[str, Any]:
        event = SLAAutomationEvent.domain.get_by_id(event_id=event_id)
        if event is None:
            return {
                "event_id": event_id,
                "delivered": False,
                "channels": [],
                "reason": "event_not_found",
            }
        if cls._already_delivered(event_id=event.id):
            return {
                "event_id": event.id,
                "rule_key": event.rule_key,
                "status": event.status,
                "delivered": True,
                "channels": [],
                "reason": "already_delivered",
            }
        return cls.deliver_event(event=event)
