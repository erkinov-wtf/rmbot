from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from bike.models import Bike
from bike.services import BikeService
from ticket.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    bike = serializers.PrimaryKeyRelatedField(read_only=True)
    bike_code = serializers.CharField(write_only=True, required=True)
    confirm_create_bike = serializers.BooleanField(
        write_only=True, required=False, default=False
    )
    bike_creation_reason = serializers.CharField(
        write_only=True, required=False, allow_blank=False
    )
    checklist_snapshot = serializers.JSONField(required=True)
    srt_total_minutes = serializers.IntegerField(required=True)
    approve_srt = serializers.BooleanField(write_only=True, required=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "bike",
            "bike_code",
            "confirm_create_bike",
            "bike_creation_reason",
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
            "bike",
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
        raw_bike_code = attrs.get("bike_code", "")
        bike_code = BikeService.normalize_bike_code(raw_bike_code)
        if not BikeService.is_valid_bike_code(bike_code):
            raise serializers.ValidationError(
                {"bike_code": ("bike_code must match pattern RM-[A-Z0-9-]{4,29}.")}
            )
        attrs["bike_code"] = bike_code

        bike = BikeService.get_by_code(bike_code)
        if bike is None:
            archived_bike = Bike.all_objects.filter(
                bike_code__iexact=bike_code,
                deleted_at__isnull=False,
            ).first()
            if archived_bike is not None:
                raise serializers.ValidationError(
                    {
                        "bike_code": (
                            f"Bike '{bike_code}' is archived. Restore the existing bike "
                            "before creating a ticket."
                        )
                    }
                )

            suggestions = BikeService.suggest_codes(bike_code)
            if not attrs.get("confirm_create_bike"):
                message = (
                    f"Bike '{bike_code}' was not found. "
                    "Set confirm_create_bike=true and provide bike_creation_reason to create it."
                )
                if suggestions:
                    message += f" Closest matches: {', '.join(suggestions)}."
                raise serializers.ValidationError({"bike_code": message})
            if not attrs.get("bike_creation_reason"):
                raise serializers.ValidationError(
                    {
                        "bike_creation_reason": (
                            "bike_creation_reason is required when confirm_create_bike=true."
                        )
                    }
                )
            attrs["_create_bike"] = True
            attrs["_bike_creation_reason"] = attrs["bike_creation_reason"].strip()
        else:
            attrs["bike"] = bike
            attrs["_create_bike"] = False
            attrs["_bike_creation_reason"] = None
            if Ticket.domain.has_active_for_bike(bike=bike):
                raise serializers.ValidationError(
                    {"bike_code": "An active ticket already exists for this bike."}
                )
        if not attrs.get("approve_srt"):
            raise serializers.ValidationError(
                {"approve_srt": "SRT must be approved by Master during intake."}
            )
        return attrs

    def create(self, validated_data):
        bike_code = validated_data.pop("bike_code")
        validated_data.pop("confirm_create_bike", None)
        validated_data.pop("bike_creation_reason", None)
        create_bike = bool(validated_data.pop("_create_bike", False))
        bike_creation_reason = validated_data.pop("_bike_creation_reason", None)

        self._resolved_bike_code = bike_code
        self._bike_created_during_intake = False
        self._bike_creation_reason = None

        if create_bike:
            try:
                bike, created = Bike.objects.get_or_create(
                    bike_code=bike_code,
                    defaults={"is_active": True},
                )
            except IntegrityError:
                archived_bike = Bike.all_objects.filter(
                    bike_code__iexact=bike_code,
                    deleted_at__isnull=False,
                ).first()
                if archived_bike is not None:
                    raise serializers.ValidationError(
                        {
                            "bike_code": (
                                f"Bike '{bike_code}' is archived. Restore the existing bike "
                                "before creating a ticket."
                            )
                        }
                    ) from None

                bike = BikeService.get_by_code(bike_code)
                if bike is None:
                    raise serializers.ValidationError(
                        {
                            "bike_code": (
                                "bike_code conflict detected while creating the bike. "
                                "Retry the request."
                            )
                        }
                    ) from None
                created = False

            if Ticket.domain.has_active_for_bike(bike=bike):
                raise serializers.ValidationError(
                    {"bike_code": "An active ticket already exists for this bike."}
                )
            validated_data["bike"] = bike
            self._bike_created_during_intake = created
            self._bike_creation_reason = bike_creation_reason

        validated_data.pop("approve_srt", None)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["srt_approved_by"] = request.user
            validated_data["srt_approved_at"] = timezone.now()
        return super().create(validated_data)

    def get_intake_metadata(self) -> dict[str, object]:
        return {
            "bike_code": getattr(self, "_resolved_bike_code", None),
            "bike_created_during_intake": bool(
                getattr(self, "_bike_created_during_intake", False)
            ),
            "bike_creation_reason": getattr(self, "_bike_creation_reason", None),
        }

    @staticmethod
    def _is_valid_checklist_item(item) -> bool:
        if isinstance(item, str):
            return bool(item.strip())
        if isinstance(item, dict):
            task = item.get("task")
            return isinstance(task, str) and bool(task.strip())
        return False
