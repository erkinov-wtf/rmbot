from __future__ import annotations

import difflib

from django.db import IntegrityError, models, transaction

from core.utils.constants import InventoryItemStatus, TicketStatus

ACTIVE_TICKET_STATUSES = (
    TicketStatus.NEW,
    TicketStatus.ASSIGNED,
    TicketStatus.IN_PROGRESS,
    TicketStatus.WAITING_QC,
    TicketStatus.REWORK,
)

DEFAULT_INVENTORY_NAME = "Default Inventory"


class InventoryQuerySet(models.QuerySet):
    def by_name(self, name: str):
        return self.filter(name__iexact=name)


class InventoryDomainManager(models.Manager.from_queryset(InventoryQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def get_default(self):
        model_cls = self.model
        existing = (
            model_cls.all_objects.filter(name__iexact=DEFAULT_INVENTORY_NAME)
            .order_by("id")
            .first()
        )
        if existing is not None:
            if existing.deleted_at is not None:
                model_cls.all_objects.filter(pk=existing.pk).update(deleted_at=None)
                existing.deleted_at = None
            return existing

        try:
            with transaction.atomic():
                return self.create(name=DEFAULT_INVENTORY_NAME)
        except IntegrityError:
            fallback = (
                model_cls.all_objects.filter(name__iexact=DEFAULT_INVENTORY_NAME)
                .order_by("id")
                .first()
            )
            if fallback is None:
                raise
            if fallback.deleted_at is not None:
                model_cls.all_objects.filter(pk=fallback.pk).update(deleted_at=None)
                fallback.deleted_at = None
            return fallback


class InventoryItemCategoryQuerySet(models.QuerySet):
    def by_name(self, name: str):
        return self.filter(name__iexact=name)


class InventoryItemCategoryDomainManager(
    models.Manager.from_queryset(InventoryItemCategoryQuerySet)
):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def get_default(self):
        category = self.get_queryset().order_by("id").first()
        if category is None:
            raise self.model.DoesNotExist("No inventory category exists.")
        return category


class InventoryItemPartQuerySet(models.QuerySet):
    def with_category(self, category_id: int):
        return self.filter(category_id=category_id)

    def with_inventory_item(self, inventory_item_id: int):
        return self.filter(inventory_item_id=inventory_item_id)


class InventoryItemPartDomainManager(
    models.Manager.from_queryset(InventoryItemPartQuerySet)
):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class InventoryItemQuerySet(models.QuerySet):
    def active_fleet(self):
        return self.filter(is_active=True).exclude(status=InventoryItemStatus.WRITE_OFF)

    def ready(self):
        return self.filter(status=InventoryItemStatus.READY)

    def by_serial_number(self, serial_number: str):
        return self.filter(serial_number__iexact=serial_number)

    def by_serial_number_contains(self, query: str):
        return self.filter(serial_number__icontains=query)

    def with_inventory(self, inventory_id: int):
        return self.filter(inventory_id=inventory_id)

    def with_category(self, category_id: int):
        return self.filter(category_id=category_id)

    def with_status(self, status: str):
        return self.filter(status=status)

    def with_is_active(self, is_active: bool):
        return self.filter(is_active=is_active)

    def created_from(self, value):
        return self.filter(created_at__date__gte=value)

    def created_to(self, value):
        return self.filter(created_at__date__lte=value)

    def updated_from(self, value):
        return self.filter(updated_at__date__gte=value)

    def updated_to(self, value):
        return self.filter(updated_at__date__lte=value)

    def with_active_ticket(self):
        return self.filter(
            tickets__status__in=ACTIVE_TICKET_STATUSES,
            tickets__deleted_at__isnull=True,
        ).distinct()

    def without_active_ticket(self):
        return self.exclude(
            tickets__status__in=ACTIVE_TICKET_STATUSES,
            tickets__deleted_at__isnull=True,
        ).distinct()


class InventoryItemDomainManager(models.Manager.from_queryset(InventoryItemQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def find_by_serial_number(self, serial_number: str):
        return (
            self.get_queryset().by_serial_number(serial_number).order_by("id").first()
        )

    def ready_active_count(self) -> int:
        return self.get_queryset().active_fleet().ready().count()

    def suggest_serial_numbers(self, *, query: str, limit: int) -> list[str]:
        starts_with = list(
            self.get_queryset()
            .filter(serial_number__istartswith=query)
            .order_by("serial_number")
            .values_list("serial_number", flat=True)[:limit]
        )
        if len(starts_with) >= limit:
            return starts_with

        contains_serials = list(
            self.get_queryset()
            .filter(serial_number__icontains=query)
            .exclude(serial_number__in=starts_with)
            .order_by("serial_number")
            .values_list("serial_number", flat=True)[: limit - len(starts_with)]
        )
        suggestions = starts_with + contains_serials
        if len(suggestions) >= limit:
            return suggestions

        candidate_serials = list(
            self.get_queryset()
            .order_by("serial_number")
            .values_list("serial_number", flat=True)[:500]
        )
        fuzzy_serials = difflib.get_close_matches(
            query,
            candidate_serials,
            n=limit,
            cutoff=0.6,
        )
        for serial in fuzzy_serials:
            if serial in suggestions:
                continue
            suggestions.append(serial)
            if len(suggestions) >= limit:
                break
        return suggestions
