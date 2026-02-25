from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from account.models import User
from attendance.models import AttendanceRecord
from core.utils.constants import (
    InventoryItemStatus,
    RoleSlug,
    TicketColor,
    TicketStatus,
    TicketTransitionAction,
)
from gamification.models import XPTransaction
from inventory.models import InventoryItem
from ticket.models import Ticket, TicketTransition


class TicketAnalyticsService:
    """Aggregates fleet/team operational KPIs for analytics API payloads."""

    BUSINESS_TIMEZONE = ZoneInfo("Asia/Tashkent")
    QC_WINDOW_DAYS = 7

    SCORE_WEIGHTS = {
        "tickets_done": 120,
        "xp_total": 1,
        "first_pass_done": 40,
        "green_flag_done": 20,
        "yellow_flag_done": 10,
        "red_flag_done_penalty": 8,
        "attendance_day": 6,
        "rework_done_penalty": 25,
        "qc_fail_event_penalty": 12,
    }

    @classmethod
    def fleet_summary(cls) -> dict[str, object]:
        now_utc = timezone.now()
        now_local = timezone.localtime(now_utc, cls.BUSINESS_TIMEZONE)

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
            "green": active_tickets_qs.filter(flag_color=TicketColor.GREEN).count(),
            "yellow": active_tickets_qs.filter(flag_color=TicketColor.YELLOW).count(),
            "red": active_tickets_qs.filter(flag_color=TicketColor.RED).count(),
        }
        backlog_total = sum(backlog_counts.values())
        active_status_counts = dict(
            active_tickets_qs.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

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
            backlog_red_or_worse=backlog_kpis["red_or_worse_count"],
            backlog_black_or_worse=backlog_kpis["black_or_worse_count"],
        )
        qc_kpis = cls._qc_kpis(now_utc=now_utc, days=cls.QC_WINDOW_DAYS)

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
                "under_review": ticket_counts.get(TicketStatus.UNDER_REVIEW, 0),
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
                    "under_review": active_status_counts.get(
                        TicketStatus.UNDER_REVIEW, 0
                    ),
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
            },
            "sla": sla_snapshot,
            "qc": qc_kpis,
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
            finished_at__date__gte=start_date,
            finished_at__date__lte=end_date,
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
            XPTransaction.objects.filter(
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
    def public_technician_leaderboard(
        cls,
        *,
        days: int | None = None,
        request=None,
        include_photo: bool = False,
    ) -> dict[str, object]:
        now = timezone.now()
        window_days = int(days) if days is not None else None
        start_date = None
        end_date = None
        period: dict[str, object] | None = None
        if window_days is not None:
            window_days = max(1, window_days)
            end_date = timezone.localdate()
            start_date = end_date - timedelta(days=window_days - 1)
            period = {
                "days": window_days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        technicians = cls._active_technicians()
        members = cls._public_leaderboard_members(
            technicians=technicians,
            start_date=start_date,
            end_date=end_date,
            request=request,
            include_photo=include_photo,
        )

        tickets_done_total = sum(int(item["tickets_done_total"]) for item in members)
        first_pass_total = sum(
            int(item["tickets_first_pass_total"]) for item in members
        )
        xp_total = sum(int(item["xp_total"]) for item in members)
        total_score = sum(int(item["score"]) for item in members)

        payload = {
            "generated_at": now.isoformat(),
            "summary": {
                "technicians_total": len(technicians),
                "tickets_done_total": tickets_done_total,
                "tickets_first_pass_total": first_pass_total,
                "first_pass_rate_percent": (
                    round((first_pass_total / tickets_done_total) * 100, 2)
                    if tickets_done_total
                    else 0.0
                ),
                "xp_total": xp_total,
                "total_score": total_score,
            },
            "members": members,
            "weights": {key: int(value) for key, value in cls.SCORE_WEIGHTS.items()},
        }
        if period is not None:
            payload["period"] = period
        return payload

    @classmethod
    def public_technician_detail(
        cls,
        *,
        user_id: int,
        request=None,
        include_photo: bool = False,
    ) -> dict[str, object]:
        leaderboard = cls.public_technician_leaderboard(
            request=request,
            include_photo=include_photo,
        )
        members = list(leaderboard.get("members", []))
        selected_member = next(
            (item for item in members if int(item.get("user_id", 0)) == int(user_id)),
            None,
        )
        if selected_member is None:
            raise ValueError("Technician was not found.")

        total_technicians = max(int(leaderboard["summary"]["technicians_total"]), 1)
        rank = int(selected_member["rank"])
        score = int(selected_member["score"])
        average_score = (
            round(int(leaderboard["summary"]["total_score"]) / total_technicians, 2)
            if total_technicians
            else 0.0
        )
        better_than_percent = (
            round(((total_technicians - rank) / (total_technicians - 1)) * 100, 2)
            if total_technicians > 1
            else 100.0
        )

        status_counts_raw = dict(
            Ticket.domain.filter(technician_id=user_id)
            .values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        status_counts = {
            TicketStatus.UNDER_REVIEW: int(
                status_counts_raw.get(TicketStatus.UNDER_REVIEW, 0) or 0
            ),
            TicketStatus.NEW: int(status_counts_raw.get(TicketStatus.NEW, 0) or 0),
            TicketStatus.ASSIGNED: int(
                status_counts_raw.get(TicketStatus.ASSIGNED, 0) or 0
            ),
            TicketStatus.IN_PROGRESS: int(
                status_counts_raw.get(TicketStatus.IN_PROGRESS, 0) or 0
            ),
            TicketStatus.WAITING_QC: int(
                status_counts_raw.get(TicketStatus.WAITING_QC, 0) or 0
            ),
            TicketStatus.REWORK: int(
                status_counts_raw.get(TicketStatus.REWORK, 0) or 0
            ),
            TicketStatus.DONE: int(status_counts_raw.get(TicketStatus.DONE, 0) or 0),
        }

        qc_event_counts_raw = dict(
            TicketTransition.objects.filter(
                ticket__technician_id=user_id,
                action__in=[
                    TicketTransitionAction.QC_PASS,
                    TicketTransitionAction.QC_FAIL,
                ],
            )
            .values("action")
            .annotate(total=Count("id"))
            .values_list("action", "total")
        )
        qc_pass_events_total = int(
            qc_event_counts_raw.get(TicketTransitionAction.QC_PASS, 0) or 0
        )
        qc_fail_events_total = int(
            qc_event_counts_raw.get(TicketTransitionAction.QC_FAIL, 0) or 0
        )

        xp_breakdown_rows = list(
            XPTransaction.objects.filter(user_id=user_id)
            .values("entry_type")
            .annotate(
                total_amount=Sum("amount"),
                total_count=Count("id"),
            )
            .order_by("-total_amount", "-total_count", "entry_type")
        )
        xp_by_entry_type = [
            {
                "entry_type": str(row["entry_type"]),
                "total_amount": int(row["total_amount"] or 0),
                "total_count": int(row["total_count"] or 0),
            }
            for row in xp_breakdown_rows
        ]
        recent_xp_rows = list(
            XPTransaction.objects.filter(user_id=user_id)
            .order_by("-created_at", "-id")
            .values(
                "id",
                "amount",
                "entry_type",
                "description",
                "reference",
                "payload",
                "created_at",
            )[:20]
        )
        recent_xp_transactions = [
            {
                "id": int(row["id"]),
                "amount": int(row["amount"] or 0),
                "entry_type": str(row["entry_type"]),
                "description": row["description"],
                "reference": str(row["reference"]),
                "payload": row["payload"] or {},
                "created_at": row["created_at"].isoformat(),
            }
            for row in recent_xp_rows
        ]

        attendance_rows = list(
            AttendanceRecord.domain.filter(
                user_id=user_id,
                check_in_at__isnull=False,
            )
            .values("work_date", "check_in_at", "check_out_at")
            .order_by("-work_date")[:366]
        )
        attendance_days_total = len(attendance_rows)
        attendance_completed_days = 0
        attendance_minutes_total = 0
        for row in attendance_rows:
            check_in_at = row.get("check_in_at")
            check_out_at = row.get("check_out_at")
            if check_in_at is None or check_out_at is None:
                continue
            attendance_completed_days += 1
            attendance_minutes_total += max(
                0, int((check_out_at - check_in_at).total_seconds() // 60)
            )
        average_attendance_minutes = (
            round(attendance_minutes_total / attendance_completed_days, 2)
            if attendance_completed_days
            else 0.0
        )

        recent_done_ticket_rows = list(
            Ticket.domain.filter(technician_id=user_id, status=TicketStatus.DONE)
            .order_by("-finished_at", "-id")
            .values(
                "id",
                "title",
                "finished_at",
                "total_duration",
                "flag_color",
                "xp_amount",
                "is_manual",
            )[:20]
        )
        recent_done_tickets = [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "finished_at": (
                    row["finished_at"].isoformat() if row.get("finished_at") else None
                ),
                "total_duration": int(row["total_duration"] or 0),
                "flag_color": str(row["flag_color"]),
                "xp_amount": int(row["xp_amount"] or 0),
                "is_manual": bool(row["is_manual"]),
            }
            for row in recent_done_ticket_rows
        ]

        components = selected_member["score_components"]
        component_labels = {
            "tickets_done_points": "Closed tickets",
            "xp_total_points": "XP total",
            "first_pass_points": "First-pass completions",
            "quality_points": "Quality flags",
            "attendance_points": "Attendance consistency",
            "rework_penalty_points": "Rework / QC fail penalty",
        }
        contribution_items = [
            {
                "key": str(key),
                "label": component_labels.get(str(key), str(key)),
                "points": int(value or 0),
                "is_positive": int(value or 0) >= 0,
            }
            for key, value in components.items()
        ]
        contribution_items.sort(
            key=lambda item: abs(int(item["points"])),
            reverse=True,
        )
        top_positive_factors = [
            item for item in contribution_items if item["points"] > 0
        ][:3]
        top_negative_factors = [
            item for item in contribution_items if item["points"] < 0
        ][:3]

        return {
            "generated_at": leaderboard["generated_at"],
            "leaderboard_position": {
                "rank": rank,
                "total_technicians": total_technicians,
                "better_than_percent": better_than_percent,
                "score": score,
                "average_score": average_score,
            },
            "profile": {
                "user_id": int(selected_member["user_id"]),
                "name": str(selected_member["name"]),
                "username": str(selected_member["username"]),
                "level": int(selected_member["level"]),
                "has_photo": bool(selected_member.get("has_photo", False)),
                "photo_url": selected_member.get("photo_url"),
            },
            "score_breakdown": {
                "components": {
                    key: int(value or 0)
                    for key, value in components.items()
                },
                "contribution_items": contribution_items,
                "reasoning": {
                    "top_positive_factors": top_positive_factors,
                    "top_negative_factors": top_negative_factors,
                },
            },
            "metrics": {
                "tickets": {
                    "tickets_done_total": int(selected_member["tickets_done_total"]),
                    "tickets_first_pass_total": int(
                        selected_member["tickets_first_pass_total"]
                    ),
                    "tickets_rework_total": int(
                        selected_member["tickets_rework_total"]
                    ),
                    "first_pass_rate_percent": float(
                        selected_member["first_pass_rate_percent"]
                    ),
                    "tickets_closed_by_flag": {
                        "green": int(
                            selected_member["tickets_closed_by_flag"]["green"]
                        ),
                        "yellow": int(
                            selected_member["tickets_closed_by_flag"]["yellow"]
                        ),
                        "red": int(selected_member["tickets_closed_by_flag"]["red"]),
                    },
                    "average_resolution_minutes": float(
                        selected_member["average_resolution_minutes"]
                    ),
                    "status_counts": status_counts,
                    "qc_pass_events_total": qc_pass_events_total,
                    "qc_fail_events_total": qc_fail_events_total,
                },
                "xp": {
                    "xp_total": int(selected_member["xp_total"]),
                    "entry_type_breakdown": xp_by_entry_type,
                },
                "attendance": {
                    "attendance_days_total": int(
                        selected_member["attendance_days_total"]
                    ),
                    "attendance_completed_days": attendance_completed_days,
                    "average_work_minutes_per_day": average_attendance_minutes,
                },
            },
            "recent": {
                "done_tickets": recent_done_tickets,
                "xp_transactions": recent_xp_transactions,
            },
        }

    @classmethod
    def _active_technicians(cls) -> list[User]:
        return list(
            User.objects.filter(
                deleted_at__isnull=True,
                is_active=True,
                roles__slug=RoleSlug.TECHNICIAN,
                roles__deleted_at__isnull=True,
            )
            .distinct()
            .order_by("id")
        )

    @classmethod
    def _public_leaderboard_members(
        cls,
        *,
        technicians: list[User],
        start_date: date | None = None,
        end_date: date | None = None,
        request=None,
        include_photo: bool = False,
    ) -> list[dict[str, object]]:
        technician_ids = [int(user.id) for user in technicians]
        if not technician_ids:
            return []

        has_window = start_date is not None and end_date is not None

        done_ticket_qs = Ticket.domain.filter(
            technician_id__in=technician_ids,
            status=TicketStatus.DONE,
        )
        if has_window:
            done_ticket_qs = done_ticket_qs.filter(
                finished_at__date__gte=start_date,
                finished_at__date__lte=end_date,
            )
        done_ticket_rows = list(
            done_ticket_qs.values(
                "id",
                "technician_id",
                "flag_color",
                "total_duration",
            )
        )
        done_ticket_ids = [int(row["id"]) for row in done_ticket_rows]
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

        done_counts: dict[int, int] = defaultdict(int)
        first_pass_counts: dict[int, int] = defaultdict(int)
        rework_done_counts: dict[int, int] = defaultdict(int)
        duration_sums: dict[int, int] = defaultdict(int)
        flag_counts: dict[int, dict[str, int]] = defaultdict(
            lambda: {
                "green": 0,
                "yellow": 0,
                "red": 0,
            }
        )

        for row in done_ticket_rows:
            technician_id = int(row["technician_id"])
            ticket_id = int(row["id"])
            done_counts[technician_id] += 1
            duration_sums[technician_id] += int(row["total_duration"] or 0)

            flag_color = str(row.get("flag_color") or TicketColor.GREEN)
            if flag_color in ("green", "yellow", "red"):
                flag_counts[technician_id][flag_color] += 1

            if ticket_id in qc_failed_ticket_ids:
                rework_done_counts[technician_id] += 1
            else:
                first_pass_counts[technician_id] += 1

        qc_fail_event_qs = TicketTransition.objects.filter(
            ticket__technician_id__in=technician_ids,
            action=TicketTransitionAction.QC_FAIL,
        )
        if has_window:
            qc_fail_event_qs = qc_fail_event_qs.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
        qc_fail_event_counts = dict(
            qc_fail_event_qs
            .values("ticket__technician_id")
            .annotate(total=Count("id"))
            .values_list("ticket__technician_id", "total")
        )

        xp_qs = XPTransaction.objects.filter(user_id__in=technician_ids)
        if has_window:
            xp_qs = xp_qs.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
            )
        xp_totals = dict(
            xp_qs
            .values("user_id")
            .annotate(total=Sum("amount"))
            .values_list("user_id", "total")
        )
        attendance_qs = AttendanceRecord.domain.filter(
            user_id__in=technician_ids,
            check_in_at__isnull=False,
        )
        if has_window:
            attendance_qs = attendance_qs.filter(
                work_date__gte=start_date,
                work_date__lte=end_date,
            )
        attendance_totals = dict(
            attendance_qs
            .values("user_id")
            .annotate(total=Count("id"))
            .values_list("user_id", "total")
        )

        members: list[dict[str, object]] = []
        for user in technicians:
            user_id = int(user.id)
            done_total = int(done_counts.get(user_id, 0) or 0)
            first_pass_total = int(first_pass_counts.get(user_id, 0) or 0)
            rework_done_total = int(rework_done_counts.get(user_id, 0) or 0)
            qc_fail_events_total = int(qc_fail_event_counts.get(user_id, 0) or 0)
            xp_total = int(xp_totals.get(user_id, 0) or 0)
            attendance_total = int(attendance_totals.get(user_id, 0) or 0)
            flags = flag_counts[user_id]
            average_resolution_minutes = (
                round(duration_sums[user_id] / done_total, 2) if done_total else 0.0
            )
            first_pass_rate_percent = (
                round((first_pass_total / done_total) * 100, 2) if done_total else 0.0
            )

            tickets_done_points = done_total * cls.SCORE_WEIGHTS["tickets_done"]
            xp_total_points = xp_total * cls.SCORE_WEIGHTS["xp_total"]
            first_pass_points = (
                first_pass_total * cls.SCORE_WEIGHTS["first_pass_done"]
            )
            quality_points = (
                int(flags["green"]) * cls.SCORE_WEIGHTS["green_flag_done"]
                + int(flags["yellow"]) * cls.SCORE_WEIGHTS["yellow_flag_done"]
                - int(flags["red"]) * cls.SCORE_WEIGHTS["red_flag_done_penalty"]
            )
            attendance_points = (
                attendance_total * cls.SCORE_WEIGHTS["attendance_day"]
            )
            rework_penalty_points = -(
                rework_done_total * cls.SCORE_WEIGHTS["rework_done_penalty"]
                + qc_fail_events_total * cls.SCORE_WEIGHTS["qc_fail_event_penalty"]
            )
            score = (
                tickets_done_points
                + xp_total_points
                + first_pass_points
                + quality_points
                + attendance_points
                + rework_penalty_points
            )

            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            members.append(
                {
                    "user_id": user_id,
                    "name": full_name or user.username,
                    "username": user.username,
                    "level": int(user.level),
                    "has_photo": cls._has_public_photo(user=user),
                    "photo_url": (
                        cls._resolve_public_photo_url(user=user, request=request)
                        if include_photo
                        else None
                    ),
                    "score": int(score),
                    "score_components": {
                        "tickets_done_points": int(tickets_done_points),
                        "xp_total_points": int(xp_total_points),
                        "first_pass_points": int(first_pass_points),
                        "quality_points": int(quality_points),
                        "attendance_points": int(attendance_points),
                        "rework_penalty_points": int(rework_penalty_points),
                    },
                    "tickets_done_total": done_total,
                    "tickets_first_pass_total": first_pass_total,
                    "tickets_rework_total": rework_done_total,
                    "first_pass_rate_percent": first_pass_rate_percent,
                    "tickets_closed_by_flag": {
                        "green": int(flags["green"]),
                        "yellow": int(flags["yellow"]),
                        "red": int(flags["red"]),
                    },
                    "xp_total": xp_total,
                    "attendance_days_total": attendance_total,
                    "average_resolution_minutes": average_resolution_minutes,
                    "qc_fail_events_total": qc_fail_events_total,
                }
            )

        members.sort(
            key=lambda item: (
                int(item["score"]),
                int(item["tickets_done_total"]),
                int(item["tickets_first_pass_total"]),
                int(item["xp_total"]),
                -int(item["user_id"]),
            ),
            reverse=True,
        )
        for index, row in enumerate(members, start=1):
            row["rank"] = index
        return members

    @classmethod
    def public_technician_photo(cls, *, user_id: int, request=None) -> dict[str, object]:
        user = (
            User.objects.filter(
                id=user_id,
                deleted_at__isnull=True,
                is_active=True,
                roles__slug=RoleSlug.TECHNICIAN,
                roles__deleted_at__isnull=True,
            )
            .distinct()
            .first()
        )
        if user is None:
            raise ValueError("Technician was not found.")

        has_photo = cls._has_public_photo(user=user)
        return {
            "user_id": int(user.id),
            "has_photo": has_photo,
            "photo_url": (
                cls._resolve_public_photo_url(user=user, request=request)
                if has_photo
                else None
            ),
        }

    @staticmethod
    def _resolve_public_photo_url(*, user: User, request=None) -> str | None:
        return user.resolve_public_photo_url(request=request)

    @staticmethod
    def _has_public_photo(*, user: User) -> bool:
        return bool(user.public_photo_blob) or bool(user.public_photo)

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

        red_or_worse = int(backlog_counts.get("red", 0))
        black_or_worse = red_or_worse

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
        backlog_red_or_worse: int,
        backlog_black_or_worse: int,
    ) -> dict[str, object]:
        return {
            "availability": {
                "percent": availability_pct,
                "ready": ready_count,
                "active": active_count,
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
                finished_at__date__gte=start_date,
                finished_at__date__lte=end_date,
            ).values("id", "finished_at__date")
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
            done_date = record["finished_at__date"]
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
