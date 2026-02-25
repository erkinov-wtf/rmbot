import base64
import binascii
import mimetypes

from rest_framework import serializers

from account.models import AccessRequest, Role, TelegramProfile, User
from core.utils.constants import EmployeeLevel, RoleSlug
from gamification.services import ProgressionService

MAX_PUBLIC_PHOTO_BYTES = 3 * 1024 * 1024
MAX_PUBLIC_PHOTO_LABEL = "3 MB"


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
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "phone",
            "photo_url",
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

    def get_photo_url(self, obj: User) -> str | None:
        request = self.context.get("request")
        return obj.resolve_public_photo_url(request=request)


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
    photo_url = serializers.SerializerMethodField()
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "phone",
            "photo_url",
            "has_photo",
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

    def get_photo_url(self, obj: User) -> str | None:
        if not bool(self.context.get("include_photo", True)):
            return None
        request = self.context.get("request")
        return obj.resolve_public_photo_url(request=request)

    def get_has_photo(self, obj: User) -> bool:
        return bool(obj.public_photo_blob) or bool(obj.public_photo)


class UserManagementUpdateSerializer(serializers.Serializer):
    role_slugs = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleSlug.values),
        required=False,
        allow_empty=True,
    )
    is_active = serializers.BooleanField(required=False)
    level = serializers.ChoiceField(choices=EmployeeLevel.values, required=False)
    photo = serializers.FileField(required=False, allow_null=True)
    photo_data_url = serializers.CharField(required=False, allow_blank=False)
    photo_clear = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        if attrs.get("photo") is not None and attrs.get("photo_data_url") is not None:
            raise serializers.ValidationError(
                "Provide either photo or photo_data_url, not both."
            )
        return attrs

    @staticmethod
    def _decode_photo_data_url(value: str) -> tuple[bytes, str]:
        data_url = str(value or "").strip()
        prefix, separator, encoded_payload = data_url.partition(",")
        if (
            not separator
            or not prefix.startswith("data:")
            or ";base64" not in prefix
        ):
            raise serializers.ValidationError(
                {"photo_data_url": "Invalid photo data URL format."}
            )
        mime = prefix[5 : prefix.index(";base64")].strip().lower() or "image/jpeg"
        try:
            raw_photo = base64.b64decode(encoded_payload, validate=True)
        except (ValueError, binascii.Error):
            raise serializers.ValidationError(
                {"photo_data_url": "Invalid base64 photo payload."}
            ) from None
        if not raw_photo:
            raise serializers.ValidationError(
                {"photo_data_url": "Uploaded photo payload is empty."}
            )
        if len(raw_photo) > MAX_PUBLIC_PHOTO_BYTES:
            raise serializers.ValidationError(
                {
                    "photo_data_url": (
                        f"Uploaded photo exceeds {MAX_PUBLIC_PHOTO_LABEL} limit."
                    )
                }
            )
        return raw_photo, mime

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

        photo = validated_data.get("photo")
        photo_data_url = validated_data.get("photo_data_url")
        photo_clear = bool(validated_data.get("photo_clear", False))
        if photo is not None or photo_data_url is not None:
            raw_photo: bytes
            content_type: str | None
            if photo is not None:
                raw_photo = photo.read()
                if not raw_photo:
                    raise serializers.ValidationError(
                        {"photo": "Uploaded photo file is empty."}
                    )
                if len(raw_photo) > MAX_PUBLIC_PHOTO_BYTES:
                    raise serializers.ValidationError(
                        {
                            "photo": (
                                f"Uploaded photo exceeds {MAX_PUBLIC_PHOTO_LABEL} limit."
                            )
                        }
                    )
                content_type = getattr(photo, "content_type", None)
                if not content_type:
                    guessed_type, _ = mimetypes.guess_type(getattr(photo, "name", ""))
                    content_type = guessed_type
            else:
                raw_photo, content_type = self._decode_photo_data_url(photo_data_url)
            instance.public_photo_blob = raw_photo
            instance.public_photo_mime = (
                str(content_type).strip().lower() if content_type else "image/jpeg"
            )
            if instance.public_photo:
                instance.public_photo.delete(save=False)
            instance.public_photo = None
            instance.save(
                update_fields=[
                    "public_photo_blob",
                    "public_photo_mime",
                    "public_photo",
                    "updated_at",
                ]
            )
        elif photo_clear:
            instance.public_photo_blob = None
            instance.public_photo_mime = None
            if instance.public_photo:
                instance.public_photo.delete(save=False)
            instance.public_photo = None
            instance.save(
                update_fields=[
                    "public_photo_blob",
                    "public_photo_mime",
                    "public_photo",
                    "updated_at",
                ]
            )

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
