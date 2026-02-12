from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from ticket.services_analytics import TicketAnalyticsService

AnalyticsPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


class TeamAnalyticsQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(
        required=False, min_value=1, max_value=90, default=7
    )


@extend_schema(
    tags=["Analytics"],
    summary="Fleet analytics snapshot",
    description=(
        "Returns current fleet/ticket operational metrics including availability, "
        "active backlog, SLA pressure indicators, and a 7-day QC KPI trend."
    ),
)
class AnalyticsFleetAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AnalyticsPermission)

    def get(self, request, *args, **kwargs):
        return Response(
            TicketAnalyticsService.fleet_summary(), status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Analytics"],
    summary="Team analytics snapshot",
    description=(
        "Returns per-technician productivity metrics for a recent time window "
        "(tickets done, first-pass QC rate, XP and attendance days)."
    ),
    parameters=[TeamAnalyticsQuerySerializer],
)
class AnalyticsTeamAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AnalyticsPermission)
    serializer_class = TeamAnalyticsQuerySerializer

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data.get("days", 7)
        payload = TicketAnalyticsService.team_summary(days=days)
        return Response(payload, status=status.HTTP_200_OK)
