from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from account.models import User
from core.api.exceptions import DomainValidationError
from core.services.notifications import UserNotificationService
from core.utils.constants import EmployeeLevel, XPTransactionEntryType
from gamification.models import LevelUpCouponEvent, WeeklyLevelEvaluation, XPTransaction
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
    """Weekly progression evaluator that maps raw XP to persisted user levels."""

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
    def parse_week_start_token(week_start_token: str) -> date:
        try:
            parsed = datetime.strptime(week_start_token, "%Y-%m-%d")
        except ValueError as exc:
            raise DomainValidationError(
                "week_start must be in YYYY-MM-DD format."
            ) from exc
        week_start = date(parsed.year, parsed.month, parsed.day)
        if week_start.weekday() != 0:
            raise DomainValidationError("week_start must be a Monday date.")
        return week_start

    @classmethod
    def default_previous_week_start(cls) -> date:
        local_today = timezone.now().astimezone(cls.BUSINESS_TZ).date()
        current_week_start = local_today - timedelta(days=local_today.weekday())
        return current_week_start - timedelta(days=7)

    @classmethod
    def _week_bounds(cls, week_start: date) -> tuple[date, date, datetime]:
        if week_start.weekday() != 0:
            raise DomainValidationError("week_start must be a Monday date.")

        week_end = week_start + timedelta(days=6)
        week_end_exclusive_dt = timezone.make_aware(
            datetime.combine(week_end + timedelta(days=1), time.min),
            cls.BUSINESS_TZ,
        )
        return week_start, week_end, week_end_exclusive_dt

    @classmethod
    def _progression_rules_from_active_config(cls) -> tuple[dict[int, int], int, dict]:
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

        rules_snapshot = {
            "version": state.active_version.version,
            "cache_key": state.cache_key,
        }
        return normalized_thresholds, coupon_amount, rules_snapshot

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
        week_start, week_end, week_end_exclusive_dt = cls._week_bounds(
            target_week_start
        )
        level_thresholds, coupon_amount, rules_snapshot = (
            cls._progression_rules_from_active_config()
        )

        xp_rows = list(
            XPTransaction.objects.filter(created_at__lt=week_end_exclusive_dt)
            .values("user_id")
            .annotate(raw_xp=Coalesce(Sum("amount"), 0))
            .order_by("user_id")
        )
        user_ids = [row["user_id"] for row in xp_rows]

        users_by_id = {
            user.id: user
            for user in User.objects.select_for_update()
            .filter(id__in=user_ids)
            .only("id", "level")
        }
        already_evaluated_user_ids = set(
            WeeklyLevelEvaluation.objects.filter(
                week_start=week_start, user_id__in=user_ids
            ).values_list("user_id", flat=True)
        )

        created = 0
        skipped = 0
        level_ups = 0
        coupon_events = 0

        for row in xp_rows:
            user_id = int(row["user_id"])
            if user_id in already_evaluated_user_ids:
                skipped += 1
                continue

            user = users_by_id.get(user_id)
            if not user:
                continue

            raw_xp = int(row["raw_xp"] or 0)
            previous_level = cls._normalize_level(user.level)
            mapped_level = cls.map_raw_xp_to_level(
                raw_xp=raw_xp, level_thresholds=level_thresholds
            )
            new_level = max(previous_level, mapped_level)
            is_level_up = new_level > previous_level

            evaluation = WeeklyLevelEvaluation.objects.create(
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                raw_xp=raw_xp,
                previous_level=previous_level,
                new_level=new_level,
                is_level_up=is_level_up,
                rules_version=int(rules_snapshot["version"]),
                rules_cache_key=str(rules_snapshot["cache_key"]),
                evaluated_by_id=actor_user_id,
                payload={
                    "thresholds": {str(k): int(v) for k, v in level_thresholds.items()},
                    "raw_xp": raw_xp,
                },
            )
            created += 1

            if is_level_up:
                user.level = new_level
                user.save(update_fields=["level", "updated_at"])
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
            "evaluations_created": created,
            "evaluations_skipped": skipped,
            "level_ups": level_ups,
            "coupon_events_created": coupon_events,
        }
