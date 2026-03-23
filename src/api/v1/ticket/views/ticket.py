from django.db.models import F, Q, Value
from django.db.models.functions import Replace, Upper
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.ticket.permissions import (
    TicketCreatePermission,
    TicketDeletePermission,
    TicketEditPermission,
)
from api.v1.ticket.serializers import TicketSerializer, TicketUpdateSerializer
from core.api.schema import extend_schema
from core.api.views import BaseModelViewSet
from core.utils.constants import TicketStatus, TicketTransitionAction
from inventory.services import InventoryItemService
from ticket.models import Ticket
from ticket.services_delete import TicketDeleteService


class TicketViewSet(BaseModelViewSet):
    serializer_class = TicketSerializer
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
        .order_by("-created_at")
    )

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return TicketUpdateSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = str(self.request.query_params.get("status", "")).strip()
        if status_filter:
            allowed_statuses = {status for status, _ in TicketStatus.choices}
            if status_filter not in allowed_statuses:
                return queryset.none()
            queryset = queryset.filter(status=status_filter)

        technician_filter = str(
            self.request.query_params.get("technician", "")
        ).strip()
        if technician_filter:
            try:
                technician_id = int(technician_filter)
            except (TypeError, ValueError):
                return queryset.none()
            if technician_id < 1:
                return queryset.none()
            queryset = queryset.filter(technician_id=technician_id)

        q_filter = str(self.request.query_params.get("q", "")).strip()
        if q_filter:
            text_query = q_filter.lstrip("#").strip()
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
            queryset = queryset.filter(search_filter)

        return queryset

    def get_permissions(self):
        permission_classes = [IsAuthenticated]

        if self.action == "create":
            permission_classes += [TicketCreatePermission]
        if self.action in {"update", "partial_update"}:
            permission_classes += [TicketEditPermission]
        if self.action in {"destroy", "bulk_destroy"}:
            permission_classes += [TicketDeletePermission]

        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Create ticket",
        description=(
            "Creates a new ticket intake by inventory-item serial number with "
            "part-level specs, auto-computed ticket metrics (minutes/flag/XP), and "
            "initial NEW status. Unknown serials are auto-created in inventory."
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

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Update ticket",
        description=(
            "Updates an existing editable ticket before work history exists. "
            "Supports title, total minutes, and active part selection changes."
        ),
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        ticket = self.get_object()
        serializer = self.get_serializer(
            ticket,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        updated_ticket = serializer.save()
        refreshed_ticket = self.get_queryset().get(pk=updated_ticket.pk)
        response_serializer = TicketSerializer(
            refreshed_ticket,
            context={"request": request},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Delete ticket",
        description=(
            "Soft-deletes ticket and all related ticket-level history records "
            "(parts, transitions, work sessions)."
        ),
    )
    def destroy(self, request, *args, **kwargs):
        ticket = self.get_object()
        TicketDeleteService.delete_ticket(ticket=ticket)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Tickets / Workflow"],
        summary="Bulk delete tickets",
        description=(
            "Soft-deletes every ticket matching the current list filters and "
            "removes related ticket-level history records (parts, transitions, "
            "work sessions)."
        ),
    )
    def bulk_destroy(self, request, *args, **kwargs):
        summary = TicketDeleteService.delete_queryset(
            queryset=self.filter_queryset(self.get_queryset())
        )
        return Response(
            {"deleted_count": summary["deleted_ticket_count"]},
            status=status.HTTP_200_OK,
        )

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
