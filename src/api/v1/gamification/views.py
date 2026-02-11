from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.gamification.serializers import XPLedgerSerializer
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug, XPLedgerEntryType
from gamification.models import XPLedger

PRIVILEGED_LEDGER_VIEW_ROLES = {RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER}


class XPLedgerListAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        role_slugs = set(request.user.roles.values_list("slug", flat=True))
        can_view_all = bool(role_slugs & PRIVILEGED_LEDGER_VIEW_ROLES)

        user_id_raw = request.query_params.get("user_id")
        ticket_id_raw = request.query_params.get("ticket_id")
        entry_type = request.query_params.get("entry_type")
        limit_raw = request.query_params.get("limit", "100")

        try:
            limit = int(limit_raw)
        except ValueError:
            return Response(
                {"detail": "limit must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if limit < 1 or limit > 500:
            return Response(
                {"detail": "limit must be between 1 and 500"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = None
        if user_id_raw is not None:
            try:
                user_id = int(user_id_raw)
            except ValueError:
                return Response(
                    {"detail": "user_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user_id < 1:
                return Response(
                    {"detail": "user_id must be a positive integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ticket_id = None
        if ticket_id_raw is not None:
            try:
                ticket_id = int(ticket_id_raw)
            except ValueError:
                return Response(
                    {"detail": "ticket_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ticket_id < 1:
                return Response(
                    {"detail": "ticket_id must be a positive integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if entry_type and entry_type not in XPLedgerEntryType.values:
            return Response(
                {
                    "detail": f"Invalid entry_type value. Allowed: {', '.join(XPLedgerEntryType.values)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = XPLedger.objects.select_related("user").order_by("-created_at")

        if can_view_all:
            if user_id is not None:
                queryset = queryset.filter(user_id=user_id)
        else:
            if user_id is not None and user_id != request.user.id:
                return Response(
                    {"detail": "You can only view your own XP ledger entries."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            queryset = queryset.filter(user_id=request.user.id)

        if ticket_id is not None:
            queryset = queryset.filter(
                Q(payload__ticket_id=ticket_id)
                | Q(reference=f"ticket_base_xp:{ticket_id}")
                | Q(reference=f"ticket_qc_first_pass_bonus:{ticket_id}")
            )

        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)

        serializer = XPLedgerSerializer(queryset[:limit], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
