from rest_framework import serializers

from account.models import User
from core.utils.constants import RoleSlug, TicketColor


class TicketAssignSerializer(serializers.Serializer):
    technician_id = serializers.IntegerField(min_value=1)

    def validate_technician_id(self, value: int) -> int:
        user = User.objects.filter(pk=value).first()
        if not user:
            raise serializers.ValidationError("Technician user does not exist.")
        if not user.roles.filter(slug=RoleSlug.TECHNICIAN).exists():
            raise serializers.ValidationError(
                "Selected user does not have TECHNICIAN role."
            )
        return value


class TicketClaimSerializer(serializers.Serializer):
    pass


class TicketPartCompletionInputSerializer(serializers.Serializer):
    part_spec_id = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_note(self, value: str) -> str:
        return value.strip()


class TicketCompletePartsSerializer(serializers.Serializer):
    parts = TicketPartCompletionInputSerializer(
        many=True,
        allow_empty=False,
        required=False,
    )
    completed_part_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=False,
        write_only=True,
    )

    def validate_parts(self, value: list[dict]) -> list[dict]:
        part_spec_ids = [int(row["part_spec_id"]) for row in value]
        if len(set(part_spec_ids)) != len(part_spec_ids):
            raise serializers.ValidationError(
                "Each part_spec_id must appear only once in one request."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        parts = attrs.get("parts")
        completed_part_ids = attrs.get("completed_part_ids")

        if parts and completed_part_ids:
            raise serializers.ValidationError(
                "Provide either parts or completed_part_ids, not both."
            )

        if completed_part_ids:
            seen: set[int] = set()
            normalized_ids: list[int] = []
            for item in completed_part_ids:
                part_spec_id = int(item)
                if part_spec_id in seen:
                    continue
                seen.add(part_spec_id)
                normalized_ids.append(part_spec_id)
            attrs["parts"] = [
                {"part_spec_id": part_spec_id, "note": ""}
                for part_spec_id in normalized_ids
            ]
            return attrs

        if not parts:
            raise serializers.ValidationError(
                "parts or completed_part_ids is required."
            )

        attrs["parts"] = self.validate_parts(parts)
        return attrs


class TicketQCFailSerializer(serializers.Serializer):
    failed_part_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_failed_part_ids(self, value: list[int]) -> list[int]:
        deduplicated: list[int] = []
        seen: set[int] = set()
        for item in value:
            part_id = int(item)
            if part_id in seen:
                continue
            seen.add(part_id)
            deduplicated.append(part_id)
        return deduplicated

    def validate_note(self, value: str) -> str:
        return value.strip()


class TicketManualMetricsSerializer(serializers.Serializer):
    flag_color = serializers.ChoiceField(choices=TicketColor.choices)
    xp_amount = serializers.IntegerField(min_value=0)
