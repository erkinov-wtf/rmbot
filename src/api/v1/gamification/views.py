from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.gamification.filters import (
    XPTransactionFilterSet,
    can_view_all_transaction_entries,
)
from api.v1.gamification.serializers import (
    LevelManualSetSerializer,
    WeeklyEvaluationRunSerializer,
    XPAdjustmentSerializer,
    XPTransactionSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, ListAPIView
from core.utils.constants import RoleSlug
from gamification.models import XPTransaction
from gamification.services import GamificationService, ProgressionService

XPAdjustmentPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)
LevelControlPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


@extend_schema(
    tags=["XP Transactions"],
    summary="List XP transactions",
    description=(
        "Returns paginated XP transaction entries with optional filters. Regular users can only see their own entries."
    ),
)
class XPTransactionListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = XPTransactionSerializer
    queryset = XPTransaction.objects.select_related("user").order_by(
        "-created_at", "-id"
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = XPTransactionFilterSet

    def get_queryset(self):
        queryset = self.queryset
        if self._can_view_all():
            return queryset

        return queryset.filter(user_id=self.request.user.id)

    def _can_view_all(self) -> bool:
        return can_view_all_transaction_entries(self.request.user)


@extend_schema(
    tags=["XP Transactions"],
    summary="Create manual XP adjustment",
    description=(
        "Creates an append-only manual XP entry for any user. "
        "Only manager roles can call this endpoint. "
        "Comment is required and is used for Telegram notification payload."
    ),
)
class XPAdjustmentCreateAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, XPAdjustmentPermission)
    serializer_class = XPAdjustmentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry = GamificationService.adjust_user_xp(
            actor_user_id=request.user.id,
            target_user_id=serializer.validated_data["user_id"],
            amount=serializer.validated_data["amount"],
            comment=serializer.validated_data["comment"],
        )

        output = XPTransactionSerializer(entry).data
        return Response(output, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["XP Progression"],
    summary="Get level control overview",
    description=(
        "Returns technicians with XP totals for the selected date range, "
        "target comparison, warning suggestions, and latest weekly progression states."
    ),
)
class LevelControlOverviewAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, LevelControlPermission)

    def get(self, request, *args, **kwargs):
        raw_date_from = str(request.query_params.get("date_from", "")).strip()
        raw_date_to = str(request.query_params.get("date_to", "")).strip()

        date_from = None
        date_to = None
        if raw_date_from or raw_date_to:
            if not raw_date_from or not raw_date_to:
                return Response(
                    {"detail": "date_from and date_to must be provided together."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                date_from = ProgressionService.parse_date_token(
                    raw_date_from, field_name="date_from"
                )
                date_to = ProgressionService.parse_date_token(
                    raw_date_to, field_name="date_to"
                )
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            payload = ProgressionService.get_level_control_overview(
                date_from=date_from,
                date_to=date_to,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["XP Progression"],
    summary="Get level control history for one user",
    description=(
        "Returns combined user history for level control: XP transactions, "
        "weekly level evaluations, and append-only level history events."
    ),
)
class LevelControlUserHistoryAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, LevelControlPermission)

    def get(self, request, *args, **kwargs):
        raw_date_from = str(request.query_params.get("date_from", "")).strip()
        raw_date_to = str(request.query_params.get("date_to", "")).strip()
        raw_limit = str(request.query_params.get("limit", "")).strip()

        date_from = None
        date_to = None
        if raw_date_from or raw_date_to:
            if not raw_date_from or not raw_date_to:
                return Response(
                    {"detail": "date_from and date_to must be provided together."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                date_from = ProgressionService.parse_date_token(
                    raw_date_from, field_name="date_from"
                )
                date_to = ProgressionService.parse_date_token(
                    raw_date_to, field_name="date_to"
                )
            except ValueError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            limit = int(raw_limit) if raw_limit else 500
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = ProgressionService.get_user_level_history(
                user_id=int(kwargs["user_id"]),
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["XP Progression"],
    summary="Set user level manually",
    description=(
        "Manually sets a user's level and records append-only level-history event, "
        "with optional warning-clear action."
    ),
)
class LevelControlSetLevelAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, LevelControlPermission)
    serializer_class = LevelManualSetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = ProgressionService.set_user_level_manually(
                actor_user_id=request.user.id,
                user_id=int(kwargs["user_id"]),
                new_level=int(serializer.validated_data["level"]),
                note=serializer.validated_data.get("note", ""),
                clear_warning=bool(serializer.validated_data.get("clear_warning", False)),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


@extend_schema(
    tags=["XP Progression"],
    summary="Run weekly level evaluation",
    description=(
        "Runs weekly level progression evaluation for a Monday week_start "
        "(default: previous week)."
    ),
)
class WeeklyLevelEvaluationRunAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, LevelControlPermission)
    serializer_class = WeeklyEvaluationRunSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = ProgressionService.run_weekly_level_evaluation(
                week_start=serializer.validated_data.get("week_start"),
                actor_user_id=request.user.id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)
