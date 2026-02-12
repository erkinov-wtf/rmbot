from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from bike.models import Bike
from core.utils.constants import BikeStatus, TicketStatus, TicketTransitionAction
from rules.services import RulesService
from ticket.models import StockoutIncident, Ticket, TicketTransition


class StockoutIncidentService:
    DEFAULT_TIMEZONE = "Asia/Tashkent"
    DEFAULT_BUSINESS_START_HOUR = 10
    DEFAULT_BUSINESS_END_HOUR = 20

    @classmethod
    def _stockout_config(cls) -> tuple[ZoneInfo, int, int]:
        sla_rules = RulesService.get_active_rules_config().get("sla", {})
        stockout_rules = sla_rules.get("stockout", {})

        timezone_name = stockout_rules.get("timezone", cls.DEFAULT_TIMEZONE)
        try:
            business_tz = ZoneInfo(str(timezone_name))
        except Exception:
            business_tz = ZoneInfo(cls.DEFAULT_TIMEZONE)

        try:
            start_hour = int(
                stockout_rules.get(
                    "business_start_hour",
                    cls.DEFAULT_BUSINESS_START_HOUR,
                )
            )
        except (TypeError, ValueError):
            start_hour = cls.DEFAULT_BUSINESS_START_HOUR
        try:
            end_hour = int(
                stockout_rules.get(
                    "business_end_hour",
                    cls.DEFAULT_BUSINESS_END_HOUR,
                )
            )
        except (TypeError, ValueError):
            end_hour = cls.DEFAULT_BUSINESS_END_HOUR

        start_hour = max(0, min(23, start_hour))
        end_hour = max(1, min(24, end_hour))
        if start_hour >= end_hour:
            start_hour = cls.DEFAULT_BUSINESS_START_HOUR
            end_hour = cls.DEFAULT_BUSINESS_END_HOUR

        return business_tz, start_hour, end_hour

    @classmethod
    def business_window_context(cls, *, now_utc=None) -> dict[str, object]:
        now = now_utc or timezone.now()
        business_tz, start_hour, end_hour = cls._stockout_config()
        local_now = now.astimezone(business_tz)
        return {
            "timezone": getattr(business_tz, "key", cls.DEFAULT_TIMEZONE),
            "start_hour": start_hour,
            "end_hour": end_hour,
            "in_business_window": start_hour <= local_now.hour < end_hour,
            "local_now": local_now,
        }

    @staticmethod
    def _ready_active_bike_count() -> int:
        return (
            Bike.objects.filter(deleted_at__isnull=True, is_active=True)
            .exclude(status=BikeStatus.WRITE_OFF)
            .filter(status=BikeStatus.READY)
            .count()
        )

    @classmethod
    @transaction.atomic
    def detect_and_sync(cls, *, now_utc=None) -> dict[str, object]:
        now = now_utc or timezone.now()
        window_context = cls.business_window_context(now_utc=now)
        in_business_window = bool(window_context["in_business_window"])
        ready_count = cls._ready_active_bike_count()

        active_incident = (
            StockoutIncident.objects.select_for_update()
            .filter(is_active=True)
            .order_by("-started_at")
            .first()
        )

        if in_business_window and ready_count == 0:
            if active_incident:
                return {
                    "action": "no_change_active",
                    "incident_id": active_incident.id,
                    "ready_count": ready_count,
                    "in_business_window": in_business_window,
                }

            incident = StockoutIncident.objects.create(
                started_at=now,
                is_active=True,
                ready_count_at_start=ready_count,
                payload={
                    "timezone": window_context["timezone"],
                    "business_start_hour": window_context["start_hour"],
                    "business_end_hour": window_context["end_hour"],
                },
            )
            return {
                "action": "started",
                "incident_id": incident.id,
                "ready_count": ready_count,
                "in_business_window": in_business_window,
            }

        if not active_incident:
            return {
                "action": "no_change_idle",
                "incident_id": None,
                "ready_count": ready_count,
                "in_business_window": in_business_window,
            }

        overlap_minutes = max(
            int((now - active_incident.started_at).total_seconds() // 60),
            0,
        )
        active_incident.ended_at = now
        active_incident.is_active = False
        active_incident.ready_count_at_end = ready_count
        active_incident.duration_minutes = overlap_minutes
        active_incident.save(
            update_fields=[
                "ended_at",
                "is_active",
                "ready_count_at_end",
                "duration_minutes",
                "updated_at",
            ]
        )
        return {
            "action": "resolved",
            "incident_id": active_incident.id,
            "ready_count": ready_count,
            "in_business_window": in_business_window,
            "duration_minutes": overlap_minutes,
        }

    @classmethod
    def _incident_overlap_minutes(cls, *, incident, start_dt, end_dt, now_utc) -> int:
        effective_end = incident.ended_at or now_utc
        overlap_start = max(incident.started_at, start_dt)
        overlap_end = min(effective_end, end_dt)
        if overlap_end <= overlap_start:
            return 0
        return max(int((overlap_end - overlap_start).total_seconds() // 60), 0)

    @classmethod
    def stockout_window_summary(
        cls,
        *,
        start_dt,
        end_dt,
        now_utc=None,
    ) -> dict[str, int]:
        now = now_utc or timezone.now()
        incidents = list(
            StockoutIncident.objects.filter(started_at__lt=end_dt).filter(
                Q(ended_at__isnull=True) | Q(ended_at__gt=start_dt)
            )
        )
        total_minutes = sum(
            cls._incident_overlap_minutes(
                incident=incident,
                start_dt=start_dt,
                end_dt=end_dt,
                now_utc=now,
            )
            for incident in incidents
        )
        return {
            "incidents": len(incidents),
            "minutes": total_minutes,
        }

    @classmethod
    def monthly_sla_snapshot(
        cls, *, month_start_dt, next_month_start_dt
    ) -> dict[str, object]:
        now = timezone.now()
        stockout_summary = cls.stockout_window_summary(
            start_dt=month_start_dt,
            end_dt=next_month_start_dt,
            now_utc=now,
        )

        done_ticket_ids = list(
            Ticket.objects.filter(
                deleted_at__isnull=True,
                status=TicketStatus.DONE,
                done_at__gte=month_start_dt,
                done_at__lt=next_month_start_dt,
            ).values_list("id", flat=True)
        )
        done_total = len(done_ticket_ids)
        qc_fail_ticket_ids = set()
        if done_ticket_ids:
            qc_fail_ticket_ids = set(
                TicketTransition.objects.filter(
                    ticket_id__in=done_ticket_ids,
                    action=TicketTransitionAction.QC_FAIL,
                )
                .values_list("ticket_id", flat=True)
                .distinct()
            )
        first_pass_done = max(done_total - len(qc_fail_ticket_ids), 0)
        first_pass_rate_percent = (
            round((first_pass_done / done_total) * 100, 2) if done_total else 0.0
        )

        return {
            "qc": {
                "done": done_total,
                "first_pass_done": first_pass_done,
                "first_pass_rate_percent": first_pass_rate_percent,
            },
            "stockout": stockout_summary,
        }

    @classmethod
    def rolling_stockout_summary(
        cls, *, now_utc=None, days: int = 30
    ) -> dict[str, object]:
        now = now_utc or timezone.now()
        window_days = max(1, int(days))
        window_start = now - timedelta(days=window_days)
        summary = cls.stockout_window_summary(
            start_dt=window_start,
            end_dt=now,
            now_utc=now,
        )
        open_incident = (
            StockoutIncident.objects.filter(is_active=True)
            .order_by("-started_at")
            .first()
        )
        return {
            "window_days": window_days,
            "window_start": window_start.isoformat(),
            "window_end": now.isoformat(),
            "incidents": summary["incidents"],
            "minutes": summary["minutes"],
            "open_incident": (
                {
                    "id": open_incident.id,
                    "started_at": open_incident.started_at.isoformat(),
                    "ready_count_at_start": open_incident.ready_count_at_start,
                }
                if open_incident
                else None
            ),
        }
