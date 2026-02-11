from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.rules.serializers import (
    RulesConfigRollbackSerializer,
    RulesConfigUpdateSerializer,
    RulesConfigVersionSerializer,
)
from core.api.permissions import HasRole
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from rules.services import (
    get_active_rules_state,
    list_rules_versions,
    rollback_rules_config,
    update_rules_config,
)

RulesReadPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)
RulesWritePermission = HasRole.as_any(RoleSlug.SUPER_ADMIN)


def _state_payload(state) -> dict:
    return {
        "active_version": state.active_version.version,
        "cache_key": state.cache_key,
        "checksum": state.active_version.checksum,
        "config": state.active_version.config,
        "updated_at": state.updated_at,
    }


class RulesConfigAPIView(BaseAPIView):
    serializer_class = RulesConfigUpdateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            permission_classes = (IsAuthenticated, RulesReadPermission)
        else:
            permission_classes = (IsAuthenticated, RulesWritePermission)
        return [permission() for permission in permission_classes]

    def get(self, request, *args, **kwargs):
        state = get_active_rules_state()
        return Response(_state_payload(state), status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            state = update_rules_config(
                config=serializer.validated_data["config"],
                actor_user_id=request.user.id,
                reason=serializer.validated_data.get("reason"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_state_payload(state), status=status.HTTP_200_OK)


class RulesConfigRollbackAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, RulesWritePermission)
    serializer_class = RulesConfigRollbackSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            state = rollback_rules_config(
                target_version_number=serializer.validated_data["target_version"],
                actor_user_id=request.user.id,
                reason=serializer.validated_data.get("reason"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_state_payload(state), status=status.HTTP_200_OK)


class RulesConfigHistoryAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, RulesReadPermission)

    def get(self, request, *args, **kwargs):
        limit_raw = request.query_params.get("limit", "50")
        try:
            limit = int(limit_raw)
        except ValueError:
            return Response(
                {"detail": "limit must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if limit < 1 or limit > 200:
            return Response(
                {"detail": "limit must be between 1 and 200"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        history = list_rules_versions(limit=limit)
        return Response(
            RulesConfigVersionSerializer(history, many=True).data,
            status=status.HTTP_200_OK,
        )
