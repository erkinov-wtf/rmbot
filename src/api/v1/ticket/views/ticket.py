from rest_framework.permissions import IsAuthenticated

from api.v1.ticket.permissions import TicketCreatePermission
from api.v1.ticket.serializers import TicketSerializer
from core.api.schema import extend_schema
from core.api.views import BaseModelViewSet
from core.utils.constants import TicketTransitionAction
from ticket.models import Ticket


class TicketViewSet(BaseModelViewSet):
    serializer_class = TicketSerializer
    queryset = (
        Ticket.objects.select_related("inventory_item", "master", "technician")
        .prefetch_related("part_specs__inventory_item_part")
        .order_by("-created_at")
    )

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
