from django.db import models

from core.models import AppendOnlyModel, TimestampedModel


class RulesConfigAction(models.TextChoices):
    BOOTSTRAP = "bootstrap", "Bootstrap"
    UPDATE = "update", "Update"
    ROLLBACK = "rollback", "Rollback"


class RulesConfigVersion(AppendOnlyModel):
    version = models.PositiveIntegerField(unique=True, db_index=True)
    action = models.CharField(
        max_length=20, choices=RulesConfigAction.choices, db_index=True
    )
    config = models.JSONField(default=dict)
    diff = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, db_index=True)
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    source_version = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"RulesConfigVersion#{self.version} [{self.action}]"


class RulesConfigState(TimestampedModel):
    singleton = models.BooleanField(default=True, unique=True)
    active_version = models.ForeignKey(
        RulesConfigVersion, on_delete=models.PROTECT, related_name="+"
    )
    cache_key = models.CharField(max_length=64, db_index=True)

    def __str__(self) -> str:
        return f"RulesConfigState active=v{self.active_version.version}"
