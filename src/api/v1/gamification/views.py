from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from api.v1.gamification.filters import XPLedgerFilterSet, can_view_all_ledger_entries
from api.v1.gamification.serializers import XPLedgerSerializer
from core.api.schema import extend_schema
from core.api.views import ListAPIView
from gamification.models import XPLedger


@extend_schema(
    tags=["XP Ledger"],
    summary="List XP ledger entries",
    description=(
        "Returns paginated XP ledger entries with optional filters. Regular users "
        "can only see their own entries."
    ),
)
class XPLedgerListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = XPLedgerSerializer
    queryset = XPLedger.objects.select_related("user").order_by("-created_at", "-id")
    filter_backends = (DjangoFilterBackend,)
    filterset_class = XPLedgerFilterSet

    def get_queryset(self):
        queryset = self.queryset
        if self._can_view_all():
            return queryset

        return queryset.filter(user_id=self.request.user.id)

    def _can_view_all(self) -> bool:
        return can_view_all_ledger_entries(self.request.user)
