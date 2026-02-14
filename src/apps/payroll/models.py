from django.db import models
from django.utils import timezone

from core.models import AppendOnlyModel, TimestampedModel
from core.utils.constants import (
    EmployeeLevel,
    PayrollAllowanceDecision,
    PayrollMonthStatus,
)
from payroll.managers import PayrollMonthlyDomainManager


class PayrollMonthly(TimestampedModel):
    domain = PayrollMonthlyDomainManager()

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

    def assert_closable(self) -> None:
        if self.status == PayrollMonthStatus.CLOSED:
            raise ValueError("Payroll month is already closed.")
        if self.status == PayrollMonthStatus.APPROVED:
            raise ValueError(
                "Payroll month is already approved and cannot be closed again."
            )

    def assert_allowance_decision_mutable(self) -> None:
        if self.status == PayrollMonthStatus.DRAFT:
            raise ValueError("Payroll month must be closed before allowance decisions.")
        if self.status == PayrollMonthStatus.APPROVED:
            raise ValueError(
                "Payroll month is already approved and allowance decisions are locked."
            )

    def assert_approvable(self) -> None:
        if self.status == PayrollMonthStatus.DRAFT:
            raise ValueError("Payroll month must be closed before approval.")
        if self.status == PayrollMonthStatus.APPROVED:
            raise ValueError("Payroll month is already approved.")

    def replace_lines(self, *, lines: list["PayrollMonthlyLine"]) -> None:
        self.lines.all().delete()
        if lines:
            PayrollMonthlyLine.objects.bulk_create(lines)

    def mark_closed(
        self,
        *,
        actor_user_id: int,
        rules_snapshot: dict,
        total_raw_xp: int,
        total_paid_xp: int,
        total_fix_salary: int,
        total_bonus_amount: int,
        total_allowance_amount: int,
        total_payout_amount: int,
        closed_at=None,
    ) -> None:
        self.status = PayrollMonthStatus.CLOSED
        self.closed_at = closed_at or timezone.now()
        self.closed_by_id = actor_user_id
        self.approved_at = None
        self.approved_by = None
        self.rules_snapshot = rules_snapshot
        self.total_raw_xp = total_raw_xp
        self.total_paid_xp = total_paid_xp
        self.total_fix_salary = total_fix_salary
        self.total_bonus_amount = total_bonus_amount
        self.total_allowance_amount = total_allowance_amount
        self.total_payout_amount = total_payout_amount
        self.save(
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

    def mark_approved(self, *, actor_user_id: int, approved_at=None) -> None:
        self.status = PayrollMonthStatus.APPROVED
        self.approved_at = approved_at or timezone.now()
        self.approved_by_id = actor_user_id
        self.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    def apply_allowance_release_delta(
        self,
        *,
        total_allowance_delta: int,
        manual_decision_payload: dict,
    ) -> None:
        self.total_allowance_amount = int(self.total_allowance_amount) + int(
            total_allowance_delta
        )
        self.total_payout_amount = int(self.total_payout_amount) + int(
            total_allowance_delta
        )
        rules_snapshot = dict(self.rules_snapshot or {})
        rules_snapshot_allowance_gate = dict(rules_snapshot.get("allowance_gate", {}))
        rules_snapshot_allowance_gate["manual_decision"] = manual_decision_payload
        rules_snapshot["allowance_gate"] = rules_snapshot_allowance_gate
        self.rules_snapshot = rules_snapshot
        self.save(
            update_fields=[
                "rules_snapshot",
                "total_allowance_amount",
                "total_payout_amount",
                "updated_at",
            ]
        )

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

    def release_gated_allowance(
        self,
        *,
        expected_allowance: int,
        actor_user_id: int,
        released_at,
    ) -> tuple[bool, int]:
        payload = dict(self.payload or {})
        if not payload.get("allowance_gated"):
            return False, 0
        if payload.get("allowance_override_released"):
            return False, 0

        delta = max(int(expected_allowance) - int(self.allowance_amount or 0), 0)
        self.allowance_amount = int(expected_allowance)
        self.total_amount = int(self.total_amount or 0) + int(delta)
        payload["allowance_gated"] = False
        payload["allowance_override_released"] = True
        payload["allowance_override_released_at"] = released_at.isoformat()
        payload["allowance_override_released_by"] = actor_user_id
        self.payload = payload
        self.save(
            update_fields=[
                "allowance_amount",
                "total_amount",
                "payload",
                "updated_at",
            ]
        )
        return True, int(delta)

    def __str__(self) -> str:
        return (
            f"PayrollMonthlyLine#{self.pk} month={self.payroll_monthly.month:%Y-%m} "
            f"user={self.user_id} paid_xp={self.paid_xp}"
        )


class PayrollAllowanceGateDecision(AppendOnlyModel):
    payroll_monthly = models.ForeignKey(
        PayrollMonthly,
        on_delete=models.CASCADE,
        related_name="allowance_gate_decisions",
    )
    decision = models.CharField(max_length=30, choices=PayrollAllowanceDecision)
    decided_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    affected_lines_count = models.PositiveIntegerField(default=0)
    total_allowance_delta = models.BigIntegerField(default=0)
    note = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["payroll_monthly", "created_at"]),
            models.Index(fields=["decision", "created_at"]),
        ]

    @classmethod
    def create_for_month(
        cls,
        *,
        payroll_monthly: PayrollMonthly,
        decision: str,
        decided_by_user_id: int,
        affected_lines_count: int,
        total_allowance_delta: int,
        note: str,
        gate_reasons: list[str],
        rules_version,
    ):
        return cls.objects.create(
            payroll_monthly=payroll_monthly,
            decision=decision,
            decided_by_id=decided_by_user_id,
            affected_lines_count=affected_lines_count,
            total_allowance_delta=total_allowance_delta,
            note=note,
            payload={
                "gate_reasons": gate_reasons,
                "rules_version": rules_version,
            },
        )

    def __str__(self) -> str:
        month_str = (
            self.payroll_monthly.month.strftime("%Y-%m")
            if self.payroll_monthly
            else "N/A"
        )
        return f"PayrollAllowanceGateDecision#{self.pk} month={month_str} decision={self.decision}"
