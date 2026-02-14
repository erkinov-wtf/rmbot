from __future__ import annotations

from django.db import models

from core.models import AppendOnlyModel, TimestampedModel
from rules.managers import (
    RulesConfigStateDomainManager,
    RulesConfigVersionDomainManager,
)


class RulesConfigAction(models.TextChoices):
    BOOTSTRAP = "bootstrap", "Bootstrap"
    UPDATE = "update", "Update"
    ROLLBACK = "rollback", "Rollback"


class RulesConfigVersion(AppendOnlyModel):
    domain = RulesConfigVersionDomainManager()

    version = models.PositiveIntegerField(unique=True, db_index=True)
    action = models.CharField(max_length=20, choices=RulesConfigAction, db_index=True)
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
    domain = RulesConfigStateDomainManager()

    singleton = models.BooleanField(default=True, unique=True)
    active_version = models.ForeignKey(
        RulesConfigVersion, on_delete=models.PROTECT, related_name="+"
    )
    cache_key = models.CharField(max_length=64, db_index=True)

    def activate_version(
        self, *, active_version: RulesConfigVersion, cache_key: str
    ) -> None:
        self.active_version = active_version
        self.cache_key = cache_key
        self.save(update_fields=["active_version", "cache_key", "updated_at"])

    def __str__(self) -> str:
        return f"RulesConfigState active=v{self.active_version.version}"
