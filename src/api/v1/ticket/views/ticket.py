from django.db.models import Q
from rest_framework.permissions import IsAuthenticated

from api.v1.ticket.permissions import TicketCreatePermission
from api.v1.ticket.serializers import TicketSerializer
from core.api.schema import extend_schema
from core.api.views import BaseModelViewSet
from core.utils.constants import TicketStatus, TicketTransitionAction
from ticket.models import Ticket


class TicketViewSet(BaseModelViewSet):
    serializer_class = TicketSerializer
    queryset = (
        Ticket.objects.select_related("inventory_item", "master", "technician")
        .prefetch_related("part_specs__inventory_item_part")
        .order_by("-created_at")
    )

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = str(self.request.query_params.get("status", "")).strip()
        if status_filter:
            allowed_statuses = {status for status, _ in TicketStatus.choices}
            if status_filter not in allowed_statuses:
                return queryset.none()
            queryset = queryset.filter(status=status_filter)

        q_filter = str(self.request.query_params.get("q", "")).strip()
        if q_filter:
            normalized_q = q_filter.lstrip("#").strip()
            if not normalized_q:
                return queryset.none()
            search_filter = (
                Q(inventory_item__serial_number__icontains=normalized_q)
                | Q(title__icontains=normalized_q)
            )
            if normalized_q.isdigit():
                search_filter |= Q(id=int(normalized_q))
            queryset = queryset.filter(search_filter)

        return queryset

    def get_permissions(self):

        permission_classes = [IsAuthenticated]

        if self.action == "create":
            permission_classes += [TicketCreatePermission]

        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Create ticket",
        description=(
            "Creates a new ticket intake by inventory-item serial number with "
            "part-level specs, auto-computed ticket metrics (minutes/flag/XP), and "
            "initial UNDER_REVIEW status. Unknown serials require explicit "
            "confirm-create and a reason."
        ),
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Retrieve ticket",
        description="Returns a single ticket with inventory item, master, and technician data.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        ticket = serializer.save(master=self.request.user)
        intake_metadata = serializer.get_intake_metadata()
        ticket.add_transition(
            from_status=None,
            to_status=ticket.status,
            action=TicketTransitionAction.CREATED,
            actor_user_id=self.request.user.id,
            metadata={
                "total_duration": ticket.total_duration,
                "review_approved": bool(ticket.approved_at),
                "flag_color": ticket.flag_color,
                "xp_amount": ticket.xp_amount,
                "is_manual": ticket.is_manual,
                **intake_metadata,
            },
        )
