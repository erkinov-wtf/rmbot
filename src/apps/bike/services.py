from __future__ import annotations

import difflib
import re

from bike.models import Bike


class BikeService:
    BIKE_CODE_PATTERN = re.compile(r"^RM-[A-Z0-9-]{4,29}$")
    SUGGESTION_MIN_CHARS = 2
    SUGGESTION_LIMIT = 5

    @classmethod
    def normalize_bike_code(cls, raw_code: str) -> str:
        value = str(raw_code or "")
        value = re.sub(r"\s+", "", value)
        return value.upper()

    @classmethod
    def is_valid_bike_code(cls, bike_code: str) -> bool:
        normalized = cls.normalize_bike_code(bike_code)
        return bool(cls.BIKE_CODE_PATTERN.fullmatch(normalized))

    @classmethod
    def get_by_code(cls, bike_code: str) -> Bike | None:
        normalized = cls.normalize_bike_code(bike_code)
        return (
            Bike.objects.filter(deleted_at__isnull=True, bike_code__iexact=normalized)
            .order_by("id")
            .first()
        )

    @classmethod
    def suggest_codes(
        cls,
        query: str,
        *,
        min_chars: int | None = None,
        limit: int | None = None,
    ) -> list[str]:
        normalized_query = cls.normalize_bike_code(query)
        min_length = min_chars if min_chars is not None else cls.SUGGESTION_MIN_CHARS
        max_items = limit if limit is not None else cls.SUGGESTION_LIMIT

        if len(normalized_query) < min_length:
            return []

        starts_with = list(
            Bike.objects.filter(
                deleted_at__isnull=True,
                bike_code__istartswith=normalized_query,
            )
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[:max_items]
        )
        if len(starts_with) >= max_items:
            return starts_with

        contains_codes = list(
            Bike.objects.filter(
                deleted_at__isnull=True,
                bike_code__icontains=normalized_query,
            )
            .exclude(bike_code__in=starts_with)
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[: max_items - len(starts_with)]
        )
        suggestions = starts_with + contains_codes
        if len(suggestions) >= max_items:
            return suggestions

        candidate_codes = list(
            Bike.objects.filter(deleted_at__isnull=True)
            .order_by("bike_code")
            .values_list("bike_code", flat=True)[:500]
        )
        fuzzy_codes = difflib.get_close_matches(
            normalized_query,
            candidate_codes,
            n=max_items,
            cutoff=0.6,
        )
        for code in fuzzy_codes:
            if code not in suggestions:
                suggestions.append(code)
            if len(suggestions) >= max_items:
                break

        return suggestions
