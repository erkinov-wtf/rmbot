from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
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


class PublicTechnicianLeaderboardQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(required=False, min_value=1, max_value=90)
    include_photo = serializers.BooleanField(required=False, default=False)


class PublicTechnicianDetailQuerySerializer(serializers.Serializer):
    include_photo = serializers.BooleanField(required=False, default=False)


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


@extend_schema(
    tags=["Analytics"],
    summary="Public technician leaderboard",
    description=(
        "Public ranking chart for technicians based on cumulative score "
        "(tickets, quality, XP, attendance, and penalties)."
    ),
    parameters=[PublicTechnicianLeaderboardQuerySerializer],
)
class PublicTechnicianLeaderboardAPIView(BaseAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PublicTechnicianLeaderboardQuerySerializer

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data.get("days")
        include_photo = serializer.validated_data.get("include_photo", False)
        payload = TicketAnalyticsService.public_technician_leaderboard(
            days=days,
            request=request,
            include_photo=include_photo,
        )
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Analytics"],
    summary="Public technician detailed stats",
    description=(
        "Returns full explanation and metric breakdown for a technician's "
        "position in the public leaderboard."
    ),
    parameters=[PublicTechnicianDetailQuerySerializer],
)
class PublicTechnicianDetailAPIView(BaseAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PublicTechnicianDetailQuerySerializer

    def get(self, request, user_id: int, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        include_photo = serializer.validated_data.get("include_photo", False)
        try:
            payload = TicketAnalyticsService.public_technician_detail(
                user_id=user_id,
                request=request,
                include_photo=include_photo,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Analytics"],
    summary="Public technician photo",
    description=(
        "Returns technician public avatar payload for on-demand lazy-loading in public dashboards."
    ),
)
class PublicTechnicianPhotoAPIView(BaseAPIView):
    permission_classes = (AllowAny,)

    def get(self, request, user_id: int, *args, **kwargs):
        try:
            payload = TicketAnalyticsService.public_technician_photo(
                user_id=user_id,
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)
