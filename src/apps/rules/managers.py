from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models import Max


class RulesConfigVersionQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related("created_by", "source_version")

    def by_version_number(self, *, version_number: int):
        return self.filter(version=version_number)

    def ordered_latest(self):
        return self.order_by("-version")


class RulesConfigVersionDomainManager(
    models.Manager.from_queryset(RulesConfigVersionQuerySet)
):
    def next_version_number(self) -> int:
        current_version = (
            self.get_queryset().aggregate(max_version=Max("version")).get("max_version")
            or 0
        )
        return int(current_version) + 1

    def create_version_entry(
        self,
        *,
        action: str,
        config: dict[str, Any],
        diff: dict[str, Any],
        checksum: str,
        reason: str,
        created_by_id: int | None,
        source_version,
    ):
        return self.create(
            version=self.next_version_number(),
            action=action,
            config=config,
            diff=diff,
            checksum=checksum,
            reason=reason,
            created_by_id=created_by_id,
            source_version=source_version,
        )

    def get_by_version_number(self, *, version_number: int):
        return (
            self.get_queryset().by_version_number(version_number=version_number).first()
        )

    def latest_versions(self, *, limit: int = 50):
        capped_limit = max(1, min(limit, 200))
        return list(self.get_queryset().with_related().ordered_latest()[:capped_limit])


class RulesConfigStateDomainManager(models.Manager):
    def get_singleton_for_update(self):
        return (
            self.get_queryset()
            .select_for_update()
            .select_related("active_version")
            .first()
        )

    def create_singleton(self, *, active_version, cache_key: str):
        return self.create(
            singleton=True,
            active_version=active_version,
            cache_key=cache_key,
        )

    def get_with_related(self, *, state_id: int):
        return (
            self.get_queryset()
            .select_related("active_version", "active_version__created_by")
            .get(pk=state_id)
        )
