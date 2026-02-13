from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from account.models import User
from core.utils.constants import (
    EmployeeLevel,
    PayrollAllowanceDecision,
    PayrollMonthStatus,
)
from gamification.models import XPLedger
from payroll.models import (
    PayrollAllowanceGateDecision,
    PayrollMonthly,
    PayrollMonthlyLine,
)
from rules.services import RulesService
from ticket.services_stockout import StockoutIncidentService


class PayrollService:
    BUSINESS_TZ = ZoneInfo("Asia/Tashkent")

    @staticmethod
    def _payroll_month_queryset():
        return (
            PayrollMonthly.objects.select_related("closed_by", "approved_by")
            .prefetch_related("lines__user")
            .prefetch_related("allowance_gate_decisions__decided_by")
        )

    @staticmethod
    def parse_month_token(month_token: str) -> date:
        try:
            parsed = datetime.strptime(month_token, "%Y-%m")
        except ValueError as exc:
            raise ValueError("month must be in YYYY-MM format.") from exc
        return date(parsed.year, parsed.month, 1)

    @classmethod
    def _month_bounds(cls, month_start: date) -> tuple[datetime, datetime]:
        if month_start.month == 12:
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)

        month_start_dt = timezone.make_aware(
            datetime.combine(month_start, time.min), cls.BUSINESS_TZ
        )
        next_month_start_dt = timezone.make_aware(
            datetime.combine(next_month, time.min), cls.BUSINESS_TZ
        )
        return month_start_dt, next_month_start_dt

    @staticmethod
    def _normalize_level(level: int | None) -> int:
        if level in EmployeeLevel.values:
            return int(level)
        return int(EmployeeLevel.L1)

    @staticmethod
    def _payroll_rules_from_active_config() -> tuple[
        int,
        int,
        dict[int, int],
        dict[int, int],
        dict[str, int | bool | set[int]],
        dict,
    ]:
        rules_state = RulesService.get_active_rules_state()
        rules_config = rules_state.active_version.config
        payroll_rules = rules_config.get("payroll", {})
        fix_salary = int(payroll_rules.get("fix_salary", 3_000_000) or 0)
        bonus_rate = int(payroll_rules.get("bonus_rate", 3_000) or 0)

        caps_raw = payroll_rules.get("level_caps", {})
        allowances_raw = payroll_rules.get("level_allowances", {})

        level_caps = {
            int(level): int(caps_raw.get(str(level), 0) or 0)
            for level in EmployeeLevel.values
        }
        level_allowances = {
            int(level): int(allowances_raw.get(str(level), 0) or 0)
            for level in EmployeeLevel.values
        }

        allowance_gate_rules = rules_config.get("sla", {}).get("allowance_gate", {})
        raw_enabled = allowance_gate_rules.get("enabled", False)
        gate_enabled = raw_enabled if isinstance(raw_enabled, bool) else False
        gated_levels: set[int] = set()
        for raw_level in allowance_gate_rules.get("gated_levels", []):
            try:
                level_value = int(raw_level)
            except (TypeError, ValueError):
                continue
            if level_value in EmployeeLevel.values:
                gated_levels.add(level_value)
        try:
            min_first_pass_rate_percent = int(
                allowance_gate_rules.get("min_first_pass_rate_percent", 0) or 0
            )
        except (TypeError, ValueError):
            min_first_pass_rate_percent = 0
        min_first_pass_rate_percent = max(0, min(100, min_first_pass_rate_percent))
        try:
            max_stockout_minutes = int(
                allowance_gate_rules.get("max_stockout_minutes", 0) or 0
            )
        except (TypeError, ValueError):
            max_stockout_minutes = 0
        max_stockout_minutes = max(0, max_stockout_minutes)
        allowance_gate = {
            "enabled": gate_enabled,
            "gated_levels": gated_levels,
            "min_first_pass_rate_percent": min_first_pass_rate_percent,
            "max_stockout_minutes": max_stockout_minutes,
        }

        rules_snapshot = {
            "version": rules_state.active_version.version,
            "cache_key": rules_state.cache_key,
            "config": rules_config,
        }
        return (
            fix_salary,
            bonus_rate,
            level_caps,
            level_allowances,
            allowance_gate,
            rules_snapshot,
        )

    @staticmethod
    def _level_allowances_from_rules_snapshot(
        payroll_month: PayrollMonthly,
    ) -> dict[int, int]:
        rules_snapshot = payroll_month.rules_snapshot or {}
        config = rules_snapshot.get("config", {})
        payroll_rules = config.get("payroll", {}) if isinstance(config, dict) else {}
        raw_allowances = payroll_rules.get("level_allowances", {})
        if not isinstance(raw_allowances, dict):
            raw_allowances = {}

        level_allowances: dict[int, int] = {}
        for level in EmployeeLevel.values:
            raw = raw_allowances.get(str(level), raw_allowances.get(level, 0))
            try:
                level_allowances[int(level)] = max(int(raw or 0), 0)
            except (TypeError, ValueError):
                level_allowances[int(level)] = 0
        return level_allowances

    @classmethod
    @transaction.atomic
    def close_payroll_month(
        cls, *, month_token: str, actor_user_id: int
    ) -> PayrollMonthly:
        month_start = cls.parse_month_token(month_token)
        month_start_dt, next_month_start_dt = cls._month_bounds(month_start)
        now_dt = timezone.now()
        (
            fix_salary,
            bonus_rate,
            level_caps,
            level_allowances,
            allowance_gate,
            rules_snapshot,
        ) = cls._payroll_rules_from_active_config()
        sla_snapshot = StockoutIncidentService.monthly_sla_snapshot(
            month_start_dt=month_start_dt,
            next_month_start_dt=next_month_start_dt,
        )
        allowance_gate_reasons: list[str] = []
        if allowance_gate["enabled"]:
            if (
                sla_snapshot["qc"]["first_pass_rate_percent"]
                < allowance_gate["min_first_pass_rate_percent"]
            ):
                allowance_gate_reasons.append("first_pass_rate_below_threshold")
            if (
                sla_snapshot["stockout"]["minutes"]
                > allowance_gate["max_stockout_minutes"]
            ):
                allowance_gate_reasons.append("stockout_minutes_above_threshold")
        allowance_gate_passed = len(allowance_gate_reasons) == 0

        payroll_month, _ = PayrollMonthly.objects.select_for_update().get_or_create(
            month=month_start
        )
        if payroll_month.status == PayrollMonthStatus.CLOSED:
            raise ValueError("Payroll month is already closed.")
        if payroll_month.status == PayrollMonthStatus.APPROVED:
            raise ValueError(
                "Payroll month is already approved and cannot be closed again."
            )

        payroll_month.lines.all().delete()

        xp_rows = list(
            XPLedger.objects.filter(
                created_at__gte=month_start_dt, created_at__lt=next_month_start_dt
            )
            .values("user_id")
            .annotate(raw_xp=Coalesce(Sum("amount"), 0))
            .order_by("user_id")
        )
        users_by_id = {
            user.id: user
            for user in User.objects.filter(
                id__in=[row["user_id"] for row in xp_rows]
            ).only("id", "level")
        }

        lines = []
        total_raw_xp = 0
        total_paid_xp = 0
        total_fix_salary = 0
        total_bonus_amount = 0
        total_allowance_amount = 0
        total_payout_amount = 0

        for row in xp_rows:
            user = users_by_id.get(row["user_id"])
            if not user:
                continue

            raw_xp = int(row["raw_xp"] or 0)
            level = cls._normalize_level(user.level)
            paid_xp_cap = level_caps[level]
            paid_xp = max(0, min(raw_xp, paid_xp_cap))
            allowance_amount = level_allowances[level]
            allowance_gated = (
                allowance_gate["enabled"]
                and level in allowance_gate["gated_levels"]
                and not allowance_gate_passed
            )
            if allowance_gated:
                allowance_amount = 0
            bonus_amount = paid_xp * bonus_rate
            total_amount = fix_salary + allowance_amount + bonus_amount

            total_raw_xp += raw_xp
            total_paid_xp += paid_xp
            total_fix_salary += fix_salary
            total_bonus_amount += bonus_amount
            total_allowance_amount += allowance_amount
            total_payout_amount += total_amount

            lines.append(
                PayrollMonthlyLine(
                    payroll_monthly=payroll_month,
                    user_id=user.id,
                    level=level,
                    raw_xp=raw_xp,
                    paid_xp=paid_xp,
                    paid_xp_cap=paid_xp_cap,
                    fix_salary=fix_salary,
                    allowance_amount=allowance_amount,
                    bonus_rate=bonus_rate,
                    bonus_amount=bonus_amount,
                    total_amount=total_amount,
                    payload={
                        "month": month_start.strftime("%Y-%m"),
                        "raw_xp": raw_xp,
                        "paid_xp_cap": paid_xp_cap,
                        "paid_xp": paid_xp,
                        "level": level,
                        "allowance_gated": allowance_gated,
                        "allowance_gate_reasons": allowance_gate_reasons,
                    },
                )
            )

        if lines:
            PayrollMonthlyLine.objects.bulk_create(lines)

        payroll_month.status = PayrollMonthStatus.CLOSED
        payroll_month.closed_at = now_dt
        payroll_month.closed_by_id = actor_user_id
        payroll_month.approved_at = None
        payroll_month.approved_by = None
        rules_snapshot["sla_snapshot"] = sla_snapshot
        rules_snapshot["allowance_gate"] = {
            "enabled": allowance_gate["enabled"],
            "gated_levels": sorted(allowance_gate["gated_levels"]),
            "min_first_pass_rate_percent": allowance_gate[
                "min_first_pass_rate_percent"
            ],
            "max_stockout_minutes": allowance_gate["max_stockout_minutes"],
            "passed": allowance_gate_passed,
            "reasons": allowance_gate_reasons,
        }
        payroll_month.rules_snapshot = rules_snapshot
        payroll_month.total_raw_xp = total_raw_xp
        payroll_month.total_paid_xp = total_paid_xp
        payroll_month.total_fix_salary = total_fix_salary
        payroll_month.total_bonus_amount = total_bonus_amount
        payroll_month.total_allowance_amount = total_allowance_amount
        payroll_month.total_payout_amount = total_payout_amount
        payroll_month.save(
            update_fields=[
                "status",
                "closed_at",
                "closed_by",
                "approved_at",
                "approved_by",
                "rules_snapshot",
                "total_raw_xp",
                "total_paid_xp",
                "total_fix_salary",
                "total_bonus_amount",
                "total_allowance_amount",
                "total_payout_amount",
                "updated_at",
            ]
        )

        return cls._payroll_month_queryset().get(pk=payroll_month.pk)

    @classmethod
    @transaction.atomic
    def apply_allowance_gate_decision(
        cls,
        *,
        month_token: str,
        actor_user_id: int,
        decision: str,
        note: str = "",
    ) -> PayrollMonthly:
        if decision not in PayrollAllowanceDecision.values:
            raise ValueError("Invalid allowance gate decision.")

        month_start = cls.parse_month_token(month_token)
        payroll_month = (
            PayrollMonthly.objects.select_for_update().filter(month=month_start).first()
        )
        if not payroll_month:
            raise ValueError("Payroll month is not closed yet.")
        if payroll_month.status == PayrollMonthStatus.DRAFT:
            raise ValueError("Payroll month must be closed before allowance decisions.")
        if payroll_month.status == PayrollMonthStatus.APPROVED:
            raise ValueError(
                "Payroll month is already approved and allowance decisions are locked."
            )

        allowance_gate_snapshot = dict(
            (payroll_month.rules_snapshot or {}).get("allowance_gate", {})
        )
        gate_reasons = allowance_gate_snapshot.get("reasons", [])
        if not isinstance(gate_reasons, list):
            gate_reasons = []

        if decision == PayrollAllowanceDecision.KEEP_GATED:
            PayrollAllowanceGateDecision.objects.create(
                payroll_monthly=payroll_month,
                decision=decision,
                decided_by_id=actor_user_id,
                affected_lines_count=0,
                total_allowance_delta=0,
                note=note,
                payload={
                    "gate_reasons": gate_reasons,
                    "rules_version": (payroll_month.rules_snapshot or {}).get(
                        "version"
                    ),
                },
            )
            return cls._payroll_month_queryset().get(pk=payroll_month.pk)

        level_allowances = cls._level_allowances_from_rules_snapshot(payroll_month)
        now_dt = timezone.now()
        total_allowance_delta = 0
        affected_lines_count = 0

        lines = list(payroll_month.lines.select_for_update().all())
        for line in lines:
            payload = dict(line.payload or {})
            if not payload.get("allowance_gated"):
                continue
            if payload.get("allowance_override_released"):
                continue

            expected_allowance = int(
                level_allowances.get(int(line.level), int(line.allowance_amount or 0))
            )
            delta = expected_allowance - int(line.allowance_amount or 0)
            if delta < 0:
                delta = 0

            line.allowance_amount = expected_allowance
            line.total_amount = int(line.total_amount or 0) + delta
            payload["allowance_gated"] = False
            payload["allowance_override_released"] = True
            payload["allowance_override_released_at"] = now_dt.isoformat()
            payload["allowance_override_released_by"] = actor_user_id
            line.payload = payload
            line.save(
                update_fields=[
                    "allowance_amount",
                    "total_amount",
                    "payload",
                    "updated_at",
                ]
            )

            total_allowance_delta += delta
            affected_lines_count += 1

        if affected_lines_count == 0:
            raise ValueError("No gated payroll lines are available for release.")

        payroll_month.total_allowance_amount = int(
            payroll_month.total_allowance_amount
        ) + int(total_allowance_delta)
        payroll_month.total_payout_amount = int(
            payroll_month.total_payout_amount
        ) + int(total_allowance_delta)
        rules_snapshot = dict(payroll_month.rules_snapshot or {})
        rules_snapshot_allowance_gate = dict(rules_snapshot.get("allowance_gate", {}))
        rules_snapshot_allowance_gate["manual_decision"] = {
            "decision": decision,
            "actor_user_id": actor_user_id,
            "note": note,
            "affected_lines_count": affected_lines_count,
            "total_allowance_delta": total_allowance_delta,
            "applied_at": now_dt.isoformat(),
        }
        rules_snapshot["allowance_gate"] = rules_snapshot_allowance_gate
        payroll_month.rules_snapshot = rules_snapshot
        payroll_month.save(
            update_fields=[
                "rules_snapshot",
                "total_allowance_amount",
                "total_payout_amount",
                "updated_at",
            ]
        )

        PayrollAllowanceGateDecision.objects.create(
            payroll_monthly=payroll_month,
            decision=decision,
            decided_by_id=actor_user_id,
            affected_lines_count=affected_lines_count,
            total_allowance_delta=total_allowance_delta,
            note=note,
            payload={
                "gate_reasons": gate_reasons,
                "rules_version": (payroll_month.rules_snapshot or {}).get("version"),
            },
        )
        return cls._payroll_month_queryset().get(pk=payroll_month.pk)

    @classmethod
    @transaction.atomic
    def approve_payroll_month(
        cls, *, month_token: str, actor_user_id: int
    ) -> PayrollMonthly:
        month_start = cls.parse_month_token(month_token)
        payroll_month = (
            PayrollMonthly.objects.select_for_update().filter(month=month_start).first()
        )
        if not payroll_month:
            raise ValueError("Payroll month is not closed yet.")
        if payroll_month.status == PayrollMonthStatus.DRAFT:
            raise ValueError("Payroll month must be closed before approval.")
        if payroll_month.status == PayrollMonthStatus.APPROVED:
            raise ValueError("Payroll month is already approved.")

        payroll_month.status = PayrollMonthStatus.APPROVED
        payroll_month.approved_at = timezone.now()
        payroll_month.approved_by_id = actor_user_id
        payroll_month.save(
            update_fields=["status", "approved_at", "approved_by", "updated_at"]
        )

        return cls._payroll_month_queryset().get(pk=payroll_month.pk)

    @classmethod
    def get_payroll_month(cls, *, month_token: str) -> PayrollMonthly | None:
        month_start = cls.parse_month_token(month_token)
        return cls._payroll_month_queryset().filter(month=month_start).first()
