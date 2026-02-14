from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from bike.models import Bike
from core.utils.constants import TicketStatus, TicketTransitionAction
from rules.services import RulesService
from ticket.models import StockoutIncident, Ticket, TicketTransition


class StockoutIncidentService:
    """Detects stockout incidents in rules-defined business time windows."""

    DEFAULT_TIMEZONE = "Asia/Tashkent"
    DEFAULT_BUSINESS_START_HOUR = 10
    DEFAULT_BUSINESS_END_HOUR = 20
    DEFAULT_WORKING_WEEKDAYS = (1, 2, 3, 4, 5, 6)

    @classmethod
    def _stockout_config(cls) -> dict[str, object]:
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

        working_weekdays_raw = stockout_rules.get(
            "working_weekdays",
            cls.DEFAULT_WORKING_WEEKDAYS,
        )
        parsed_weekdays: set[int] = set()
        if isinstance(working_weekdays_raw, list):
            for raw_day in working_weekdays_raw:
                try:
                    day = int(raw_day)
                except (TypeError, ValueError):
                    continue
                if 1 <= day <= 7:
                    parsed_weekdays.add(day)
        if not parsed_weekdays:
            parsed_weekdays = set(cls.DEFAULT_WORKING_WEEKDAYS)
        working_weekdays = sorted(parsed_weekdays)

        holiday_dates_raw = stockout_rules.get("holiday_dates", [])
        parsed_holidays: set[date] = set()
        if isinstance(holiday_dates_raw, list):
            for raw_date in holiday_dates_raw:
                if not isinstance(raw_date, str):
                    continue
                try:
                    parsed_holidays.add(date.fromisoformat(raw_date.strip()))
                except ValueError:
                    continue

        return {
            "timezone": business_tz,
            "start_hour": start_hour,
            "end_hour": end_hour,
            "working_weekdays": working_weekdays,
            "holiday_dates": parsed_holidays,
        }

    @classmethod
    def business_window_context(cls, *, now_utc=None) -> dict[str, object]:
        now = now_utc or timezone.now()
        config = cls._stockout_config()
        business_tz = config["timezone"]
        start_hour = int(config["start_hour"])
        end_hour = int(config["end_hour"])
        working_weekdays = list(config["working_weekdays"])
        holiday_dates = set(config["holiday_dates"])
        local_now = now.astimezone(business_tz)
        local_date = local_now.date()
        local_iso_weekday = local_now.isoweekday()
        is_working_weekday = local_iso_weekday in working_weekdays
        is_holiday = local_date in holiday_dates
        is_business_day = is_working_weekday and not is_holiday
        in_business_hours = start_hour <= local_now.hour < end_hour
        in_business_window = is_business_day and in_business_hours
        # Context payload is reused by detector, analytics, and SLA services.
        return {
            "timezone": getattr(business_tz, "key", cls.DEFAULT_TIMEZONE),
            "start_hour": start_hour,
            "end_hour": end_hour,
            "working_weekdays": working_weekdays,
            "holiday_dates": sorted(day.isoformat() for day in holiday_dates),
            "local_iso_weekday": local_iso_weekday,
            "is_working_weekday": is_working_weekday,
            "is_holiday": is_holiday,
            "is_business_day": is_business_day,
            "in_business_hours": in_business_hours,
            "in_business_window": in_business_window,
            "local_now": local_now,
        }

    @staticmethod
    def _ready_active_bike_count() -> int:
        return Bike.domain.ready_active_count()

    @classmethod
    @transaction.atomic
    def detect_and_sync(cls, *, now_utc=None) -> dict[str, object]:
        now = now_utc or timezone.now()
        window_context = cls.business_window_context(now_utc=now)
        in_business_window = bool(window_context["in_business_window"])
        ready_count = cls._ready_active_bike_count()

        active_incident = StockoutIncident.domain.latest_active_for_update()

        if in_business_window and ready_count == 0:
            if active_incident:
                return {
                    "action": "no_change_active",
                    "incident_id": active_incident.id,
                    "ready_count": ready_count,
                    "in_business_window": in_business_window,
                }

            incident = StockoutIncident.start_incident(
                started_at=now,
                ready_count_at_start=ready_count,
                window_context=window_context,
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

        overlap_minutes = active_incident.resolve(
            ended_at=now,
            ready_count_at_end=ready_count,
        )
        return {
            "action": "resolved",
            "incident_id": active_incident.id,
            "ready_count": ready_count,
            "in_business_window": in_business_window,
            "duration_minutes": overlap_minutes,
        }

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
            StockoutIncident.domain.list_overlapping_window(
                start_dt=start_dt,
                end_dt=end_dt,
            )
        )
        total_minutes = sum(
            incident.overlap_minutes(start_dt=start_dt, end_dt=end_dt, now_utc=now)
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
        open_incident = StockoutIncident.domain.latest_active()
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
