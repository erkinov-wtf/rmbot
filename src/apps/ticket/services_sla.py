from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from core.utils.constants import (
    SLAAutomationEventSeverity,
    SLAAutomationEventStatus,
)
from rules.services import RulesService
from ticket.models import (
    ACTIVE_TICKET_STATUSES,
    SLAAutomationEvent,
    StockoutIncident,
    Ticket,
)
from ticket.services_analytics import TicketAnalyticsService


class SLAAutomationService:
    RULE_STOCKOUT_OPEN_MINUTES = "stockout_open_minutes"
    RULE_BACKLOG_BLACK_PLUS = "backlog_black_plus_count"
    RULE_FIRST_PASS_RATE = "first_pass_rate_percent"

    @staticmethod
    def _parse_int(value: Any, *, default: int = 0, min_value: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(min_value, parsed)

    @classmethod
    def _automation_config(cls) -> dict[str, int | bool]:
        default_config = RulesService.default_rules_config()["sla"]["automation"]
        rules_config = RulesService.get_active_rules_config()
        raw = rules_config.get("sla", {}).get("automation", {})
        if not isinstance(raw, dict):
            raw = {}

        enabled = raw.get("enabled", default_config["enabled"])
        if not isinstance(enabled, bool):
            enabled = bool(default_config["enabled"])

        return {
            "enabled": enabled,
            "cooldown_minutes": cls._parse_int(
                raw.get("cooldown_minutes", default_config["cooldown_minutes"]),
                default=int(default_config["cooldown_minutes"]),
                min_value=0,
            ),
            "max_open_stockout_minutes": cls._parse_int(
                raw.get(
                    "max_open_stockout_minutes",
                    default_config["max_open_stockout_minutes"],
                ),
                default=int(default_config["max_open_stockout_minutes"]),
                min_value=0,
            ),
            "max_backlog_black_plus_count": cls._parse_int(
                raw.get(
                    "max_backlog_black_plus_count",
                    default_config["max_backlog_black_plus_count"],
                ),
                default=int(default_config["max_backlog_black_plus_count"]),
                min_value=0,
            ),
            "min_first_pass_rate_percent": cls._parse_int(
                raw.get(
                    "min_first_pass_rate_percent",
                    default_config["min_first_pass_rate_percent"],
                ),
                default=int(default_config["min_first_pass_rate_percent"]),
                min_value=0,
            ),
            "min_qc_done_tickets": cls._parse_int(
                raw.get("min_qc_done_tickets", default_config["min_qc_done_tickets"]),
                default=int(default_config["min_qc_done_tickets"]),
                min_value=0,
            ),
        }

    @classmethod
    def _collect_metrics(cls, *, now_utc) -> dict[str, int | float | bool]:
        open_incident = (
            StockoutIncident.objects.filter(is_active=True)
            .order_by("-started_at")
            .first()
        )
        open_stockout_minutes = 0
        if open_incident:
            open_stockout_minutes = max(
                int((now_utc - open_incident.started_at).total_seconds() // 60),
                0,
            )

        backlog_black_plus_count = Ticket.objects.filter(
            deleted_at__isnull=True,
            status__in=ACTIVE_TICKET_STATUSES,
            flag_minutes__gt=180,
        ).count()

        fleet_summary = TicketAnalyticsService.fleet_summary()
        qc_totals = fleet_summary.get("qc", {}).get("totals", {})
        qc_done = int(qc_totals.get("done") or 0)
        first_pass_rate_percent = float(qc_totals.get("first_pass_rate_percent") or 0.0)

        return {
            "open_stockout_minutes": open_stockout_minutes,
            "has_open_stockout": open_incident is not None,
            "backlog_black_plus_count": backlog_black_plus_count,
            "qc_done": qc_done,
            "first_pass_rate_percent": first_pass_rate_percent,
        }

    @classmethod
    def _latest_rule_event(cls, *, rule_key: str) -> SLAAutomationEvent | None:
        return (
            SLAAutomationEvent.objects.filter(rule_key=rule_key)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def _latest_event_time(
        event: SLAAutomationEvent, *, fallback_now: datetime
    ) -> datetime:
        payload = event.payload if isinstance(event.payload, dict) else {}
        raw = payload.get("evaluated_at")
        if isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo is None:
                    parsed = timezone.make_aware(parsed, timezone.utc)
                return parsed
            except ValueError:
                pass
        return event.created_at or fallback_now

    @classmethod
    def _create_event(
        cls,
        *,
        rule_key: str,
        status: str,
        severity: str,
        metric_value: float,
        threshold_value: float,
        payload: dict[str, Any],
    ) -> SLAAutomationEvent:
        return SLAAutomationEvent.objects.create(
            rule_key=rule_key,
            status=status,
            severity=severity,
            metric_value=metric_value,
            threshold_value=threshold_value,
            payload=payload,
        )

    @classmethod
    def evaluate_and_act(cls, *, now_utc=None) -> dict[str, Any]:
        now = now_utc or timezone.now()
        config = cls._automation_config()
        metrics = cls._collect_metrics(now_utc=now)

        if not config["enabled"]:
            return {
                "enabled": False,
                "metrics": metrics,
                "results": [],
            }

        evaluations = [
            {
                "rule_key": cls.RULE_STOCKOUT_OPEN_MINUTES,
                "breached": bool(metrics["has_open_stockout"])
                and int(metrics["open_stockout_minutes"])
                > int(config["max_open_stockout_minutes"]),
                "metric_value": float(metrics["open_stockout_minutes"]),
                "threshold_value": float(config["max_open_stockout_minutes"]),
                "severity": SLAAutomationEventSeverity.CRITICAL,
                "recommended_action": "notify_ops_and_dispatch_recovery",
                "extra": {
                    "has_open_stockout": bool(metrics["has_open_stockout"]),
                },
            },
            {
                "rule_key": cls.RULE_BACKLOG_BLACK_PLUS,
                "breached": int(metrics["backlog_black_plus_count"])
                > int(config["max_backlog_black_plus_count"]),
                "metric_value": float(metrics["backlog_black_plus_count"]),
                "threshold_value": float(config["max_backlog_black_plus_count"]),
                "severity": SLAAutomationEventSeverity.WARNING,
                "recommended_action": "prioritize_black_plus_backlog",
                "extra": {},
            },
            {
                "rule_key": cls.RULE_FIRST_PASS_RATE,
                "breached": int(metrics["qc_done"])
                >= int(config["min_qc_done_tickets"])
                and float(metrics["first_pass_rate_percent"])
                < float(config["min_first_pass_rate_percent"]),
                "metric_value": float(metrics["first_pass_rate_percent"]),
                "threshold_value": float(config["min_first_pass_rate_percent"]),
                "severity": SLAAutomationEventSeverity.WARNING,
                "recommended_action": "trigger_qc_coaching_review",
                "extra": {
                    "qc_done": int(metrics["qc_done"]),
                    "min_qc_done_tickets": int(config["min_qc_done_tickets"]),
                },
            },
        ]

        cooldown = int(config["cooldown_minutes"])
        results: list[dict[str, Any]] = []

        for item in evaluations:
            latest = cls._latest_rule_event(rule_key=item["rule_key"])
            breached = bool(item["breached"])
            event = None

            if breached:
                if (
                    latest is None
                    or latest.status != SLAAutomationEventStatus.TRIGGERED
                ):
                    event = cls._create_event(
                        rule_key=item["rule_key"],
                        status=SLAAutomationEventStatus.TRIGGERED,
                        severity=item["severity"],
                        metric_value=float(item["metric_value"]),
                        threshold_value=float(item["threshold_value"]),
                        payload={
                            "recommended_action": item["recommended_action"],
                            "repeat": False,
                            "evaluated_at": now.isoformat(),
                            **item["extra"],
                        },
                    )
                elif cooldown > 0 and now - cls._latest_event_time(
                    latest,
                    fallback_now=now,
                ) >= timedelta(minutes=cooldown):
                    event = cls._create_event(
                        rule_key=item["rule_key"],
                        status=SLAAutomationEventStatus.TRIGGERED,
                        severity=item["severity"],
                        metric_value=float(item["metric_value"]),
                        threshold_value=float(item["threshold_value"]),
                        payload={
                            "recommended_action": item["recommended_action"],
                            "repeat": True,
                            "last_event_id": latest.id,
                            "evaluated_at": now.isoformat(),
                            **item["extra"],
                        },
                    )
            elif latest and latest.status == SLAAutomationEventStatus.TRIGGERED:
                event = cls._create_event(
                    rule_key=item["rule_key"],
                    status=SLAAutomationEventStatus.RESOLVED,
                    severity=item["severity"],
                    metric_value=float(item["metric_value"]),
                    threshold_value=float(item["threshold_value"]),
                    payload={
                        "recommended_action": "clear_escalation",
                        "resolved_from_event_id": latest.id,
                        "evaluated_at": now.isoformat(),
                        **item["extra"],
                    },
                )

            results.append(
                {
                    "rule_key": item["rule_key"],
                    "breached": breached,
                    "metric_value": float(item["metric_value"]),
                    "threshold_value": float(item["threshold_value"]),
                    "event_created": event is not None,
                    "event_id": event.id if event else None,
                    "event_status": event.status if event else None,
                }
            )

        return {
            "enabled": True,
            "metrics": metrics,
            "results": results,
        }
