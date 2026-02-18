from rest_framework import serializers

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import EmployeeLevel, RoleSlug
from gamification.services import ProgressionService


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


class UserManagementSerializer(serializers.ModelSerializer):
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
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
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


class UserManagementUpdateSerializer(serializers.Serializer):
    role_slugs = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleSlug.values),
        required=False,
        allow_empty=True,
    )
    is_active = serializers.BooleanField(required=False)
    level = serializers.ChoiceField(choices=EmployeeLevel.values, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs

    def update(self, instance: User, validated_data):
        role_slugs = validated_data.get("role_slugs")
        if role_slugs is not None:
            unique_role_slugs = list(dict.fromkeys(role_slugs))
            roles = list(
                Role.objects.filter(
                    slug__in=unique_role_slugs,
                    deleted_at__isnull=True,
                )
            )
            role_slugs_found = {role.slug for role in roles}
            missing_slugs = [
                role_slug
                for role_slug in unique_role_slugs
                if role_slug not in role_slugs_found
            ]
            if missing_slugs:
                raise serializers.ValidationError(
                    {
                        "role_slugs": (
                            "Roles are missing in database: "
                            + ", ".join(sorted(missing_slugs))
                        )
                    }
                )
            instance.roles.set(roles)

        update_fields: list[str] = []
        if "is_active" in validated_data:
            instance.is_active = bool(validated_data["is_active"])
            update_fields.append("is_active")

        if update_fields:
            instance.save(update_fields=update_fields)

        if "level" in validated_data:
            request = self.context.get("request")
            actor_user_id = getattr(getattr(request, "user", None), "id", None)
            next_level = int(validated_data["level"])
            if actor_user_id:
                ProgressionService.set_user_level_manually(
                    actor_user_id=actor_user_id,
                    user_id=instance.id,
                    new_level=next_level,
                    note="User management level update",
                    clear_warning=False,
                )
                instance.refresh_from_db(fields=["level", "updated_at"])
            else:
                instance.level = next_level
                instance.save(update_fields=["level"])

        return instance

    def create(self, validated_data):
        raise NotImplementedError


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
