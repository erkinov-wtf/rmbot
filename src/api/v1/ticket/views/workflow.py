from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.ticket.permissions import (
    TicketAssignPermission,
    TicketManualMetricsPermission,
    TicketQCPermission,
    TicketReviewPermission,
    TicketWorkPermission,
)
from api.v1.ticket.serializers import (
    TicketAssignSerializer,
    TicketManualMetricsSerializer,
    TicketSerializer,
    TicketTransitionSerializer,
)
from core.api.schema import extend_schema
from core.api.views import BaseViewSet, ListAPIView
from ticket.models import Ticket, TicketTransition
from ticket.services_workflow import TicketWorkflowService


class TicketWorkflowViewSet(BaseViewSet):
    serializer_class = TicketAssignSerializer
    queryset = Ticket.objects.select_related(
        "inventory_item", "master", "technician"
    ).prefetch_related("part_specs__inventory_item_part")

    def get_serializer_class(self):
        if self.action == "manual_metrics":
            return TicketManualMetricsSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        if self.action == "assign":
            permission_classes = (IsAuthenticated, TicketAssignPermission)
        elif self.action == "review_approve":
            permission_classes = (IsAuthenticated, TicketReviewPermission)
        elif self.action == "manual_metrics":
            permission_classes = (IsAuthenticated, TicketManualMetricsPermission)
        elif self.action in {"start", "to_waiting_qc"}:
            permission_classes = (IsAuthenticated, TicketWorkPermission)
        elif self.action in {"qc_pass", "qc_fail"}:
            permission_classes = (IsAuthenticated, TicketQCPermission)
        else:
            permission_classes = (IsAuthenticated,)
        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Assign technician to ticket",
        description=(
            "Assigns a technician to the ticket and applies assignment workflow rules."
        ),
    )
    def assign(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            TicketWorkflowService.assign_ticket(
                ticket=ticket,
                technician_id=serializer.validated_data["technician_id"],
                actor_user_id=request.user.id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Start ticket work",
        description=(
            "Moves the ticket into active work state when start conditions are "
            "satisfied and opens a running work session for the assigned technician."
        ),
    )
    def start(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            TicketWorkflowService.start_ticket(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Move ticket to waiting QC",
        description=(
            "Transitions the ticket from work to waiting-for-QC state after the "
            "technician stops the active work session."
        ),
    )
    def to_waiting_qc(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            TicketWorkflowService.move_ticket_to_waiting_qc(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Mark ticket as QC passed",
        description=(
            "Marks the ticket as QC passed and runs completion side effects like XP awarding."
        ),
    )
    def qc_pass(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            TicketWorkflowService.qc_pass_ticket(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Mark ticket as QC failed",
        description=(
            "Marks the ticket as QC failed and sends it back through the rework path."
        ),
    )
    def qc_fail(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            TicketWorkflowService.qc_fail_ticket(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Approve ticket admin review",
        description=(
            "Approves ticket admin review and moves ticket from UNDER_REVIEW to NEW when applicable."
        ),
    )
    def review_approve(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            TicketWorkflowService.approve_ticket_review(
                ticket=ticket,
                actor_user_id=request.user.id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Set ticket manual metrics",
        description=(
            "Manually overrides ticket flag color and XP amount, and marks the "
            "ticket as manual metrics mode without approving admin review."
        ),
    )
    def manual_metrics(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TicketWorkflowService.set_manual_ticket_metrics(
            ticket=ticket,
            flag_color=serializer.validated_data["flag_color"],
            xp_amount=serializer.validated_data["xp_amount"],
        )
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    def _ticket(self, pk: int) -> Ticket:
        return get_object_or_404(self.get_queryset(), pk=pk)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="List ticket transitions",
    description=(
        "Returns workflow transition history for a specific ticket in reverse chronological order."
    ),
)
class TicketTransitionListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TicketTransitionSerializer
    queryset = TicketTransition.objects.select_related("actor", "ticket").order_by(
        "-created_at", "-id"
    )

    def get_queryset(self):
        return self.queryset.filter(ticket_id=self.kwargs["pk"])
