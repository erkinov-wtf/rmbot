from rest_framework import serializers

from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)
from inventory.services import InventoryItemService


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class InventoryItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItemCategory
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class InventoryItemPartSerializer(serializers.ModelSerializer):
    inventory_item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.domain.get_queryset(),
    )

    class Meta:
        model = InventoryItemPart
        fields = ("id", "inventory_item", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs):
        inventory_item = attrs.get("inventory_item")
        if inventory_item is None and self.instance is not None:
            inventory_item = self.instance.inventory_item

        name = attrs.get("name")
        if name is None and self.instance is not None:
            name = self.instance.name

        if inventory_item is None or not name:
            return attrs

        existing = InventoryItemPart.domain.get_queryset().filter(
            inventory_item=inventory_item,
            name__iexact=name,
        )
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                {
                    "name": (
                        "Part with this name already exists for the selected "
                        "inventory item."
                    )
                }
            )
        return attrs


class InventoryItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    serial_number = serializers.CharField()
    inventory = serializers.PrimaryKeyRelatedField(
        queryset=Inventory.domain.get_queryset(),
        required=False,
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItemCategory.domain.get_queryset(),
        required=False,
    )
    parts = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "name",
            "serial_number",
            "inventory",
            "category",
            "parts",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_serial_number(self, value: str) -> str:
        normalized_serial_number = InventoryItemService.normalize_serial_number(value)

        existing = InventoryItem.all_objects.filter(
            serial_number__iexact=normalized_serial_number
        )
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                "Inventory item with this serial_number already exists."
            )
        return normalized_serial_number

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get("name"):
                attrs["name"] = attrs.get("serial_number")
            attrs.setdefault("inventory", InventoryItemService.get_default_inventory())
            attrs.setdefault("category", InventoryItemService.get_default_category())
        return attrs
