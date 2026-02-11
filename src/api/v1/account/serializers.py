from rest_framework import serializers

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import AccessRequestStatus, RoleSlug


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
            "patronymic",
            "username",
            "email",
            "phone",
            "level",
            "roles",
            "telegram",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_telegram(self, obj: User):
        profile = (
            obj.telegram_profiles.filter(deleted_at__isnull=True)
            .order_by("-verified_at", "-created_at")
            .first()
        )
        if not profile:
            return None
        return TelegramProfileSerializer(profile).data


class AccessRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessRequest
        fields = (
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "note",
        )

    def validate(self, attrs):
        telegram_id = attrs.get("telegram_id")
        if AccessRequest.all_objects.filter(
            telegram_id=telegram_id,
            status=AccessRequestStatus.PENDING,
        ).exists():
            raise serializers.ValidationError(
                "Access request is already pending for this Telegram ID."
            )
        return attrs


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
    user_id = serializers.IntegerField(min_value=1, required=False)
    user = serializers.DictField(required=False)
    role_slugs = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleSlug.values),
        required=False,
        allow_empty=True,
    )

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

    def validate_user(self, value: dict) -> dict:
        required_fields = ("username", "first_name", "email")
        missing = [field for field in required_fields if not value.get(field)]
        if missing:
            raise serializers.ValidationError(
                f"Missing required fields: {', '.join(missing)}"
            )

        username = value.get("username")
        email = value.get("email")
        phone = value.get("phone")

        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError("username is already taken.")
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("email is already taken.")
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("phone is already taken.")

        return value

    def validate(self, attrs):
        has_user_id = attrs.get("user_id") is not None
        has_user_payload = attrs.get("user") is not None
        if has_user_id == has_user_payload:
            raise serializers.ValidationError(
                "Provide exactly one of 'user_id' or 'user'."
            )
        return attrs
