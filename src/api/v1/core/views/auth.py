import json
from dataclasses import dataclass

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenVerifySerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from account.services import upsert_telegram_profile
from api.v1.account.serializers import UserSerializer
from core.api.views import BaseAPIView
from core.utils.telegram import InitDataValidationError, validate_init_data


class LoginAPIView(TokenObtainPairView, BaseAPIView):
    pass


class RefreshAPIView(TokenRefreshView, BaseAPIView):
    pass


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


@dataclass(slots=True)
class _TelegramFromUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_premium: bool = False
    is_bot: bool = False


class TMAInitDataVerifyAPIView(BaseAPIView):
    """
    Verifies Telegram Mini App initData, returns JWT tokens if linked user exists.
    """

    permission_classes = (AllowAny,)
    serializer_class = TMAInitDataSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            parsed = validate_init_data(
                serializer.validated_data["init_data"], bot_token=settings.BOT_TOKEN
            )
        except InitDataValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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

        profile = upsert_telegram_profile(
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

        refresh = RefreshToken.for_user(user)
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
