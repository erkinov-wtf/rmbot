from __future__ import annotations

import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)


class InventoryItemService:
    SERIAL_NUMBER_PATTERN = re.compile(r"^RM-[A-Z0-9-]{4,29}$")
    SUGGESTION_MIN_CHARS = 2
    SUGGESTION_LIMIT = 5
    LIST_SEARCH_SUGGESTION_LIMIT = 20

    @classmethod
    def normalize_serial_number(cls, raw_serial_number: str) -> str:
        value = str(raw_serial_number or "")
        value = re.sub(r"\s+", "", value)
        return value.upper()

    @classmethod
    def is_valid_serial_number(cls, serial_number: str) -> bool:
        normalized = cls.normalize_serial_number(serial_number)
        return bool(cls.SERIAL_NUMBER_PATTERN.fullmatch(normalized))

    @classmethod
    def get_by_serial_number(cls, serial_number: str) -> InventoryItem | None:
        normalized = cls.normalize_serial_number(serial_number)
        return InventoryItem.domain.find_by_serial_number(normalized)

    @classmethod
    def suggest_serial_numbers(
        cls,
        query: str,
        *,
        min_chars: int | None = None,
        limit: int | None = None,
    ) -> list[str]:
        normalized_query = cls.normalize_serial_number(query)
        min_length = min_chars if min_chars is not None else cls.SUGGESTION_MIN_CHARS
        max_items = limit if limit is not None else cls.SUGGESTION_LIMIT

        if len(normalized_query) < min_length:
            return []

        return InventoryItem.domain.suggest_serial_numbers(
            query=normalized_query,
            limit=max_items,
        )

    @staticmethod
    def get_default_inventory() -> Inventory:
        return Inventory.domain.get_default()

    @staticmethod
    def get_default_category() -> InventoryItemCategory:
        return InventoryItemCategory.domain.get_default()

    @classmethod
    def filter_inventory_items(
        cls,
        *,
        queryset,
        q: str | None = None,
        serial_number: str | None = None,
        inventory_id: int | None = None,
        category_id: int | None = None,
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

        if serial_number:
            filtered = filtered.by_serial_number(serial_number)

        if q:
            suggestions = cls.suggest_serial_numbers(
                q,
                limit=cls.LIST_SEARCH_SUGGESTION_LIMIT,
            )
            filtered = filtered.filter(
                Q(serial_number__icontains=q) | Q(serial_number__in=suggestions)
            )

        if inventory_id:
            filtered = filtered.with_inventory(inventory_id)
        if category_id:
            filtered = filtered.with_category(category_id)
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


class InventoryCategoryService:
    CATEGORY_HAS_ITEMS_ERROR = (
        "Cannot delete category while inventory items are assigned to it."
    )

    @classmethod
    @transaction.atomic
    def delete_category(cls, *, category: InventoryItemCategory) -> None:
        has_items = (
            InventoryItem.domain.get_queryset().filter(category_id=category.id).exists()
        )
        if has_items:
            raise ValueError(cls.CATEGORY_HAS_ITEMS_ERROR)

        now_dt = timezone.now()
        InventoryItemPart.domain.get_queryset().filter(category_id=category.id).update(
            deleted_at=now_dt,
            updated_at=now_dt,
        )

        category.delete()
