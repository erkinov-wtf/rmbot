from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.gamification.filters import (
    XPTransactionFilterSet,
    can_view_all_transaction_entries,
)
from api.v1.gamification.serializers import (
    XPAdjustmentSerializer,
    XPTransactionSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, ListAPIView
from core.utils.constants import RoleSlug
from gamification.models import XPTransaction
from gamification.services import GamificationService

XPAdjustmentPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


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
