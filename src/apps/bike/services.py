from __future__ import annotations

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
