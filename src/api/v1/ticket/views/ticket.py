from rest_framework.permissions import IsAuthenticated

from api.v1.ticket.permissions import TicketCreatePermission
from api.v1.ticket.serializers import TicketSerializer
from core.api.schema import extend_schema
from core.api.views import BaseModelViewSet
from core.utils.constants import TicketTransitionAction
from ticket.models import Ticket
from ticket.services_workflow import TicketWorkflowService


class TicketViewSet(BaseModelViewSet):
    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician").order_by(
        "-created_at"
    )

    def get_permissions(self):
        if self.action == "create":
            permission_classes = (IsAuthenticated, TicketCreatePermission)
        else:
            permission_classes = (IsAuthenticated,)
        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="List tickets",
        description="Returns tickets with related bike, master, and technician data.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Create ticket",
        description=(
            "Creates a new ticket intake with checklist snapshot and master-approved "
            "SRT, then records the initial workflow transition."
        ),
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Retrieve ticket",
        description="Returns a single ticket with bike, master, and technician data.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        ticket = serializer.save(master=self.request.user)
        TicketWorkflowService.log_ticket_transition(
            ticket=ticket,
            from_status=None,
            to_status=ticket.status,
            action=TicketTransitionAction.CREATED,
            actor_user_id=self.request.user.id,
            metadata={
                "srt_total_minutes": ticket.srt_total_minutes,
                "srt_approved": bool(ticket.srt_approved_at),
                "checklist_items_count": len(ticket.checklist_snapshot or []),
            },
        )
