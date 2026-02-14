from __future__ import annotations

import difflib

from django.db import models

from core.utils.constants import BikeStatus


class BikeQuerySet(models.QuerySet):
    def active_fleet(self):
        return self.filter(is_active=True).exclude(status=BikeStatus.WRITE_OFF)

    def ready(self):
        return self.filter(status=BikeStatus.READY)

    def by_code(self, bike_code: str):
        return self.filter(bike_code__iexact=bike_code)


class BikeDomainManager(models.Manager.from_queryset(BikeQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def find_by_code(self, bike_code: str):
        return self.get_queryset().by_code(bike_code).order_by("id").first()

    def ready_active_count(self) -> int:
        return self.get_queryset().active_fleet().ready().count()

    def suggest_codes(self, *, query: str, limit: int) -> list[str]:
        starts_with = list(
            self.get_queryset()
            .filter(bike_code__istartswith=query)
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[:limit]
        )
        if len(starts_with) >= limit:
            return starts_with

        contains_codes = list(
            self.get_queryset()
            .filter(bike_code__icontains=query)
            .exclude(bike_code__in=starts_with)
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[: limit - len(starts_with)]
        )
        suggestions = starts_with + contains_codes
        if len(suggestions) >= limit:
            return suggestions

        candidate_codes = list(
            self.get_queryset()
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[:500]
        )
        fuzzy_codes = difflib.get_close_matches(
            query, candidate_codes, n=limit, cutoff=0.6
        )
        for code in fuzzy_codes:
            if code in suggestions:
                continue
            suggestions.append(code)
            if len(suggestions) >= limit:
                break
        return suggestions
