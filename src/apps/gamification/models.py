from django.db import IntegrityError, models

from core.models import AppendOnlyManager, AppendOnlyModel
from core.utils.constants import EmployeeLevel, XPLedgerEntryType


class XPLedgerManager(AppendOnlyManager):
    def append_entry(
        self,
        *,
        user_id: int,
        amount: int,
        entry_type: str,
        reference: str,
        description: str | None = None,
        payload: dict | None = None,
    ):
        try:
            entry = self.create(
                user_id=user_id,
                amount=amount,
                entry_type=entry_type,
                reference=reference,
                description=description,
                payload=payload or {},
            )
            return entry, True
        except IntegrityError:
            existing = self.get(reference=reference)
            return existing, False


class XPLedger(AppendOnlyModel):
    objects = XPLedgerManager()

    user = models.ForeignKey(
        "account.User", on_delete=models.PROTECT, related_name="xp_ledger_entries"
    )
    amount = models.IntegerField()
    entry_type = models.CharField(
        max_length=50, choices=XPLedgerEntryType, db_index=True
    )
    reference = models.CharField(max_length=120, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["entry_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"XPLedger#{self.pk} user={self.user_id} amount={self.amount} ({self.entry_type})"


class WeeklyLevelEvaluation(AppendOnlyModel):
    user = models.ForeignKey(
        "account.User",
        on_delete=models.PROTECT,
        related_name="weekly_level_evaluations",
    )
    week_start = models.DateField(db_index=True)
    week_end = models.DateField(db_index=True)
    raw_xp = models.IntegerField(default=0)
    previous_level = models.PositiveSmallIntegerField(choices=EmployeeLevel)
    new_level = models.PositiveSmallIntegerField(choices=EmployeeLevel)
    is_level_up = models.BooleanField(default=False)
    rules_version = models.PositiveIntegerField(default=1)
    rules_cache_key = models.CharField(max_length=64, blank=True, default="")
    evaluated_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["week_start", "user"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["is_level_up", "week_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "week_start"],
                name="unique_weekly_level_evaluation_per_user_week",
            )
        ]

    def __str__(self) -> str:
        return (
            f"WeeklyLevelEvaluation#{self.pk} user={self.user_id} "
            f"{self.previous_level}->{self.new_level} {self.week_start}"
        )


class LevelUpCouponEvent(AppendOnlyModel):
    user = models.ForeignKey(
        "account.User",
        on_delete=models.PROTECT,
        related_name="level_up_coupon_events",
    )
    evaluation = models.OneToOneField(
        WeeklyLevelEvaluation,
        on_delete=models.PROTECT,
        related_name="coupon_event",
    )
    week_start = models.DateField(db_index=True)
    amount = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, default="UZS")
    reference = models.CharField(max_length=120, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    issued_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "week_start"]),
            models.Index(fields=["week_start", "created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"LevelUpCouponEvent#{self.pk} user={self.user_id} amount={self.amount} "
            f"{self.currency} {self.week_start}"
        )
