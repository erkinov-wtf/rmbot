import math

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from core.utils.constants import RoleSlug, TicketColor, TicketStatus
from inventory.models import InventoryItem, InventoryItemCategory, InventoryItemPart
from inventory.services import InventoryItemService
from rules.services import RulesService
from ticket.models import Ticket, TicketPartSpec


class TicketPartSpecInputSerializer(serializers.Serializer):
    part_id = serializers.IntegerField(min_value=1)
    color = serializers.ChoiceField(choices=TicketColor.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    minutes = serializers.IntegerField(min_value=1)

    def validate_comment(self, value: str) -> str:
        return value.strip()


class TicketPartSpecSerializer(serializers.ModelSerializer):
    part_id = serializers.IntegerField(source="inventory_item_part_id", read_only=True)
    part_name = serializers.CharField(source="inventory_item_part.name", read_only=True)

    class Meta:
        model = TicketPartSpec
        fields = (
            "id",
            "part_id",
            "part_name",
            "color",
            "comment",
            "minutes",
            "created_at",
            "updated_at",
        )


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
    technician = serializers.PrimaryKeyRelatedField(read_only=True)
    part_specs = TicketPartSpecInputSerializer(
        many=True, write_only=True, required=True
    )
    ticket_parts = TicketPartSpecSerializer(
        source="part_specs", many=True, read_only=True
    )
    total_duration = serializers.IntegerField(read_only=True)
    flag_minutes = serializers.IntegerField(read_only=True)
    xp_amount = serializers.IntegerField(required=False, min_value=0)
    flag_color = serializers.ChoiceField(choices=TicketColor.choices, required=False)
    is_manual = serializers.BooleanField(read_only=True)
    approve_review = serializers.BooleanField(
        write_only=True, required=False, default=False
    )
    master_name = serializers.SerializerMethodField(read_only=True)
    technician_name = serializers.SerializerMethodField(read_only=True)
    approved_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "inventory_item",
            "serial_number",
            "confirm_create_inventory_item",
            "inventory_item_creation_reason",
            "master",
            "master_name",
            "technician",
            "technician_name",
            "title",
            "part_specs",
            "ticket_parts",
            "total_duration",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "approve_review",
            "flag_minutes",
            "flag_color",
            "xp_amount",
            "is_manual",
            "status",
            "assigned_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "inventory_item",
            "master",
            "technician",
            "status",
            "assigned_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "approved_by",
            "approved_at",
            "total_duration",
            "flag_minutes",
            "is_manual",
            "ticket_parts",
            "master_name",
            "technician_name",
            "approved_by_name",
        )

    @staticmethod
    def _user_display_name(user) -> str | None:
        if not user:
            return None
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return full_name or user.username

    def get_master_name(self, obj: Ticket) -> str | None:
        return self._user_display_name(obj.master)

    def get_technician_name(self, obj: Ticket) -> str | None:
        return self._user_display_name(obj.technician)

    def get_approved_by_name(self, obj: Ticket) -> str | None:
        return self._user_display_name(obj.approved_by)

    def validate(self, attrs):
        request = self.context.get("request")
        if attrs.get("approve_review"):
            if not request or not request.user or not request.user.is_authenticated:
                raise serializers.ValidationError(
                    {
                        "approve_review": (
                            "Authenticated admin user is required for approve_review."
                        )
                    }
                )
            if not request.user.roles.filter(
                slug__in=[RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER],
                deleted_at__isnull=True,
            ).exists():
                raise serializers.ValidationError(
                    {"approve_review": "Only admin users can approve ticket review."}
                )

        raw_serial_number = attrs.get("serial_number", "")
        serial_number = InventoryItemService.normalize_serial_number(raw_serial_number)
        attrs["serial_number"] = serial_number

        inventory_item = InventoryItemService.get_by_serial_number(serial_number)
        if inventory_item is None:
            if not InventoryItemService.is_valid_serial_number(serial_number):
                raise serializers.ValidationError(
                    {
                        "serial_number": (
                            "serial_number must match pattern RM-[A-Z0-9-]{4,29}."
                        )
                    }
                )

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

        raw_part_specs = attrs.get("part_specs") or []
        (
            normalized_specs,
            total_minutes,
            part_category_id,
        ) = self._resolve_part_specs(
            part_specs=raw_part_specs,
            inventory_item=inventory_item,
            creating_inventory_item=bool(attrs.get("_create_inventory_item")),
        )
        attrs["_part_specs"] = normalized_specs
        attrs["_total_minutes"] = total_minutes
        attrs["_part_category_id"] = part_category_id

        auto_flag_color = Ticket.flag_color_from_minutes(total_minutes=total_minutes)
        xp_divisor = self._ticket_xp_divisor()
        auto_xp_amount = math.ceil(total_minutes / xp_divisor)

        manual_flag_color = attrs.get("flag_color")
        manual_xp_amount = attrs.get("xp_amount")
        if manual_flag_color is not None or manual_xp_amount is not None:
            if manual_flag_color is None or manual_xp_amount is None:
                raise serializers.ValidationError(
                    {
                        "flag_color": (
                            "Manual override requires both flag_color and xp_amount."
                        )
                    }
                )
            attrs["flag_color"] = manual_flag_color
            attrs["xp_amount"] = int(manual_xp_amount)
            attrs["is_manual"] = True
        else:
            attrs["flag_color"] = auto_flag_color
            attrs["xp_amount"] = auto_xp_amount
            attrs["is_manual"] = False

        attrs["total_duration"] = total_minutes
        attrs["flag_minutes"] = total_minutes
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
        part_specs = validated_data.pop("_part_specs", [])
        total_minutes = int(validated_data.pop("_total_minutes", 0) or 0)
        part_category_id = validated_data.pop("_part_category_id", None)
        approve_review = bool(validated_data.pop("approve_review", False))
        validated_data.pop("part_specs", None)

        self._resolved_serial_number = serial_number
        self._inventory_item_created_during_intake = False
        self._inventory_item_creation_reason = None
        self._resolved_total_minutes = total_minutes
        self._resolved_part_specs_count = len(part_specs)

        if create_inventory_item:
            default_inventory = InventoryItemService.get_default_inventory()
            part_category = None
            if part_category_id:
                part_category = InventoryItemCategory.domain.get_queryset().filter(
                    pk=part_category_id
                ).first()
            if part_category is None:
                raise serializers.ValidationError(
                    {
                        "part_specs": (
                            "Selected parts must belong to a category when creating "
                            "a new inventory item."
                        )
                    }
                )
            try:
                inventory_item, created = InventoryItem.objects.get_or_create(
                    serial_number=serial_number,
                    defaults={
                        "name": serial_number,
                        "inventory": default_inventory,
                        "category": part_category,
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

        request = self.context.get("request")
        if (
            approve_review
            and request
            and request.user
            and request.user.is_authenticated
        ):
            validated_data["approved_by"] = request.user
            validated_data["approved_at"] = timezone.now()
            if validated_data.get("status") == TicketStatus.UNDER_REVIEW:
                validated_data["status"] = TicketStatus.NEW

        ticket = super().create(validated_data)
        TicketPartSpec.objects.bulk_create(
            [
                TicketPartSpec(
                    ticket=ticket,
                    inventory_item_part_id=spec["part_id"],
                    color=spec["color"],
                    comment=spec["comment"],
                    minutes=spec["minutes"],
                )
                for spec in part_specs
            ]
        )
        return ticket

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
            "total_minutes": int(getattr(self, "_resolved_total_minutes", 0) or 0),
            "part_specs_count": int(
                getattr(self, "_resolved_part_specs_count", 0) or 0
            ),
        }

    @staticmethod
    def _ticket_xp_divisor() -> int:
        rules = RulesService.get_active_rules_config()
        ticket_rules = rules.get("ticket_xp", {})
        divisor = int(ticket_rules.get("base_divisor", 20) or 20)
        if divisor <= 0:
            return 20
        return divisor

    @staticmethod
    def _resolve_part_specs(
        *,
        part_specs: list[dict],
        inventory_item: InventoryItem | None,
        creating_inventory_item: bool,
    ) -> tuple[list[dict], int, int | None]:
        if not part_specs:
            raise serializers.ValidationError(
                {"part_specs": "part_specs must contain at least one part entry."}
            )

        provided_ids = [int(item["part_id"]) for item in part_specs]
        if len(set(provided_ids)) != len(provided_ids):
            raise serializers.ValidationError(
                {"part_specs": "Each part_id must appear only once."}
            )

        parts_by_id: dict[int, InventoryItemPart] = {
            part.id: part
            for part in InventoryItemPart.objects.filter(id__in=provided_ids).only(
                "id",
                "name",
                "category_id",
            )
        }
        missing_part_ids = sorted(set(provided_ids) - set(parts_by_id.keys()))
        if missing_part_ids:
            raise serializers.ValidationError(
                {
                    "part_specs": (
                        "Unknown part ids: "
                        f"{', '.join(str(part_id) for part_id in missing_part_ids)}."
                    )
                }
            )

        part_category_ids = sorted(
            {
                int(part.category_id)
                for part in parts_by_id.values()
                if part.category_id is not None
            }
        )
        if any(part.category_id is None for part in parts_by_id.values()):
            raise serializers.ValidationError(
                {
                    "part_specs": (
                        "Selected parts must belong to an inventory category."
                    )
                }
            )
        if not part_category_ids:
            raise serializers.ValidationError(
                {
                    "part_specs": (
                        "Selected parts must belong to an inventory category."
                    )
                }
            )
        if len(part_category_ids) > 1:
            raise serializers.ValidationError(
                {
                    "part_specs": (
                        "All selected parts must belong to the same category."
                    )
                }
            )
        part_category_id = int(part_category_ids[0])

        if inventory_item and not creating_inventory_item:
            if inventory_item.category_id != part_category_id:
                raise serializers.ValidationError(
                    {
                        "part_specs": (
                            "Selected parts do not belong to the inventory item's "
                            "category."
                        )
                    }
                )

        normalized: list[dict] = []
        total_minutes = 0
        for item in part_specs:
            minutes = int(item["minutes"])
            total_minutes += minutes
            normalized.append(
                {
                    "part_id": int(item["part_id"]),
                    "color": item["color"],
                    "comment": str(item.get("comment", "")).strip(),
                    "minutes": minutes,
                }
            )
        return normalized, total_minutes, part_category_id
