from __future__ import annotations

import re

from django.db.models import Q

from bike.models import Bike


class BikeService:
    BIKE_CODE_PATTERN = re.compile(r"^RM-[A-Z0-9-]{4,29}$")
    SUGGESTION_MIN_CHARS = 2
    SUGGESTION_LIMIT = 5
    LIST_SEARCH_SUGGESTION_LIMIT = 20

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
        return Bike.domain.find_by_code(normalized)

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

        return Bike.domain.suggest_codes(query=normalized_query, limit=max_items)

    @classmethod
    def filter_bikes(
        cls,
        *,
        queryset,
        q: str | None = None,
        bike_code: str | None = None,
        status: str | None = None,
        is_active: bool | None = None,
        has_active_ticket: bool | None = None,
        created_from=None,
        created_to=None,
        updated_from=None,
        updated_to=None,
        ordering: str = "-created_at",
    ):
        filtered = queryset

        if bike_code:
            filtered = filtered.by_code(bike_code)

        if q:
            suggestions = cls.suggest_codes(q, limit=cls.LIST_SEARCH_SUGGESTION_LIMIT)
            filtered = filtered.filter(
                Q(bike_code__icontains=q) | Q(bike_code__in=suggestions)
            )

        if status:
            filtered = filtered.with_status(status)
        if is_active is not None:
            filtered = filtered.with_is_active(is_active)
        if has_active_ticket is not None:
            filtered = (
                filtered.with_active_ticket()
                if has_active_ticket
                else filtered.without_active_ticket()
            )
        if created_from is not None:
            filtered = filtered.created_from(created_from)
        if created_to is not None:
            filtered = filtered.created_to(created_to)
        if updated_from is not None:
            filtered = filtered.updated_from(updated_from)
        if updated_to is not None:
            filtered = filtered.updated_to(updated_to)

        return filtered.order_by(ordering, "id")
