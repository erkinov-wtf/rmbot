from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.rules.serializers import (
    RulesConfigRollbackSerializer,
    RulesConfigUpdateSerializer,
    RulesConfigVersionSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from rules.services import RulesService

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


@extend_schema(
    tags=["Rules Engine"],
    summary="Read or update active rules config",
    description="GET returns the active rules config. PUT validates and creates a new version, then activates it.",
)
class RulesConfigAPIView(BaseAPIView):
    serializer_class = RulesConfigUpdateSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            permission_classes = (IsAuthenticated, RulesReadPermission)
        else:
            permission_classes = (IsAuthenticated, RulesWritePermission)
        return [permission() for permission in permission_classes]

    def get(self, request, *args, **kwargs):
        state = RulesService.get_active_rules_state()
        return Response(_state_payload(state), status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            state = RulesService.update_rules_config(
                config=serializer.validated_data["config"],
                actor_user_id=request.user.id,
                reason=serializer.validated_data.get("reason"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_state_payload(state), status=status.HTTP_200_OK)


@extend_schema(
    tags=["Rules Engine"],
    summary="Rollback active rules config",
    description="Rolls back active rules to a selected historical version and records a new rollback version entry.",
)
class RulesConfigRollbackAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, RulesWritePermission)
    serializer_class = RulesConfigRollbackSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            state = RulesService.rollback_rules_config(
                target_version_number=serializer.validated_data["target_version"],
                actor_user_id=request.user.id,
                reason=serializer.validated_data.get("reason"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_state_payload(state), status=status.HTTP_200_OK)


@extend_schema(
    tags=["Rules Engine"],
    summary="List rules config version history",
    description="Returns recent rules config versions with metadata and change diff snapshots.",
)
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

        history = RulesService.list_rules_versions(limit=limit)
        return Response(
            RulesConfigVersionSerializer(history, many=True).data,
            status=status.HTTP_200_OK,
        )
