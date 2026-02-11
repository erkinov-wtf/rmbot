from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from account.models import User
from core.utils.constants import EmployeeLevel, PayrollMonthStatus
from gamification.models import XPLedger
from payroll.models import PayrollMonthly, PayrollMonthlyLine


BUSINESS_TZ = ZoneInfo("Asia/Tashkent")
DEFAULT_FIX_SALARY = 3_000_000
DEFAULT_BONUS_RATE = 3_000
DEFAULT_PAID_XP_CAPS = {
    EmployeeLevel.L1: 167,
    EmployeeLevel.L2: 267,
    EmployeeLevel.L3: 400,
    EmployeeLevel.L4: 433,
    EmployeeLevel.L5: 500,
}
DEFAULT_LEVEL_ALLOWANCES = {
    EmployeeLevel.L1: 0,
    EmployeeLevel.L2: 200_000,
    EmployeeLevel.L3: 1_300_000,
    EmployeeLevel.L4: 2_200_000,
    EmployeeLevel.L5: 4_000_000,
}


def parse_month_token(month_token: str) -> date:
    try:
        parsed = datetime.strptime(month_token, "%Y-%m")
    except ValueError as exc:
        raise ValueError("month must be in YYYY-MM format.") from exc
    return date(parsed.year, parsed.month, 1)


def _month_bounds(month_start: date) -> tuple[datetime, datetime]:
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)

    month_start_dt = timezone.make_aware(datetime.combine(month_start, time.min), BUSINESS_TZ)
    next_month_start_dt = timezone.make_aware(datetime.combine(next_month, time.min), BUSINESS_TZ)
    return month_start_dt, next_month_start_dt


def _normalize_level(level: int | None) -> int:
    if level in EmployeeLevel.values:
        return int(level)
    return int(EmployeeLevel.L1)


def _rules_snapshot() -> dict:
    return {
        "fix_salary": DEFAULT_FIX_SALARY,
        "bonus_rate": DEFAULT_BONUS_RATE,
        "level_rules": {
            str(level): {
                "paid_xp_cap": DEFAULT_PAID_XP_CAPS[level],
                "allowance": DEFAULT_LEVEL_ALLOWANCES[level],
            }
            for level in EmployeeLevel.values
        },
    }


@transaction.atomic
def close_payroll_month(*, month_token: str, actor_user_id: int) -> PayrollMonthly:
    month_start = parse_month_token(month_token)
    month_start_dt, next_month_start_dt = _month_bounds(month_start)
    now_dt = timezone.now()

    payroll_month, _ = PayrollMonthly.objects.select_for_update().get_or_create(month=month_start)
    if payroll_month.status == PayrollMonthStatus.CLOSED:
        raise ValueError("Payroll month is already closed.")
    if payroll_month.status == PayrollMonthStatus.APPROVED:
        raise ValueError("Payroll month is already approved and cannot be closed again.")

    payroll_month.lines.all().delete()

    xp_rows = list(
        XPLedger.objects.filter(created_at__gte=month_start_dt, created_at__lt=next_month_start_dt)
        .values("user_id")
        .annotate(raw_xp=Coalesce(Sum("amount"), 0))
        .order_by("user_id")
    )
    users_by_id = {
        user.id: user
        for user in User.objects.filter(id__in=[row["user_id"] for row in xp_rows]).only("id", "level")
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
        level = _normalize_level(user.level)
        paid_xp_cap = DEFAULT_PAID_XP_CAPS[level]
        paid_xp = max(0, min(raw_xp, paid_xp_cap))
        fix_salary = DEFAULT_FIX_SALARY
        allowance_amount = DEFAULT_LEVEL_ALLOWANCES[level]
        bonus_rate = DEFAULT_BONUS_RATE
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
    payroll_month.rules_snapshot = _rules_snapshot()
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

    return PayrollMonthly.objects.select_related("closed_by", "approved_by").prefetch_related("lines__user").get(
        pk=payroll_month.pk
    )


@transaction.atomic
def approve_payroll_month(*, month_token: str, actor_user_id: int) -> PayrollMonthly:
    month_start = parse_month_token(month_token)
    payroll_month = PayrollMonthly.objects.select_for_update().filter(month=month_start).first()
    if not payroll_month:
        raise ValueError("Payroll month is not closed yet.")
    if payroll_month.status == PayrollMonthStatus.DRAFT:
        raise ValueError("Payroll month must be closed before approval.")
    if payroll_month.status == PayrollMonthStatus.APPROVED:
        raise ValueError("Payroll month is already approved.")

    payroll_month.status = PayrollMonthStatus.APPROVED
    payroll_month.approved_at = timezone.now()
    payroll_month.approved_by_id = actor_user_id
    payroll_month.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    return PayrollMonthly.objects.select_related("closed_by", "approved_by").prefetch_related("lines__user").get(
        pk=payroll_month.pk
    )


def get_payroll_month(*, month_token: str) -> PayrollMonthly | None:
    month_start = parse_month_token(month_token)
    return PayrollMonthly.objects.select_related("closed_by", "approved_by").prefetch_related("lines__user").filter(
        month=month_start
    ).first()
