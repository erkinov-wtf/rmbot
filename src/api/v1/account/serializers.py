from rest_framework import serializers

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import RoleSlug


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("slug", "name")


class TelegramProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramProfile
        fields = (
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "language_code",
            "is_bot",
            "is_premium",
            "verified_at",
        )


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    telegram = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "phone",
            "level",
            "roles",
            "telegram",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_telegram(self, obj: User) -> dict | None:
        profile = (
            obj.telegram_profiles.filter(deleted_at__isnull=True)
            .order_by("-verified_at", "-created_at")
            .first()
        )
        if not profile:
            return None
        return TelegramProfileSerializer(profile).data


class UserOptionSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "phone",
            "level",
            "roles",
        )
        read_only_fields = fields


class AccessRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessRequest
        fields = (
            "id",
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "note",
            "status",
            "created_at",
            "resolved_at",
        )


class AccessRequestApproveSerializer(serializers.Serializer):
    role_slugs = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleSlug.values),
        required=False,
        allow_empty=True,
    )
