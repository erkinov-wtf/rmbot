from django.contrib import admin

from core.admin import BaseModelAdmin
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)


@admin.register(Inventory)
class InventoryAdmin(BaseModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(InventoryItemCategory)
class InventoryItemCategoryAdmin(BaseModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(InventoryItemPart)
class InventoryItemPartAdmin(BaseModelAdmin):
    list_display = ("id", "name", "category", "inventory_item", "created_at")
    search_fields = (
        "name",
        "category__name",
        "inventory_item__serial_number",
        "inventory_item__name",
    )
    list_filter = ("category", "inventory_item")


@admin.register(InventoryItem)
class InventoryItemAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "serial_number",
        "name",
        "inventory",
        "category",
        "status",
        "is_active",
        "created_at",
    )
    search_fields = ("serial_number", "name", "inventory__name", "category__name")
    list_filter = ("status", "is_active", "inventory", "category")
