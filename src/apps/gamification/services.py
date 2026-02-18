from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from account.models import User
from core.api.exceptions import DomainValidationError
from core.services.notifications import UserNotificationService
from core.utils.constants import EmployeeLevel, RoleSlug, XPTransactionEntryType
from gamification.models import (
    LevelUpCouponEvent,
    UserLevelHistoryEvent,
    UserLevelHistorySource,
    WeeklyLevelEvaluation,
    XPTransaction,
)
from rules.services import RulesService


class GamificationService:
    """Append-only XP transaction writer with idempotent reference handling."""

    @staticmethod
    def append_xp_entry(
        *,
        user_id: int,
        amount: int,
        entry_type: str,
        reference: str,
        description: str | None = None,
        payload: dict | None = None,
    ) -> tuple[XPTransaction, bool]:
        return XPTransaction.objects.append_entry(
            user_id=user_id,
            amount=amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            payload=payload,
        )

    @classmethod
    @transaction.atomic
    def adjust_user_xp(
        cls,
        *,
        actor_user_id: int,
        target_user_id: int,
        amount: int,
        comment: str,
    ) -> XPTransaction:
        normalized_amount = int(amount)
        if normalized_amount == 0:
            raise DomainValidationError("amount must not be 0.")

        normalized_comment = str(comment).strip()
        if not normalized_comment:
            raise DomainValidationError("comment is required.")

        if not User.objects.filter(id=target_user_id).exists():
            raise DomainValidationError("Target user was not found.")

        reference = f"manual_adjustment:{target_user_id}:{uuid4().hex}"
        description = "Manual XP adjustment"
        payload = {
            "actor_user_id": int(actor_user_id),
            "comment": normalized_comment,
        }

        entry, _ = cls.append_xp_entry(
            user_id=target_user_id,
            amount=normalized_amount,
            entry_type=XPTransactionEntryType.MANUAL_ADJUSTMENT,
            reference=reference,
            description=description,
            payload=payload,
        )

        UserNotificationService.notify_manual_xp_adjustment(
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            amount=normalized_amount,
            comment=normalized_comment,
        )
        return entry


class ProgressionService:
    """Weekly progression evaluator and level-control service."""

    BUSINESS_TZ = ZoneInfo("Asia/Tashkent")

    @staticmethod
    def _normalize_level(level: int | None) -> int:
        if level in EmployeeLevel.values:
            return int(level)
        return int(EmployeeLevel.L1)

    @staticmethod
    def _default_level_thresholds() -> dict[int, int]:
        return {
            int(EmployeeLevel.L1): 0,
            int(EmployeeLevel.L2): 200,
            int(EmployeeLevel.L3): 450,
            int(EmployeeLevel.L4): 750,
            int(EmployeeLevel.L5): 1100,
        }

    @staticmethod
    def parse_date_token(value: str, *, field_name: str) -> date:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc
        return date(parsed.year, parsed.month, parsed.day)

    @staticmethod
    def parse_week_start_token(week_start_token: str) -> date:
        week_start = ProgressionService.parse_date_token(
            week_start_token,
            field_name="week_start",
        )
        if week_start.weekday() != 0:
            raise ValueError("week_start must be a Monday date.")
        return week_start

    @classmethod
    def default_previous_week_start(cls) -> date:
        local_today = timezone.now().astimezone(cls.BUSINESS_TZ).date()
        current_week_start = local_today - timedelta(days=local_today.weekday())
        return current_week_start - timedelta(days=7)

    @classmethod
    def default_last_7_day_range(cls) -> tuple[date, date]:
        local_today = timezone.now().astimezone(cls.BUSINESS_TZ).date()
        return local_today - timedelta(days=6), local_today

    @classmethod
    def _week_bounds(cls, week_start: date) -> tuple[date, date, datetime, datetime]:
        if week_start.weekday() != 0:
            raise ValueError("week_start must be a Monday date.")
        week_end = week_start + timedelta(days=6)
        return cls._date_range_bounds(date_from=week_start, date_to=week_end)[:4]

    @classmethod
    def _date_range_bounds(
        cls,
        *,
        date_from: date,
        date_to: date,
    ) -> tuple[date, date, datetime, datetime, int]:
        if date_from > date_to:
            raise ValueError("date_from must be less than or equal to date_to.")

        range_days = (date_to - date_from).days + 1
        if range_days > 366:
            raise ValueError("Date range cannot exceed 366 days.")

        start_dt = timezone.make_aware(
            datetime.combine(date_from, time.min),
            cls.BUSINESS_TZ,
        )
        end_exclusive_dt = timezone.make_aware(
            datetime.combine(date_to + timedelta(days=1), time.min),
            cls.BUSINESS_TZ,
        )
        return date_from, date_to, start_dt, end_exclusive_dt, range_days

    @classmethod
    def _progression_rules_from_active_config(
        cls,
    ) -> tuple[dict[int, int], int, int, dict]:
        state = RulesService.get_active_rules_state()
        config = state.active_version.config
        progression_rules = config.get("progression", {})

        default_thresholds = cls._default_level_thresholds()
        thresholds_raw = progression_rules.get("level_thresholds", {})
        normalized_thresholds: dict[int, int] = {}
        last_threshold = 0
        for level in EmployeeLevel.values:
            level_int = int(level)
            raw_threshold = None
            if isinstance(thresholds_raw, dict):
                raw_threshold = thresholds_raw.get(
                    str(level_int), thresholds_raw.get(level_int)
                )
            try:
                parsed_threshold = int(raw_threshold)
            except (TypeError, ValueError):
                parsed_threshold = default_thresholds[level_int]
            parsed_threshold = max(0, parsed_threshold)
            if level_int == int(EmployeeLevel.L1):
                parsed_threshold = 0
            if parsed_threshold < last_threshold:
                parsed_threshold = last_threshold
            normalized_thresholds[level_int] = parsed_threshold
            last_threshold = parsed_threshold

        coupon_amount_raw = progression_rules.get("weekly_coupon_amount", 100_000)
        try:
            coupon_amount = int(coupon_amount_raw)
        except (TypeError, ValueError):
            coupon_amount = 100_000
        coupon_amount = max(0, coupon_amount)

        weekly_target_xp_raw = progression_rules.get("weekly_target_xp", 100)
        try:
            weekly_target_xp = int(weekly_target_xp_raw)
        except (TypeError, ValueError):
            weekly_target_xp = 100
        weekly_target_xp = max(0, weekly_target_xp)

        rules_snapshot = {
            "version": state.active_version.version,
            "cache_key": state.cache_key,
        }
        return normalized_thresholds, coupon_amount, weekly_target_xp, rules_snapshot

    @staticmethod
    def _warning_active_from_evaluation(
        evaluation: WeeklyLevelEvaluation | None,
    ) -> bool:
        if not evaluation:
            return False
        payload = evaluation.payload if isinstance(evaluation.payload, dict) else {}
        if "warning_active_after" in payload:
            return bool(payload.get("warning_active_after"))
        return str(payload.get("target_status", "")) == "warning"

    @staticmethod
    def _warning_active_from_history_event(
        event: UserLevelHistoryEvent | None,
    ) -> bool:
        if not event:
            return False
        return bool(event.warning_active_after)

    @classmethod
    def _latest_previous_evaluation_by_user(
        cls, *, user_ids: list[int], week_start: date
    ) -> dict[int, WeeklyLevelEvaluation]:
        rows = (
            WeeklyLevelEvaluation.objects.filter(
                user_id__in=user_ids,
                week_start__lt=week_start,
            )
            .order_by("user_id", "-week_start", "-id")
            .only("id", "user_id", "week_start", "payload")
        )
        latest: dict[int, WeeklyLevelEvaluation] = {}
        for row in rows:
            if row.user_id not in latest:
                latest[row.user_id] = row
        return latest

    @classmethod
    def _latest_level_history_by_user(
        cls,
        *,
        user_ids: list[int],
        created_before: datetime | None = None,
    ) -> dict[int, UserLevelHistoryEvent]:
        qs = UserLevelHistoryEvent.objects.select_related("actor").filter(
            user_id__in=user_ids
        )
        if created_before is not None:
            qs = qs.filter(created_at__lt=created_before)
        rows = qs.order_by("user_id", "-created_at", "-id")

        latest: dict[int, UserLevelHistoryEvent] = {}
        for row in rows:
            if row.user_id not in latest:
                latest[row.user_id] = row
        return latest

    @classmethod
    def _latest_level_history_for_user(
        cls,
        *,
        user_id: int,
        created_before: datetime | None = None,
    ) -> UserLevelHistoryEvent | None:
        qs = UserLevelHistoryEvent.objects.select_related("actor").filter(user_id=user_id)
        if created_before is not None:
            qs = qs.filter(created_at__lt=created_before)
        return qs.order_by("-created_at", "-id").first()

    @classmethod
    def _candidate_user_ids(cls, *, week_end_exclusive_dt: datetime) -> list[int]:
        xp_user_ids = set(
            XPTransaction.objects.filter(created_at__lt=week_end_exclusive_dt)
            .values_list("user_id", flat=True)
            .distinct()
        )
        technician_user_ids = set(
            User.objects.filter(
                is_active=True,
                roles__slug=RoleSlug.TECHNICIAN,
                roles__deleted_at__isnull=True,
            )
            .values_list("id", flat=True)
            .distinct()
        )
        return sorted(xp_user_ids | technician_user_ids)

    @classmethod
    def _xp_aggregates(
        cls,
        *,
        user_ids: list[int],
        period_start_inclusive_dt: datetime,
        period_end_exclusive_dt: datetime,
    ) -> tuple[dict[int, int], dict[int, int]]:
        if not user_ids:
            return {}, {}
        cumulative_rows = (
            XPTransaction.objects.filter(
                user_id__in=user_ids,
                created_at__lt=period_end_exclusive_dt,
            )
            .values("user_id")
            .annotate(total=Coalesce(Sum("amount"), 0))
        )
        period_rows = (
            XPTransaction.objects.filter(
                user_id__in=user_ids,
                created_at__gte=period_start_inclusive_dt,
                created_at__lt=period_end_exclusive_dt,
            )
            .values("user_id")
            .annotate(total=Coalesce(Sum("amount"), 0))
        )
        cumulative_by_user = {
            int(row["user_id"]): int(row["total"] or 0) for row in cumulative_rows
        }
        period_by_user = {
            int(row["user_id"]): int(row["total"] or 0) for row in period_rows
        }
        return cumulative_by_user, period_by_user

    @classmethod
    def _resolve_weekly_outcome(
        cls,
        *,
        previous_level: int,
        mapped_level: int,
        met_weekly_target: bool,
        previous_warning_active: bool,
    ) -> tuple[int, str, bool]:
        if met_weekly_target:
            new_level = max(previous_level, mapped_level)
            status = "level_up" if new_level > previous_level else "maintained"
            return new_level, status, False
        if previous_warning_active:
            return int(EmployeeLevel.L1), "reset_to_l1", False
        return previous_level, "warning", True

    @staticmethod
    def _display_name_for_user(user: User) -> str:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username

    @classmethod
    def map_raw_xp_to_level(
        cls,
        *,
        raw_xp: int,
        level_thresholds: dict[int, int] | None = None,
    ) -> int:
        normalized_raw_xp = max(0, int(raw_xp or 0))
        thresholds = level_thresholds or cls._default_level_thresholds()
        resolved_level = int(EmployeeLevel.L1)
        for level in EmployeeLevel.values:
            level_int = int(level)
            threshold = int(thresholds.get(level_int, 0))
            if normalized_raw_xp >= threshold:
                resolved_level = level_int
        return resolved_level

    @classmethod
    def get_weekly_progression_overview(
        cls,
        *,
        week_start: date | None = None,
    ) -> dict[str, Any]:
        target_week_start = week_start or cls.default_previous_week_start()
        week_start_date, week_end_date, _, _, _ = cls._date_range_bounds(
            date_from=target_week_start,
            date_to=target_week_start + timedelta(days=6),
        )
        return cls.get_level_control_overview(
            date_from=week_start_date,
            date_to=week_end_date,
        )

    @classmethod
    def get_level_control_overview(
        cls,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        resolved_date_from, resolved_date_to = (
            (date_from, date_to)
            if date_from is not None and date_to is not None
            else cls.default_last_7_day_range()
        )
        (
            resolved_date_from,
            resolved_date_to,
            range_start_dt,
            range_end_exclusive_dt,
            range_days,
        ) = cls._date_range_bounds(
            date_from=resolved_date_from,
            date_to=resolved_date_to,
        )
        level_thresholds, _, weekly_target_xp, rules_snapshot = (
            cls._progression_rules_from_active_config()
        )
        range_target_xp = (weekly_target_xp * range_days + 6) // 7

        users = list(
            User.objects.filter(
                is_active=True,
                roles__slug=RoleSlug.TECHNICIAN,
                roles__deleted_at__isnull=True,
            )
            .distinct()
            .only("id", "first_name", "last_name", "username", "level")
            .order_by("first_name", "last_name", "username", "id")
        )
        user_ids = [user.id for user in users]
        cumulative_xp_by_user, range_xp_by_user = cls._xp_aggregates(
            user_ids=user_ids,
            period_start_inclusive_dt=range_start_dt,
            period_end_exclusive_dt=range_end_exclusive_dt,
        )
        latest_history_by_user = cls._latest_level_history_by_user(
            user_ids=user_ids,
            created_before=range_end_exclusive_dt,
        )

        latest_evaluation_rows = (
            WeeklyLevelEvaluation.objects.select_related("evaluated_by")
            .filter(
                user_id__in=user_ids,
                week_end__lte=resolved_date_to,
            )
            .order_by("user_id", "-week_end", "-id")
        )
        latest_evaluation_by_user: dict[int, WeeklyLevelEvaluation] = {}
        for row in latest_evaluation_rows:
            if row.user_id not in latest_evaluation_by_user:
                latest_evaluation_by_user[row.user_id] = row

        rows: list[dict[str, Any]] = []
        summary = {
            "technicians_total": len(users),
            "met_target": 0,
            "below_target": 0,
            "warning_active": 0,
            "suggested_warning": 0,
            "suggested_reset_to_l1": 0,
        }

        for user in users:
            user_id = int(user.id)
            current_level = cls._normalize_level(user.level)
            range_xp = int(range_xp_by_user.get(user_id, 0))
            cumulative_xp = int(cumulative_xp_by_user.get(user_id, 0))
            mapped_level = cls.map_raw_xp_to_level(
                raw_xp=cumulative_xp,
                level_thresholds=level_thresholds,
            )
            meets_target = range_xp >= range_target_xp

            latest_history = latest_history_by_user.get(user_id)
            latest_eval = latest_evaluation_by_user.get(user_id)
            warning_active = cls._warning_active_from_history_event(latest_history)
            if latest_history is None:
                warning_active = cls._warning_active_from_evaluation(latest_eval)

            suggested_warning = (not meets_target) and (not warning_active)
            suggested_reset_to_l1 = (not meets_target) and warning_active

            if meets_target:
                summary["met_target"] += 1
            else:
                summary["below_target"] += 1
            if warning_active:
                summary["warning_active"] += 1
            if suggested_warning:
                summary["suggested_warning"] += 1
            if suggested_reset_to_l1:
                summary["suggested_reset_to_l1"] += 1

            latest_history_payload = None
            if latest_history:
                latest_history_payload = {
                    "id": latest_history.id,
                    "source": latest_history.source,
                    "status": latest_history.status,
                    "previous_level": int(latest_history.previous_level),
                    "new_level": int(latest_history.new_level),
                    "warning_active_before": bool(latest_history.warning_active_before),
                    "warning_active_after": bool(latest_history.warning_active_after),
                    "week_start": (
                        latest_history.week_start.isoformat()
                        if latest_history.week_start
                        else None
                    ),
                    "week_end": (
                        latest_history.week_end.isoformat()
                        if latest_history.week_end
                        else None
                    ),
                    "actor_id": latest_history.actor_id,
                    "actor_username": (
                        latest_history.actor.username if latest_history.actor else None
                    ),
                    "created_at": latest_history.created_at.isoformat(),
                    "note": latest_history.note,
                }

            latest_eval_payload = None
            if latest_eval:
                eval_payload = latest_eval.payload if isinstance(latest_eval.payload, dict) else {}
                latest_eval_payload = {
                    "id": latest_eval.id,
                    "week_start": latest_eval.week_start.isoformat(),
                    "week_end": latest_eval.week_end.isoformat(),
                    "raw_xp": int(latest_eval.raw_xp),
                    "weekly_xp": int(eval_payload.get("weekly_xp", 0) or 0),
                    "weekly_target_xp": int(
                        eval_payload.get("weekly_target_xp", weekly_target_xp) or 0
                    ),
                    "status": str(eval_payload.get("target_status", "")),
                    "warning_active_after": bool(
                        eval_payload.get("warning_active_after", False)
                    ),
                    "evaluated_by_id": latest_eval.evaluated_by_id,
                    "evaluated_by_username": (
                        latest_eval.evaluated_by.username
                        if latest_eval.evaluated_by
                        else None
                    ),
                    "created_at": latest_eval.created_at.isoformat(),
                }

            rows.append(
                {
                    "user_id": user_id,
                    "display_name": cls._display_name_for_user(user),
                    "username": user.username,
                    "current_level": current_level,
                    "suggested_level_by_xp": max(current_level, mapped_level),
                    "range_xp": range_xp,
                    "cumulative_xp": cumulative_xp,
                    "weekly_target_xp": weekly_target_xp,
                    "range_target_xp": range_target_xp,
                    "meets_target": meets_target,
                    "warning_active": warning_active,
                    "suggested_warning": suggested_warning,
                    "suggested_reset_to_l1": suggested_reset_to_l1,
                    "latest_history_event": latest_history_payload,
                    "latest_weekly_evaluation": latest_eval_payload,
                }
            )

        return {
            "date_from": resolved_date_from.isoformat(),
            "date_to": resolved_date_to.isoformat(),
            "range_days": range_days,
            "weekly_target_xp": weekly_target_xp,
            "range_target_xp": range_target_xp,
            "rules_version": int(rules_snapshot["version"]),
            "rows": rows,
            "summary": summary,
        }

    @classmethod
    def get_user_level_history(
        cls,
        *,
        user_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        user = User.objects.filter(pk=user_id).only(
            "id",
            "first_name",
            "last_name",
            "username",
            "level",
            "is_active",
        ).first()
        if not user:
            raise ValueError("User was not found.")

        normalized_limit = max(1, min(int(limit or 500), 2000))
        range_start_dt: datetime | None = None
        range_end_exclusive_dt: datetime | None = None
        resolved_date_from = date_from
        resolved_date_to = date_to
        if date_from is not None and date_to is not None:
            (
                resolved_date_from,
                resolved_date_to,
                range_start_dt,
                range_end_exclusive_dt,
                _,
            ) = cls._date_range_bounds(date_from=date_from, date_to=date_to)

        xp_qs = XPTransaction.objects.filter(user_id=user.id).order_by("-created_at", "-id")
        if range_start_dt is not None and range_end_exclusive_dt is not None:
            xp_qs = xp_qs.filter(
                created_at__gte=range_start_dt,
                created_at__lt=range_end_exclusive_dt,
            )
        xp_entries = list(xp_qs[:normalized_limit])

        eval_qs = WeeklyLevelEvaluation.objects.select_related("evaluated_by").filter(
            user_id=user.id
        ).order_by("-week_start", "-id")
        if resolved_date_from is not None and resolved_date_to is not None:
            eval_qs = eval_qs.filter(
                week_end__gte=resolved_date_from,
                week_start__lte=resolved_date_to,
            )
        evaluations = list(eval_qs[:normalized_limit])

        history_qs = UserLevelHistoryEvent.objects.select_related("actor").filter(
            user_id=user.id
        ).order_by("-created_at", "-id")
        if range_start_dt is not None and range_end_exclusive_dt is not None:
            history_qs = history_qs.filter(
                created_at__gte=range_start_dt,
                created_at__lt=range_end_exclusive_dt,
            )
        history_entries = list(history_qs[:normalized_limit])

        latest_history_event = cls._latest_level_history_for_user(user_id=user.id)
        warning_active_now = cls._warning_active_from_history_event(latest_history_event)
        if latest_history_event is None:
            latest_evaluation = (
                WeeklyLevelEvaluation.objects.filter(user_id=user.id)
                .order_by("-week_start", "-id")
                .first()
            )
            warning_active_now = cls._warning_active_from_evaluation(latest_evaluation)

        serialized_xp = [
            {
                "id": row.id,
                "amount": int(row.amount),
                "entry_type": row.entry_type,
                "reference": row.reference,
                "description": row.description,
                "payload": row.payload or {},
                "created_at": row.created_at.isoformat(),
            }
            for row in xp_entries
        ]
        serialized_evaluations = []
        for row in evaluations:
            payload = row.payload if isinstance(row.payload, dict) else {}
            serialized_evaluations.append(
                {
                    "id": row.id,
                    "week_start": row.week_start.isoformat(),
                    "week_end": row.week_end.isoformat(),
                    "raw_xp": int(row.raw_xp),
                    "previous_level": int(row.previous_level),
                    "new_level": int(row.new_level),
                    "is_level_up": bool(row.is_level_up),
                    "target_status": str(payload.get("target_status", "")),
                    "weekly_xp": int(payload.get("weekly_xp", 0) or 0),
                    "weekly_target_xp": int(payload.get("weekly_target_xp", 0) or 0),
                    "met_weekly_target": bool(payload.get("met_weekly_target", False)),
                    "warning_active_after": bool(
                        payload.get("warning_active_after", False)
                    ),
                    "evaluated_by_id": row.evaluated_by_id,
                    "evaluated_by_username": (
                        row.evaluated_by.username if row.evaluated_by else None
                    ),
                    "created_at": row.created_at.isoformat(),
                }
            )
        serialized_history = [
            {
                "id": row.id,
                "source": row.source,
                "status": row.status,
                "previous_level": int(row.previous_level),
                "new_level": int(row.new_level),
                "warning_active_before": bool(row.warning_active_before),
                "warning_active_after": bool(row.warning_active_after),
                "week_start": row.week_start.isoformat() if row.week_start else None,
                "week_end": row.week_end.isoformat() if row.week_end else None,
                "actor_id": row.actor_id,
                "actor_username": row.actor.username if row.actor else None,
                "reference": row.reference,
                "note": row.note,
                "payload": row.payload or {},
                "created_at": row.created_at.isoformat(),
            }
            for row in history_entries
        ]

        return {
            "user": {
                "id": user.id,
                "display_name": cls._display_name_for_user(user),
                "username": user.username,
                "is_active": bool(user.is_active),
                "level": cls._normalize_level(user.level),
                "warning_active_now": warning_active_now,
            },
            "range": {
                "date_from": resolved_date_from.isoformat(),
                "date_to": resolved_date_to.isoformat(),
            }
            if resolved_date_from is not None and resolved_date_to is not None
            else None,
            "xp_history": serialized_xp,
            "weekly_evaluations": serialized_evaluations,
            "level_history": serialized_history,
        }

    @classmethod
    @transaction.atomic
    def set_user_level_manually(
        cls,
        *,
        actor_user_id: int,
        user_id: int,
        new_level: int,
        note: str | None = None,
        clear_warning: bool = False,
    ) -> dict[str, Any]:
        if not User.objects.filter(id=actor_user_id).exists():
            raise ValueError("actor_user_id does not exist.")

        target_level = int(new_level)
        if target_level not in EmployeeLevel.values:
            raise ValueError("level is invalid.")

        user = (
            User.objects.select_for_update()
            .filter(id=user_id)
            .only("id", "first_name", "last_name", "username", "level")
            .first()
        )
        if not user:
            raise ValueError("Target user was not found.")

        previous_level = cls._normalize_level(user.level)
        latest_history = cls._latest_level_history_for_user(user_id=user.id)
        warning_before = cls._warning_active_from_history_event(latest_history)
        if latest_history is None:
            latest_eval = (
                WeeklyLevelEvaluation.objects.filter(user_id=user.id)
                .order_by("-week_start", "-id")
                .first()
            )
            warning_before = cls._warning_active_from_evaluation(latest_eval)

        warning_after = False if clear_warning else warning_before
        normalized_note = str(note or "").strip()

        if target_level != previous_level:
            user.level = target_level
            user.save(update_fields=["level", "updated_at"])

        status = "manual_review"
        if clear_warning and warning_before and target_level == previous_level:
            status = "warning_cleared"
        elif clear_warning and warning_before and target_level != previous_level:
            status = "manual_set_and_warning_cleared"
        elif target_level != previous_level:
            status = "manual_set"

        reference = f"manual_level:{user.id}:{uuid4().hex}"
        history_event = UserLevelHistoryEvent.objects.create(
            user_id=user.id,
            actor_id=actor_user_id,
            weekly_evaluation=None,
            source=UserLevelHistorySource.MANUAL_OVERRIDE,
            status=status,
            previous_level=previous_level,
            new_level=target_level,
            warning_active_before=warning_before,
            warning_active_after=warning_after,
            week_start=None,
            week_end=None,
            reference=reference,
            note=normalized_note,
            payload={
                "clear_warning": bool(clear_warning),
                "actor_user_id": int(actor_user_id),
            },
        )

        UserNotificationService.notify_manual_level_update(
            target_user_id=user.id,
            actor_user_id=actor_user_id,
            previous_level=previous_level,
            new_level=target_level,
            warning_active_before=warning_before,
            warning_active_after=warning_after,
            note=normalized_note,
        )

        return {
            "user_id": user.id,
            "display_name": cls._display_name_for_user(user),
            "username": user.username,
            "previous_level": previous_level,
            "new_level": target_level,
            "warning_active_before": warning_before,
            "warning_active_after": warning_after,
            "status": status,
            "history_event_id": history_event.id,
            "history_reference": history_event.reference,
            "history_created_at": history_event.created_at.isoformat(),
        }

    @classmethod
    @transaction.atomic
    def run_weekly_level_evaluation(
        cls,
        *,
        week_start: date | None = None,
        actor_user_id: int | None = None,
    ) -> dict[str, int | str]:
        if (
            actor_user_id is not None
            and not User.objects.filter(id=actor_user_id).exists()
        ):
            raise ValueError("actor_user_id does not exist.")

        target_week_start = week_start or cls.default_previous_week_start()
        week_start, week_end, week_start_inclusive_dt, week_end_exclusive_dt = (
            cls._week_bounds(target_week_start)
        )
        level_thresholds, coupon_amount, weekly_target_xp, rules_snapshot = (
            cls._progression_rules_from_active_config()
        )

        candidate_user_ids = cls._candidate_user_ids(
            week_end_exclusive_dt=week_end_exclusive_dt
        )
        users_by_id = {
            user.id: user
            for user in User.objects.select_for_update()
            .filter(id__in=candidate_user_ids, is_active=True)
            .only("id", "level")
            .order_by("id")
        }
        user_ids = sorted(users_by_id.keys())
        cumulative_by_user, weekly_by_user = cls._xp_aggregates(
            user_ids=user_ids,
            period_start_inclusive_dt=week_start_inclusive_dt,
            period_end_exclusive_dt=week_end_exclusive_dt,
        )
        already_evaluated_user_ids = set(
            WeeklyLevelEvaluation.objects.filter(
                week_start=week_start, user_id__in=user_ids
            ).values_list("user_id", flat=True)
        )
        previous_evaluation_by_user = cls._latest_previous_evaluation_by_user(
            user_ids=user_ids,
            week_start=week_start,
        )
        previous_history_by_user = cls._latest_level_history_by_user(
            user_ids=user_ids,
            created_before=week_start_inclusive_dt,
        )

        created = 0
        skipped = 0
        level_ups = 0
        coupon_events = 0
        warnings = 0
        resets_to_l1 = 0

        for user_id in user_ids:
            if user_id in already_evaluated_user_ids:
                skipped += 1
                continue

            user = users_by_id.get(user_id)
            if not user:
                continue

            cumulative_xp = int(cumulative_by_user.get(user_id, 0))
            weekly_xp = int(weekly_by_user.get(user_id, 0))
            met_weekly_target = weekly_xp >= weekly_target_xp
            previous_level = cls._normalize_level(user.level)
            mapped_level = cls.map_raw_xp_to_level(
                raw_xp=cumulative_xp,
                level_thresholds=level_thresholds,
            )
            previous_warning_active = cls._warning_active_from_history_event(
                previous_history_by_user.get(user_id)
            )
            if user_id not in previous_history_by_user:
                previous_warning_active = cls._warning_active_from_evaluation(
                    previous_evaluation_by_user.get(user_id)
                )
            new_level, target_status, warning_active_after = cls._resolve_weekly_outcome(
                previous_level=previous_level,
                mapped_level=mapped_level,
                met_weekly_target=met_weekly_target,
                previous_warning_active=previous_warning_active,
            )
            is_level_up = new_level > previous_level

            evaluation = WeeklyLevelEvaluation.objects.create(
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                raw_xp=cumulative_xp,
                previous_level=previous_level,
                new_level=new_level,
                is_level_up=is_level_up,
                rules_version=int(rules_snapshot["version"]),
                rules_cache_key=str(rules_snapshot["cache_key"]),
                evaluated_by_id=actor_user_id,
                payload={
                    "thresholds": {str(k): int(v) for k, v in level_thresholds.items()},
                    "raw_xp": cumulative_xp,
                    "weekly_xp": weekly_xp,
                    "weekly_target_xp": weekly_target_xp,
                    "met_weekly_target": met_weekly_target,
                    "previous_warning_active": previous_warning_active,
                    "warning_active_after": warning_active_after,
                    "target_status": target_status,
                },
            )

            UserLevelHistoryEvent.objects.create(
                user_id=user_id,
                actor_id=actor_user_id,
                weekly_evaluation=evaluation,
                source=UserLevelHistorySource.WEEKLY_EVALUATION,
                status=target_status,
                previous_level=previous_level,
                new_level=new_level,
                warning_active_before=previous_warning_active,
                warning_active_after=warning_active_after,
                week_start=week_start,
                week_end=week_end,
                reference=f"weekly_level_history:{week_start.isoformat()}:{user_id}",
                note="",
                payload={
                    "weekly_xp": weekly_xp,
                    "weekly_target_xp": weekly_target_xp,
                    "met_weekly_target": met_weekly_target,
                },
            )

            created += 1

            if new_level != previous_level:
                user.level = new_level
                user.save(update_fields=["level", "updated_at"])

            if target_status == "warning":
                warnings += 1
            if target_status == "reset_to_l1":
                resets_to_l1 += 1

            if is_level_up:
                level_ups += 1
                if coupon_amount > 0:
                    coupon_reference = (
                        f"level_up_coupon:{week_start.isoformat()}:{user_id}"
                    )
                    try:
                        LevelUpCouponEvent.objects.create(
                            user_id=user_id,
                            evaluation=evaluation,
                            week_start=week_start,
                            amount=coupon_amount,
                            currency="UZS",
                            reference=coupon_reference,
                            description="Weekly level-up coupon",
                            issued_by_id=actor_user_id,
                            payload={
                                "week_start": week_start.isoformat(),
                                "week_end": week_end.isoformat(),
                                "previous_level": previous_level,
                                "new_level": new_level,
                            },
                        )
                        coupon_events += 1
                    except IntegrityError:
                        pass

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "weekly_target_xp": weekly_target_xp,
            "evaluations_created": created,
            "evaluations_skipped": skipped,
            "level_ups": level_ups,
            "warnings_created": warnings,
            "levels_reset_to_l1": resets_to_l1,
            "coupon_events_created": coupon_events,
        }
