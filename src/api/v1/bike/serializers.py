from rest_framework import serializers

from bike.models import Bike
from bike.services import BikeService


class BikeSerializer(serializers.ModelSerializer):
    bike_code = serializers.CharField()

    class Meta:
        model = Bike
        fields = (
            "id",
            "bike_code",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_bike_code(self, value: str) -> str:
        normalized_code = BikeService.normalize_bike_code(value)
        if not BikeService.is_valid_bike_code(normalized_code):
            raise serializers.ValidationError(
                "bike_code must match pattern RM-[A-Z0-9-]{4,29}."
            )

        existing = Bike.all_objects.filter(bike_code__iexact=normalized_code)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                "Bike with this bike_code already exists."
            )
        return normalized_code


class BikeSuggestionQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=True)

    def validate_q(self, value: str) -> str:
        normalized_query = BikeService.normalize_bike_code(value)
        if len(normalized_query) < BikeService.SUGGESTION_MIN_CHARS:
            raise serializers.ValidationError("q must contain at least 2 characters.")
        return normalized_query
