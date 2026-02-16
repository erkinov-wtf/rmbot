from django.db import models

from core.models import SoftDeleteModel, TimestampedModel
from core.utils.constants import InventoryItemStatus
from inventory import managers


class Inventory(TimestampedModel, SoftDeleteModel):
    domain = managers.InventoryDomainManager()

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        indexes = [models.Index(fields=["name"], name="inv_inventory_name_idx")]

    def __str__(self) -> str:
        return self.name


class InventoryItemCategory(TimestampedModel, SoftDeleteModel):
    domain = managers.InventoryItemCategoryDomainManager()

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name_plural = "Inventory item categories"
        indexes = [models.Index(fields=["name"], name="inv_item_category_name_idx")]

    def __str__(self) -> str:
        return self.name


class InventoryItemPart(TimestampedModel, SoftDeleteModel):
    domain = managers.InventoryItemPartDomainManager()

    inventory_item = models.ForeignKey(
        "InventoryItem",
        on_delete=models.CASCADE,
        related_name="parts",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(
                fields=["inventory_item", "name"],
                name="inv_item_part_item_name_idx",
            ),
            models.Index(fields=["name"], name="inv_item_part_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["inventory_item", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="inv_item_part_unique_name_per_item",
            )
        ]

    def __str__(self) -> str:
        return self.name


class InventoryItem(TimestampedModel, SoftDeleteModel):
    domain = managers.InventoryItemDomainManager()

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.PROTECT,
        related_name="items",
    )
    name = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=32, unique=True, db_index=True)
    category = models.ForeignKey(
        InventoryItemCategory,
        on_delete=models.PROTECT,
        related_name="items",
    )
    status = models.CharField(
        max_length=20,
        choices=InventoryItemStatus,
        default=InventoryItemStatus.READY,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "is_active"],
                name="inv_item_status_active_idx",
            ),
            models.Index(
                fields=["inventory", "category"],
                name="inv_item_inv_cat_idx",
            ),
        ]

    def mark_in_service(self) -> None:
        if self.status == InventoryItemStatus.IN_SERVICE:
            return
        self.status = InventoryItemStatus.IN_SERVICE
        self.save(update_fields=["status"])

    def mark_ready(self) -> None:
        if self.status == InventoryItemStatus.READY:
            return
        self.status = InventoryItemStatus.READY
        self.save(update_fields=["status"])

    def __str__(self) -> str:
        return f"{self.serial_number} ({self.status})"
