import json
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken, Token
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from account.services import AccountService
from api.v1.account.serializers import UserSerializer
from core.api.schema import extend_schema
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from core.utils.telegram import (
    InitDataValidationError,
    extract_init_data_hash,
    validate_init_data,
)


def _build_role_claims(user) -> tuple[list[str], list[str]]:
    role_pairs = list(
        user.roles.filter(deleted_at__isnull=True)
        .order_by("slug")
        .values_list("slug", "name")
    )
    role_slugs = [slug for slug, _ in role_pairs]
    role_titles = [name for _, name in role_pairs]
    if user.is_superuser and RoleSlug.SUPER_ADMIN not in role_slugs:
        role_slugs.append(RoleSlug.SUPER_ADMIN)
        role_titles.append("Super Admin")
    return role_slugs, role_titles


def attach_user_role_claims(token: Token, user) -> None:
    role_slugs, role_titles = _build_role_claims(user)
    token["role_slugs"] = role_slugs
    token["roles"] = role_titles


class LoginTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        attach_user_role_claims(token, user)
        return token


@extend_schema(
    tags=["Auth"],
    summary="Login with credentials and get JWT tokens",
    description="Authenticates user credentials and returns JWT access and refresh tokens.",
)
class LoginAPIView(TokenObtainPairView, BaseAPIView):
    serializer_class = LoginTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Refresh JWT access token",
    description="Validates a refresh token and issues a new access token.",
)
class RefreshAPIView(TokenRefreshView, BaseAPIView):
    pass


@extend_schema(
    tags=["Auth"],
    summary="Verify JWT token",
    description="Checks whether the provided JWT token is valid and not expired.",
)
class TokenVerifyAPIView(TokenVerifyView, BaseAPIView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            serializer = TokenVerifySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            response.data = {"detail": "Token is valid"}

        return response


class TMAInitDataSerializer(serializers.Serializer):
    init_data = serializers.CharField()

    def validate_init_data(self, value):
        if not value:
            raise serializers.ValidationError("init_data is required")

        return value


@dataclass(slots=True)
class _TelegramFromUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    is_bot: bool = False


@extend_schema(
    tags=["Auth"],
    summary="Verify Telegram Mini App initData",
    description="Validates Telegram Mini App initData and issues JWT tokens when a linked user account exists.",
)
class TMAInitDataVerifyAPIView(BaseAPIView):
    """
    Verifies Telegram Mini App initData, returns JWT tokens if linked user exists.
    """

    permission_classes = (AllowAny,)
    serializer_class = TMAInitDataSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        init_data = serializer.validated_data["init_data"]
        max_age_seconds = max(
            int(getattr(settings, "TMA_INIT_DATA_MAX_AGE_SECONDS", 300)), 1
        )
        max_future_skew_seconds = max(
            int(getattr(settings, "TMA_INIT_DATA_MAX_FUTURE_SKEW_SECONDS", 30)), 0
        )

        try:
            parsed = validate_init_data(
                init_data,
                bot_token=settings.BOT_TOKEN,
                max_age_seconds=max_age_seconds,
                max_future_skew_seconds=max_future_skew_seconds,
            )
            init_data_hash = extract_init_data_hash(init_data)
        except InitDataValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as ve:
            return Response(
                {"detail": "init_data is invalid: " + str(ve)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_user = parsed.get("user")
        try:
            user_payload = json.loads(raw_user) if raw_user else {}
        except (TypeError, json.JSONDecodeError):
            return Response(
                {"detail": "init_data user payload is invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        telegram_id = user_payload.get("id")
        try:
            telegram_id = int(telegram_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "init_data user.id is missing or invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if telegram_id <= 0:
            return Response(
                {"detail": "init_data user.id is missing or invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = user_payload.get("username")
        first_name = user_payload.get("first_name")
        last_name = user_payload.get("last_name")
        language_code = user_payload.get("language_code")
        is_premium = user_payload.get("is_premium", False)
        is_bot = user_payload.get("is_bot", False)

        profile = AccountService.upsert_telegram_profile(
            _TelegramFromUser(
                id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_premium=is_premium,
                is_bot=is_bot,
            )
        )

        user = profile.user
        if not user:
            return Response(
                {
                    "valid": True,
                    "user_exists": False,
                    "needs_access_request": True,
                    "telegram_id": telegram_id,
                    "username": username,
                },
                status=status.HTTP_200_OK,
            )

        if self._is_replayed(init_data_hash):
            return Response(
                {"detail": "init_data has already been used"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        attach_user_role_claims(refresh, user)
        user_data = UserSerializer(user).data
        return Response(
            {
                "valid": True,
                "user_exists": True,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    def _is_replayed(self, init_data_hash: str) -> bool:
        replay_ttl_seconds = max(
            int(getattr(settings, "TMA_INIT_DATA_REPLAY_TTL_SECONDS", 300)), 1
        )
        replay_cache_key = f"tma:init-data-hash:{init_data_hash}"
        return not cache.add(replay_cache_key, "1", timeout=replay_ttl_seconds)
