from django.db import models

from core.models import AppendOnlyModel
from core.utils.constants import XPLedgerEntryType


class XPLedger(AppendOnlyModel):
    user = models.ForeignKey("account.User", on_delete=models.PROTECT, related_name="xp_ledger_entries")
    amount = models.IntegerField()
    entry_type = models.CharField(max_length=50, choices=XPLedgerEntryType.choices, db_index=True)
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
