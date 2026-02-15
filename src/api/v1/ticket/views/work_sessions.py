from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.ticket.permissions import TicketWorkPermission
from api.v1.ticket.serializers import (
    WorkSessionSerializer,
    WorkSessionTransitionSerializer,
)
from core.api.schema import extend_schema
from core.api.views import BaseViewSet, ListAPIView
from ticket.models import Ticket, WorkSessionTransition
from ticket.services_work_session import TicketWorkSessionService


class TicketWorkSessionViewSet(BaseViewSet):
    serializer_class = WorkSessionSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician")

    def get_permissions(self):
        if self.action in {"pause", "resume", "stop"}:
            permission_classes = (IsAuthenticated, TicketWorkPermission)
        else:
            permission_classes = (IsAuthenticated,)
        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=["Tickets / Work Sessions"],
        summary="Pause ticket work session",
        description="Pauses the active work session timer for the specified ticket.",
    )
    def pause(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            session = TicketWorkSessionService.pause_work_session(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Work Sessions"],
        summary="Resume ticket work session",
        description="Resumes a paused work session timer for the specified ticket.",
    )
    def resume(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            session = TicketWorkSessionService.resume_work_session(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Tickets / Work Sessions"],
        summary="Stop ticket work session",
        description="Stops the active work session and persists accumulated work duration.",
    )
    def stop(self, request, pk: int, *args, **kwargs):
        ticket = self._ticket(pk)
        try:
            session = TicketWorkSessionService.stop_work_session(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)

    def _ticket(self, pk: int) -> Ticket:
        return get_object_or_404(self.get_queryset(), pk=pk)


@extend_schema(
    tags=["Tickets / Work Sessions"],
    summary="List ticket work-session history",
    description=(
        "Returns start, pause, resume, and stop events for all work sessions of "
        "the ticket."
    ),
)
class TicketWorkSessionHistoryListAPIView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = WorkSessionTransitionSerializer
    queryset = WorkSessionTransition.objects.select_related(
        "actor",
        "ticket",
        "work_session",
    ).order_by("-event_at", "-id")

    def get_queryset(self):
        return self.queryset.filter(ticket_id=self.kwargs["pk"])
