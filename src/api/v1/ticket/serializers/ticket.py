from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from inventory.models import InventoryItem
from inventory.services import InventoryItemService
from ticket.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    inventory_item = serializers.PrimaryKeyRelatedField(read_only=True)
    serial_number = serializers.CharField(write_only=True, required=True)
    confirm_create_inventory_item = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    inventory_item_creation_reason = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
    )
    checklist_snapshot = serializers.JSONField(required=True)
    srt_total_minutes = serializers.IntegerField(required=True)
    approve_srt = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "inventory_item",
            "serial_number",
            "confirm_create_inventory_item",
            "inventory_item_creation_reason",
            "master",
            "technician",
            "title",
            "checklist_snapshot",
            "srt_total_minutes",
            "srt_approved_by",
            "srt_approved_at",
            "approve_srt",
            "flag_minutes",
            "status",
            "assigned_at",
            "started_at",
            "done_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "inventory_item",
            "master",
            "status",
            "assigned_at",
            "started_at",
            "done_at",
            "created_at",
            "updated_at",
            "srt_approved_by",
            "srt_approved_at",
        )

    def validate_checklist_snapshot(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "checklist_snapshot must be an array of checklist items."
            )
        if len(value) < 10:
            raise serializers.ValidationError(
                "checklist_snapshot must include at least 10 items."
            )
        invalid_indexes = [
            idx
            for idx, item in enumerate(value)
            if not self._is_valid_checklist_item(item)
        ]
        if invalid_indexes:
            first_bad = invalid_indexes[0]
            raise serializers.ValidationError(
                f"checklist_snapshot[{first_bad}] must be a non-empty task string or object with non-empty 'task'."
            )
        return value

    def validate_srt_total_minutes(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError(
                "srt_total_minutes must be greater than 0."
            )
        return value

    def validate(self, attrs):
        raw_serial_number = attrs.get("serial_number", "")
        serial_number = InventoryItemService.normalize_serial_number(raw_serial_number)
        if not InventoryItemService.is_valid_serial_number(serial_number):
            raise serializers.ValidationError(
                {
                    "serial_number": (
                        "serial_number must match pattern RM-[A-Z0-9-]{4,29}."
                    )
                }
            )
        attrs["serial_number"] = serial_number

        inventory_item = InventoryItemService.get_by_serial_number(serial_number)
        if inventory_item is None:
            archived_inventory_item = InventoryItem.all_objects.filter(
                serial_number__iexact=serial_number,
                deleted_at__isnull=False,
            ).first()
            if archived_inventory_item is not None:
                raise serializers.ValidationError(
                    {
                        "serial_number": (
                            f"Inventory item '{serial_number}' is archived. Restore "
                            "the existing item before creating a ticket."
                        )
                    }
                )

            suggestions = InventoryItemService.suggest_serial_numbers(serial_number)
            if not attrs.get("confirm_create_inventory_item"):
                message = (
                    f"Inventory item '{serial_number}' was not found. "
                    "Set confirm_create_inventory_item=true and provide "
                    "inventory_item_creation_reason to create it."
                )
                if suggestions:
                    message += f" Closest matches: {', '.join(suggestions)}."
                raise serializers.ValidationError({"serial_number": message})
            if not attrs.get("inventory_item_creation_reason"):
                raise serializers.ValidationError(
                    {
                        "inventory_item_creation_reason": (
                            "inventory_item_creation_reason is required when "
                            "confirm_create_inventory_item=true."
                        )
                    }
                )
            attrs["_create_inventory_item"] = True
            attrs["_inventory_item_creation_reason"] = attrs[
                "inventory_item_creation_reason"
            ].strip()
        else:
            attrs["inventory_item"] = inventory_item
            attrs["_create_inventory_item"] = False
            attrs["_inventory_item_creation_reason"] = None
            if Ticket.domain.has_active_for_inventory_item(
                inventory_item=inventory_item
            ):
                raise serializers.ValidationError(
                    {
                        "serial_number": (
                            "An active ticket already exists for this inventory item."
                        )
                    }
                )
        if not attrs.get("approve_srt"):
            raise serializers.ValidationError(
                {"approve_srt": "SRT must be approved by Master during intake."}
            )
        return attrs

    def create(self, validated_data):
        serial_number = validated_data.pop("serial_number")
        validated_data.pop("confirm_create_inventory_item", None)
        validated_data.pop("inventory_item_creation_reason", None)
        create_inventory_item = bool(
            validated_data.pop("_create_inventory_item", False)
        )
        inventory_item_creation_reason = validated_data.pop(
            "_inventory_item_creation_reason", None
        )

        self._resolved_serial_number = serial_number
        self._inventory_item_created_during_intake = False
        self._inventory_item_creation_reason = None

        if create_inventory_item:
            default_inventory = InventoryItemService.get_default_inventory()
            default_category = InventoryItemService.get_default_category()
            try:
                inventory_item, created = InventoryItem.objects.get_or_create(
                    serial_number=serial_number,
                    defaults={
                        "name": serial_number,
                        "inventory": default_inventory,
                        "category": default_category,
                        "is_active": True,
                    },
                )
            except IntegrityError:
                archived_inventory_item = InventoryItem.all_objects.filter(
                    serial_number__iexact=serial_number,
                    deleted_at__isnull=False,
                ).first()
                if archived_inventory_item is not None:
                    raise serializers.ValidationError(
                        {
                            "serial_number": (
                                f"Inventory item '{serial_number}' is archived. "
                                "Restore the existing item before creating a ticket."
                            )
                        }
                    ) from None

                inventory_item = InventoryItemService.get_by_serial_number(
                    serial_number
                )
                if inventory_item is None:
                    raise serializers.ValidationError(
                        {
                            "serial_number": (
                                "serial_number conflict detected while creating the "
                                "inventory item. Retry the request."
                            )
                        }
                    ) from None
                created = False

            if Ticket.domain.has_active_for_inventory_item(
                inventory_item=inventory_item
            ):
                raise serializers.ValidationError(
                    {
                        "serial_number": (
                            "An active ticket already exists for this inventory item."
                        )
                    }
                )
            validated_data["inventory_item"] = inventory_item
            self._inventory_item_created_during_intake = created
            self._inventory_item_creation_reason = inventory_item_creation_reason

        validated_data.pop("approve_srt", None)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["srt_approved_by"] = request.user
            validated_data["srt_approved_at"] = timezone.now()
        return super().create(validated_data)

    def get_intake_metadata(self) -> dict[str, object]:
        return {
            "serial_number": getattr(self, "_resolved_serial_number", None),
            "inventory_item_created_during_intake": bool(
                getattr(self, "_inventory_item_created_during_intake", False)
            ),
            "inventory_item_creation_reason": getattr(
                self,
                "_inventory_item_creation_reason",
                None,
            ),
        }

    @staticmethod
    def _is_valid_checklist_item(item) -> bool:
        if isinstance(item, str):
            return bool(item.strip())
        if isinstance(item, dict):
            task = item.get("task")
            return isinstance(task, str) and bool(task.strip())
        return False
