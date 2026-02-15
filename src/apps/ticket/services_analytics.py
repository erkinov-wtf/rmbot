from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from account.models import User
from attendance.models import AttendanceRecord
from core.utils.constants import (
    InventoryItemStatus,
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
)
from gamification.models import XPLedger
from inventory.models import InventoryItem
from ticket.models import Ticket, TicketTransition
from ticket.services_stockout import StockoutIncidentService


class TicketAnalyticsService:
    """Aggregates fleet/team operational KPIs for analytics API payloads."""

    BUSINESS_TIMEZONE = ZoneInfo("Asia/Tashkent")
    QC_WINDOW_DAYS = 7

    @classmethod
    def fleet_summary(cls) -> dict[str, object]:
        now_utc = timezone.now()
        business_window = StockoutIncidentService.business_window_context(
            now_utc=now_utc
        )
        now_local = business_window["local_now"]

        inventory_items_qs = InventoryItem.domain.all()
        items_by_status = dict(
            inventory_items_qs.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

        active_fleet_qs = inventory_items_qs.filter(is_active=True).exclude(
            status=InventoryItemStatus.WRITE_OFF
        )
        active_count = active_fleet_qs.count()
        ready_count = active_fleet_qs.filter(status=InventoryItemStatus.READY).count()
        availability_pct = (
            round((ready_count / active_count) * 100, 2) if active_count else 0.0
        )

        active_tickets_qs = Ticket.domain.active_workflow()
        ticket_counts = dict(
            Ticket.domain.all()
            .values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        backlog_counts = {
            "green": active_tickets_qs.filter(flag_minutes__lte=30).count(),
            "yellow": active_tickets_qs.filter(
                flag_minutes__gte=31, flag_minutes__lte=60
            ).count(),
            "red": active_tickets_qs.filter(
                flag_minutes__gte=61, flag_minutes__lte=120
            ).count(),
            "black": active_tickets_qs.filter(
                flag_minutes__gte=121, flag_minutes__lte=180
            ).count(),
            "black_plus": active_tickets_qs.filter(flag_minutes__gt=180).count(),
        }
        backlog_total = sum(backlog_counts.values())
        active_status_counts = dict(
            active_tickets_qs.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

        business_window_now = bool(business_window["in_business_window"])
        stockout_now = business_window_now and ready_count == 0
        # KPI helpers keep the endpoint payload stable while internals evolve.
        backlog_kpis = cls._backlog_kpis(
            active_tickets_qs=active_tickets_qs,
            backlog_counts=backlog_counts,
            now_utc=now_utc,
        )
        sla_snapshot = cls._sla_snapshot(
            availability_pct=availability_pct,
            active_count=active_count,
            ready_count=ready_count,
            business_window_now=business_window_now,
            business_window_timezone=str(business_window["timezone"]),
            business_window_start_hour=int(business_window["start_hour"]),
            business_window_end_hour=int(business_window["end_hour"]),
            stockout_now=stockout_now,
            backlog_red_or_worse=backlog_kpis["red_or_worse_count"],
            backlog_black_or_worse=backlog_kpis["black_or_worse_count"],
        )
        qc_kpis = cls._qc_kpis(now_utc=now_utc, days=cls.QC_WINDOW_DAYS)
        stockout_incidents = StockoutIncidentService.rolling_stockout_summary(
            now_utc=now_utc,
            days=30,
        )

        return {
            "generated_at": now_utc.isoformat(),
            "local_time": now_local.isoformat(),
            "fleet": {
                "total": inventory_items_qs.count(),
                "active": active_count,
                "ready": ready_count,
                "in_service": items_by_status.get(InventoryItemStatus.IN_SERVICE, 0),
                "rented": items_by_status.get(InventoryItemStatus.RENTED, 0),
                "blocked": items_by_status.get(InventoryItemStatus.BLOCKED, 0),
                "write_off": items_by_status.get(InventoryItemStatus.WRITE_OFF, 0),
            },
            "tickets": {
                "active_total": active_tickets_qs.count(),
                "new": ticket_counts.get(TicketStatus.NEW, 0),
                "assigned": ticket_counts.get(TicketStatus.ASSIGNED, 0),
                "in_progress": ticket_counts.get(TicketStatus.IN_PROGRESS, 0),
                "waiting_qc": ticket_counts.get(TicketStatus.WAITING_QC, 0),
                "rework": ticket_counts.get(TicketStatus.REWORK, 0),
                "done": ticket_counts.get(TicketStatus.DONE, 0),
            },
            "backlog": {
                "total": backlog_total,
                "flag_buckets": backlog_counts,
                "status_buckets": {
                    "new": active_status_counts.get(TicketStatus.NEW, 0),
                    "assigned": active_status_counts.get(TicketStatus.ASSIGNED, 0),
                    "in_progress": active_status_counts.get(
                        TicketStatus.IN_PROGRESS, 0
                    ),
                    "waiting_qc": active_status_counts.get(TicketStatus.WAITING_QC, 0),
                    "rework": active_status_counts.get(TicketStatus.REWORK, 0),
                },
                "kpis": backlog_kpis,
            },
            "kpis": {
                "availability_percent": availability_pct,
                "stockout_now": stockout_now,
            },
            "sla": sla_snapshot,
            "qc": qc_kpis,
            "stockout_incidents": stockout_incidents,
        }

    @classmethod
    def team_summary(cls, *, days: int = 7) -> dict[str, object]:
        now = timezone.now()
        end_date = now.date()
        start_date = end_date - timedelta(days=max(1, days) - 1)

        technicians = list(
            User.objects.filter(
                deleted_at__isnull=True,
                is_active=True,
                roles__slug=RoleSlug.TECHNICIAN,
                roles__deleted_at__isnull=True,
            )
            .distinct()
            .order_by("id")
        )
        technician_ids = [user.id for user in technicians]

        if not technician_ids:
            return {
                "generated_at": now.isoformat(),
                "period": {
                    "days": days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "summary": {
                    "technicians_total": 0,
                    "tickets_done_total": 0,
                    "raw_xp_total": 0,
                    "attendance_days_total": 0,
                    "first_pass_rate_percent": 0.0,
                },
                "members": [],
            }

        tickets_done_qs = Ticket.domain.filter(
            technician_id__in=technician_ids,
            status=TicketStatus.DONE,
            done_at__date__gte=start_date,
            done_at__date__lte=end_date,
        )
        done_counts = dict(
            tickets_done_qs.values("technician_id")
            .annotate(total=Count("id"))
            .values_list("technician_id", "total")
        )
        done_records = list(tickets_done_qs.values("id", "technician_id"))
        done_ticket_ids = [row["id"] for row in done_records]

        qc_failed_ticket_ids = set()
        if done_ticket_ids:
            qc_failed_ticket_ids = set(
                TicketTransition.objects.filter(
                    ticket_id__in=done_ticket_ids,
                    action=TicketTransitionAction.QC_FAIL,
                )
                .values_list("ticket_id", flat=True)
                .distinct()
            )

        first_pass_counts: dict[int, int] = {}
        for row in done_records:
            technician_id = row["technician_id"]
            is_first_pass = row["id"] not in qc_failed_ticket_ids
            if is_first_pass:
                first_pass_counts[technician_id] = (
                    first_pass_counts.get(technician_id, 0) + 1
                )

        raw_xp_sums = dict(
            XPLedger.objects.filter(
                user_id__in=technician_ids,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
            .values("user_id")
            .annotate(total=Sum("amount"))
            .values_list("user_id", "total")
        )
        attendance_days = dict(
            AttendanceRecord.domain.filter(
                user_id__in=technician_ids,
                work_date__gte=start_date,
                work_date__lte=end_date,
                check_in_at__isnull=False,
            )
            .values("user_id")
            .annotate(total=Count("id"))
            .values_list("user_id", "total")
        )
        in_progress_counts = dict(
            Ticket.domain.filter(
                technician_id__in=technician_ids,
                status=TicketStatus.IN_PROGRESS,
            )
            .values("technician_id")
            .annotate(total=Count("id"))
            .values_list("technician_id", "total")
        )

        members = []
        total_done = 0
        total_first_pass = 0
        total_raw_xp = 0
        total_attendance_days = 0

        for technician in technicians:
            done_total = int(done_counts.get(technician.id, 0) or 0)
            first_pass_total = int(first_pass_counts.get(technician.id, 0) or 0)
            raw_xp_total = int(raw_xp_sums.get(technician.id, 0) or 0)
            attendance_total = int(attendance_days.get(technician.id, 0) or 0)
            in_progress_total = int(in_progress_counts.get(technician.id, 0) or 0)
            first_pass_rate = (
                round((first_pass_total / done_total) * 100, 2) if done_total else 0.0
            )

            total_done += done_total
            total_first_pass += first_pass_total
            total_raw_xp += raw_xp_total
            total_attendance_days += attendance_total

            full_name = (
                f"{technician.first_name or ''} {technician.last_name or ''}".strip()
            )
            members.append(
                {
                    "user_id": technician.id,
                    "name": full_name or technician.username,
                    "username": technician.username,
                    "level": int(technician.level),
                    "tickets_done": done_total,
                    "tickets_first_pass": first_pass_total,
                    "first_pass_rate_percent": first_pass_rate,
                    "raw_xp": raw_xp_total,
                    "attendance_days": attendance_total,
                    "in_progress_now": in_progress_total,
                }
            )

        members.sort(
            key=lambda item: (
                item["tickets_done"],
                item["raw_xp"],
                -item["user_id"],
            ),
            reverse=True,
        )
        first_pass_rate_total = (
            round((total_first_pass / total_done) * 100, 2) if total_done else 0.0
        )

        return {
            "generated_at": now.isoformat(),
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "technicians_total": len(technicians),
                "tickets_done_total": total_done,
                "raw_xp_total": total_raw_xp,
                "attendance_days_total": total_attendance_days,
                "first_pass_rate_percent": first_pass_rate_total,
            },
            "members": members,
        }

    @classmethod
    def _backlog_kpis(
        cls,
        *,
        active_tickets_qs,
        backlog_counts: dict[str, int],
        now_utc,
    ) -> dict[str, float | int]:
        total = int(active_tickets_qs.count())
        if total <= 0:
            return {
                "avg_flag_minutes": 0.0,
                "avg_age_minutes": 0.0,
                "red_or_worse_count": 0,
                "black_or_worse_count": 0,
            }

        total_flag_minutes = 0
        total_age_minutes = 0
        for created_at, flag_minutes in active_tickets_qs.values_list(
            "created_at",
            "flag_minutes",
        ):
            total_flag_minutes += int(flag_minutes or 0)
            ticket_age_minutes = max(
                int((now_utc - created_at).total_seconds() // 60),
                0,
            )
            total_age_minutes += ticket_age_minutes

        red_or_worse = (
            int(backlog_counts.get("red", 0))
            + int(backlog_counts.get("black", 0))
            + int(backlog_counts.get("black_plus", 0))
        )
        black_or_worse = int(backlog_counts.get("black", 0)) + int(
            backlog_counts.get("black_plus", 0)
        )

        return {
            "avg_flag_minutes": round(total_flag_minutes / total, 2),
            "avg_age_minutes": round(total_age_minutes / total, 2),
            "red_or_worse_count": red_or_worse,
            "black_or_worse_count": black_or_worse,
        }

    @classmethod
    def _sla_snapshot(
        cls,
        *,
        availability_pct: float,
        active_count: int,
        ready_count: int,
        business_window_now: bool,
        business_window_timezone: str,
        business_window_start_hour: int,
        business_window_end_hour: int,
        stockout_now: bool,
        backlog_red_or_worse: int,
        backlog_black_or_worse: int,
    ) -> dict[str, object]:
        return {
            "business_window": {
                "timezone": business_window_timezone,
                "start_hour": business_window_start_hour,
                "end_hour": business_window_end_hour,
                "in_window_now": business_window_now,
            },
            "availability": {
                "percent": availability_pct,
                "ready": ready_count,
                "active": active_count,
            },
            "stockout": {
                "is_now": stockout_now,
                "ready_count": ready_count,
            },
            "backlog_pressure": {
                "red_or_worse": backlog_red_or_worse,
                "black_or_worse": backlog_black_or_worse,
            },
        }

    @classmethod
    def _qc_kpis(cls, *, now_utc, days: int) -> dict[str, object]:
        window_days = max(1, int(days))
        end_date = now_utc.date()
        start_date = end_date - timedelta(days=window_days - 1)

        done_records = list(
            Ticket.domain.filter(
                status=TicketStatus.DONE,
                done_at__date__gte=start_date,
                done_at__date__lte=end_date,
            ).values("id", "done_at__date")
        )
        done_ticket_ids = [record["id"] for record in done_records]

        qc_failed_ticket_ids: set[int] = set()
        if done_ticket_ids:
            qc_failed_ticket_ids = set(
                TicketTransition.objects.filter(
                    ticket_id__in=done_ticket_ids,
                    action=TicketTransitionAction.QC_FAIL,
                )
                .values_list("ticket_id", flat=True)
                .distinct()
            )

        qc_event_rows = list(
            TicketTransition.objects.filter(
                action__in=[
                    TicketTransitionAction.QC_PASS,
                    TicketTransitionAction.QC_FAIL,
                ],
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
            .values("action", "created_at__date")
            .annotate(total=Count("id"))
        )

        done_by_date: dict[object, int] = defaultdict(int)
        first_pass_by_date: dict[object, int] = defaultdict(int)
        rework_by_date: dict[object, int] = defaultdict(int)
        first_pass_total = 0

        for record in done_records:
            ticket_id = int(record["id"])
            done_date = record["done_at__date"]
            done_by_date[done_date] += 1
            if ticket_id in qc_failed_ticket_ids:
                rework_by_date[done_date] += 1
                continue
            first_pass_total += 1
            first_pass_by_date[done_date] += 1

        qc_pass_by_date: dict[object, int] = defaultdict(int)
        qc_fail_by_date: dict[object, int] = defaultdict(int)
        qc_pass_total = 0
        qc_fail_total = 0
        for row in qc_event_rows:
            action = row["action"]
            event_date = row["created_at__date"]
            total = int(row["total"] or 0)
            if action == TicketTransitionAction.QC_PASS:
                qc_pass_by_date[event_date] += total
                qc_pass_total += total
            elif action == TicketTransitionAction.QC_FAIL:
                qc_fail_by_date[event_date] += total
                qc_fail_total += total

        done_total = len(done_records)
        rework_total = done_total - first_pass_total
        first_pass_rate_total = (
            round((first_pass_total / done_total) * 100, 2) if done_total else 0.0
        )

        trend: list[dict[str, object]] = []
        for idx in range(window_days):
            day = start_date + timedelta(days=idx)
            day_done_total = int(done_by_date.get(day, 0))
            day_first_pass = int(first_pass_by_date.get(day, 0))
            day_rework = int(rework_by_date.get(day, 0))
            trend.append(
                {
                    "date": day.isoformat(),
                    "done": day_done_total,
                    "first_pass_done": day_first_pass,
                    "rework_done": day_rework,
                    "first_pass_rate_percent": (
                        round((day_first_pass / day_done_total) * 100, 2)
                        if day_done_total
                        else 0.0
                    ),
                    "qc_pass_events": int(qc_pass_by_date.get(day, 0)),
                    "qc_fail_events": int(qc_fail_by_date.get(day, 0)),
                }
            )

        return {
            "window_days": window_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "totals": {
                "done": done_total,
                "first_pass_done": first_pass_total,
                "rework_done": rework_total,
                "first_pass_rate_percent": first_pass_rate_total,
                "qc_pass_events": qc_pass_total,
                "qc_fail_events": qc_fail_total,
            },
            "trend": trend,
        }
