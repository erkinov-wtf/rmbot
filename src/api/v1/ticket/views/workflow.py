from django.db.models import F, Q, Value
from django.db.models.functions import Replace, Upper
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
    TicketClaimSerializer,
    TicketCompletePartsSerializer,
    TicketManualMetricsSerializer,
    TicketPartCompletionSerializer,
    TicketQCFailSerializer,
    TicketSerializer,
    TicketTransitionSerializer,
)
from core.api.schema import extend_schema
from core.api.views import BaseViewSet, ListAPIView
from core.utils.constants import TicketStatus
from inventory.services import InventoryItemService
from ticket.models import Ticket, TicketPartCompletion, TicketTransition
from ticket.services_workflow import TicketWorkflowService


class TicketWorkflowViewSet(BaseViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = TicketAssignSerializer
    queryset = Ticket.objects.select_related(
        "inventory_item", "master", "technician"
    ).prefetch_related(
        "part_specs__inventory_item_part",
        "part_specs__completed_by",
        "part_specs__rework_for_technician",
        "part_specs__completion_history__technician",
        "part_specs__completion_history__ticket_part_spec__inventory_item_part",
        "part_completions__technician",
        "part_completions__ticket_part_spec__inventory_item_part",
    )

    def get_serializer_class(self):
        if self.action == "manual_metrics":
            return TicketManualMetricsSerializer
        if self.action == "claim":
            return TicketClaimSerializer
        if self.action == "complete_parts":
            return TicketCompletePartsSerializer
        if self.action == "qc_fail":
            return TicketQCFailSerializer
        return super().get_serializer_class()

    def get_permissions(self):

        permission_classes = self.permission_classes

        if self.action == "assign":
            permission_classes += (TicketAssignPermission,)
        elif self.action == "review_approve":
            permission_classes += (TicketReviewPermission,)
        elif self.action == "manual_metrics":
            permission_classes += (TicketManualMetricsPermission,)
        elif self.action in (
            "start",
            "to_waiting_qc",
            "claim",
            "complete_parts",
            "claimable",
            "active_pool",
            "todo",
        ):
            permission_classes += (TicketWorkPermission,)
        elif self.action in ("qc_pass", "qc_fail"):
            permission_classes += (TicketQCPermission,)

        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Assign technician to ticket",
        description="Assigns a technician to the ticket and applies assignment workflow rules.",
    )
    def assign(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TicketWorkflowService.assign_ticket(
            ticket=ticket,
            technician_id=serializer.validated_data["technician_id"],
            actor_user_id=request.user.id,
        )
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="List claimable active tickets",
        description=(
            "Returns common pool tickets claimable by the authenticated technician."
        ),
    )
    def claimable(self, request, *args, **kwargs):
        queryset = (
            TicketWorkflowService.claimable_tickets_queryset_for_technician(
                technician_id=request.user.id
            )
            .select_related("inventory_item", "master", "technician")
            .prefetch_related(
                "part_specs__inventory_item_part",
                "part_specs__completed_by",
                "part_specs__rework_for_technician",
                "part_specs__completion_history__technician",
                "part_specs__completion_history__ticket_part_spec__inventory_item_part",
                "part_completions__technician",
                "part_completions__ticket_part_spec__inventory_item_part",
            )
            .order_by("-created_at", "-id")
        )
        queryset = self._apply_search_filter(
            queryset=queryset,
            q_filter=self.request.query_params.get("q"),
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TicketSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)
        serializer = TicketSerializer(
            queryset,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="List active pool tickets",
        description=(
            "Alias for claimable tickets, used by mini-app/dashboard active pool."
        ),
    )
    def active_pool(self, request, *args, **kwargs):
        return self.claimable(request, *args, **kwargs)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="List technician todo tickets",
        description=(
            "Returns active tickets currently claimed by the authenticated technician."
        ),
    )
    def todo(self, request, *args, **kwargs):
        queryset = (
            Ticket.objects.select_related("inventory_item", "master", "technician")
            .prefetch_related(
                "part_specs__inventory_item_part",
                "part_specs__completed_by",
                "part_specs__rework_for_technician",
                "part_specs__completion_history__technician",
                "part_specs__completion_history__ticket_part_spec__inventory_item_part",
                "part_completions__technician",
                "part_completions__ticket_part_spec__inventory_item_part",
            )
            .filter(
                technician_id=request.user.id,
                status__in=[
                    TicketStatus.ASSIGNED,
                    TicketStatus.IN_PROGRESS,
                    TicketStatus.REWORK,
                ],
                deleted_at__isnull=True,
            )
            .order_by("-created_at", "-id")
        )
        queryset = self._apply_search_filter(
            queryset=queryset,
            q_filter=self.request.query_params.get("q"),
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TicketSerializer(
                page,
                many=True,
                context={"request": request},
            )
            return self.get_paginated_response(serializer.data)
        serializer = TicketSerializer(
            queryset,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Claim ticket from active pool",
        description=("Technician self-claims a ticket from the common active pool."),
    )
    def claim(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        claimed_ticket = TicketWorkflowService.claim_ticket(
            ticket=ticket,
            actor_user_id=request.user.id,
        )
        return Response(
            TicketSerializer(claimed_ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Complete selected parts",
        description=(
            "Marks selected part specs completed by the claiming technician. "
            "If all parts complete, ticket auto-moves to WAITING_QC."
        ),
    )
    def complete_parts(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_ticket = TicketWorkflowService.complete_ticket_parts(
            ticket=ticket,
            actor_user_id=request.user.id,
            part_payloads=serializer.validated_data["parts"],
        )
        return Response(
            TicketSerializer(updated_ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

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
        TicketWorkflowService.start_ticket(ticket=ticket, actor_user_id=request.user.id)
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

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
        TicketWorkflowService.move_ticket_to_waiting_qc(
            ticket=ticket, actor_user_id=request.user.id
        )
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Mark ticket as QC passed",
        description="Marks the ticket as QC passed and runs completion side effects like XP awarding.",
    )
    def qc_pass(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        TicketWorkflowService.qc_pass_ticket(
            ticket=ticket, actor_user_id=request.user.id
        )
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Mark ticket as QC failed",
        description="Marks the ticket as QC failed and sends it back through the rework path.",
    )
    def qc_fail(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        payload_data = request.data
        if not payload_data:
            payload_data = {
                "failed_part_ids": list(
                    ticket.part_specs.filter(deleted_at__isnull=True).values_list(
                        "id",
                        flat=True,
                    )
                )
            }
        serializer = self.get_serializer(data=payload_data)
        serializer.is_valid(raise_exception=True)

        updated_ticket = TicketWorkflowService.qc_fail_ticket(
            ticket=ticket,
            actor_user_id=request.user.id,
            failed_part_spec_ids=serializer.validated_data["failed_part_ids"],
            note=serializer.validated_data.get("note"),
        )
        return Response(
            TicketSerializer(updated_ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Approve ticket admin review",
        description="Approves ticket admin review and moves ticket from UNDER_REVIEW to NEW when applicable.",
    )
    def review_approve(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        TicketWorkflowService.approve_ticket_review(
            ticket=ticket, actor_user_id=request.user.id
        )
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

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
        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def _ticket(self, pk: int) -> Ticket:
        return get_object_or_404(self.get_queryset(), pk=pk)

    @staticmethod
    def _apply_search_filter(queryset, q_filter: str | None):
        search_value = str(q_filter or "").strip()
        if not search_value:
            return queryset

        text_query = search_value.lstrip("#").strip()
        serial_query = InventoryItemService.normalize_serial_search_query(text_query)
        if not text_query and not serial_query:
            return queryset.none()

        search_filter = Q(pk__in=[])
        if serial_query:
            queryset = queryset.annotate(
                _serial_search=Upper(
                    Replace(F("inventory_item__serial_number"), Value("-"), Value(""))
                )
            )
            search_filter |= Q(_serial_search__icontains=serial_query)

        if text_query:
            search_filter |= Q(title__icontains=text_query)
        if text_query.isdigit():
            search_filter |= Q(id=int(text_query))
        return queryset.filter(search_filter)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="List ticket transitions",
    description="Returns workflow transition history for a specific ticket in reverse chronological order.",
)
class TicketTransitionListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TicketTransitionSerializer
    queryset = TicketTransition.objects.select_related("actor", "ticket").order_by(
        "-created_at", "-id"
    )

    def get_queryset(self):
        return self.queryset.filter(ticket_id=self.kwargs["pk"])


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="List ticket part completion history",
    description=(
        "Returns per-part completion audit history (who completed which part and when)."
    ),
)
class TicketPartCompletionHistoryListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TicketPartCompletionSerializer
    queryset = TicketPartCompletion.objects.select_related(
        "technician",
        "ticket_part_spec",
        "ticket_part_spec__inventory_item_part",
        "ticket",
    ).order_by("-completed_at", "-id")

    def get_queryset(self):
        return self.queryset.filter(ticket_id=self.kwargs["pk"])
