from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from api.v1.gamification.filters import (
    XPTransactionFilterSet,
    can_view_all_transaction_entries,
)
from api.v1.gamification.serializers import XPTransactionSerializer
from core.api.schema import extend_schema
from core.api.views import ListAPIView
from gamification.models import XPTransaction


@extend_schema(
    tags=["XP Transactions"],
    summary="List XP transactions",
    description=(
        "Returns paginated XP transaction entries with optional filters. Regular users "
        "can only see their own entries."
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
