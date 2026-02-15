from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.rules.filters import RulesConfigHistoryFilterSet
from api.v1.rules.serializers import (
    RulesConfigRollbackSerializer,
    RulesConfigUpdateSerializer,
    RulesConfigVersionSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, ListAPIView
from core.utils.constants import RoleSlug
from rules.models import RulesConfigVersion
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
class RulesConfigHistoryAPIView(ListAPIView):
    permission_classes = (IsAuthenticated, RulesReadPermission)
    serializer_class = RulesConfigVersionSerializer
    queryset = RulesConfigVersion.domain.get_queryset().with_related().ordered_latest()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RulesConfigHistoryFilterSet
