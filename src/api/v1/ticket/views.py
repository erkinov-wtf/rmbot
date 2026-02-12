from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.ticket.serializers import (
    TicketAssignSerializer,
    TicketSerializer,
    TicketTransitionSerializer,
    WorkSessionSerializer,
    WorkSessionTransitionSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, CreateAPIView, ListAPIView
from core.utils.constants import RoleSlug, TicketTransitionAction
from ticket.models import Ticket, TicketTransition
from ticket.services import TicketService

TicketCreatePermission = HasRole.as_any(RoleSlug.MASTER, RoleSlug.SUPER_ADMIN)
TicketAssignPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER
)
TicketWorkPermission = HasRole.as_any(RoleSlug.TECHNICIAN, RoleSlug.SUPER_ADMIN)
TicketQCPermission = HasRole.as_any(RoleSlug.QC_INSPECTOR, RoleSlug.SUPER_ADMIN)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="List tickets",
    description="Returns tickets with related bike, master, and technician data.",
)
class TicketListAPIView(ListAPIView):
    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician").order_by(
        "-created_at"
    )


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="Create ticket",
    description=(
        "Creates a new ticket intake with checklist snapshot and master-approved "
        "SRT, then records the initial workflow transition."
    ),
)
class TicketCreateAPIView(CreateAPIView):
    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician").all()
    permission_classes = (TicketCreatePermission,)

    def perform_create(self, serializer):
        ticket = serializer.save(master=self.request.user)
        TicketService.log_ticket_transition(
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


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="Assign technician to ticket",
    description="Assigns a technician to the ticket and applies assignment workflow rules.",
)
class TicketAssignAPIView(BaseAPIView):
    serializer_class = TicketAssignSerializer
    permission_classes = (IsAuthenticated, TicketAssignPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            TicketService.assign_ticket(
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
    description="Moves the ticket into active work state when start conditions are satisfied.",
)
class TicketStartAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            TicketService.start_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="Move ticket to waiting QC",
    description="Transitions the ticket from work to waiting-for-QC state.",
)
class TicketToWaitingQCAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            TicketService.move_ticket_to_waiting_qc(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="Mark ticket as QC passed",
    description="Marks the ticket as QC passed and runs completion side effects like XP awarding.",
)
class TicketQCPassAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketQCPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            TicketService.qc_pass_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="Mark ticket as QC failed",
    description="Marks the ticket as QC failed and sends it back through the rework path.",
)
class TicketQCFailAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketQCPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            TicketService.qc_fail_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Workflow"],
    summary="List ticket transitions",
    description="Returns workflow transition history for a specific ticket in reverse chronological order.",
)
class TicketTransitionListAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.only("id"), pk=kwargs["pk"])
        transitions = (
            TicketTransition.objects.filter(ticket=ticket)
            .select_related("actor")
            .order_by("-created_at")
        )
        serializer = TicketTransitionSerializer(transitions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Work Sessions"],
    summary="Start ticket work session",
    description="Starts an active technician work session timer for the specified ticket.",
)
class TicketWorkSessionStartAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            session = TicketService.start_work_session(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Work Sessions"],
    summary="Pause ticket work session",
    description="Pauses the active work session timer for the specified ticket.",
)
class TicketWorkSessionPauseAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            session = TicketService.pause_work_session(
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
class TicketWorkSessionResumeAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            session = TicketService.resume_work_session(
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
class TicketWorkSessionStopAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(
            Ticket.objects.select_related("bike", "master", "technician"),
            pk=kwargs["pk"],
        )
        try:
            session = TicketService.stop_work_session(
                ticket=ticket, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Tickets / Work Sessions"],
    summary="List ticket work-session history",
    description="Returns start, pause, resume, and stop events for all work sessions of the ticket.",
)
class TicketWorkSessionHistoryAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.only("id"), pk=kwargs["pk"])
        history = TicketService.get_ticket_work_session_history(ticket=ticket)
        serializer = WorkSessionTransitionSerializer(history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
