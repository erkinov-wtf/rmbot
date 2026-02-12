from django.db import models

from core.models import TimestampedModel
from core.utils.constants import EmployeeLevel, PayrollMonthStatus


class PayrollMonthly(TimestampedModel):
    month = models.DateField(unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=PayrollMonthStatus,
        default=PayrollMonthStatus.DRAFT,
        db_index=True,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_closed_months",
    )
    approved_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_approved_months",
    )
    rules_snapshot = models.JSONField(default=dict, blank=True)

    total_raw_xp = models.IntegerField(default=0)
    total_paid_xp = models.PositiveIntegerField(default=0)
    total_fix_salary = models.PositiveBigIntegerField(default=0)
    total_bonus_amount = models.PositiveBigIntegerField(default=0)
    total_allowance_amount = models.PositiveBigIntegerField(default=0)
    total_payout_amount = models.PositiveBigIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["status", "month"]),
        ]

    def __str__(self) -> str:
        return f"PayrollMonthly#{self.pk} {self.month:%Y-%m} [{self.status}]"


class PayrollMonthlyLine(TimestampedModel):
    payroll_monthly = models.ForeignKey(
        PayrollMonthly, on_delete=models.CASCADE, related_name="lines"
    )
    user = models.ForeignKey(
        "account.User", on_delete=models.PROTECT, related_name="payroll_monthly_lines"
    )
    level = models.PositiveSmallIntegerField(choices=EmployeeLevel)

    raw_xp = models.IntegerField(default=0)
    paid_xp = models.PositiveIntegerField(default=0)
    paid_xp_cap = models.PositiveIntegerField(default=0)

    fix_salary = models.PositiveBigIntegerField(default=0)
    allowance_amount = models.PositiveBigIntegerField(default=0)
    bonus_rate = models.PositiveIntegerField(default=0)
    bonus_amount = models.PositiveBigIntegerField(default=0)
    total_amount = models.PositiveBigIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["payroll_monthly", "user"]),
            models.Index(fields=["user", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_monthly", "user"],
                name="unique_payroll_monthly_line_per_user",
            )
        ]

    def __str__(self) -> str:
        return (
            f"PayrollMonthlyLine#{self.pk} month={self.payroll_monthly.month:%Y-%m} "
            f"user={self.user_id} paid_xp={self.paid_xp}"
        )
