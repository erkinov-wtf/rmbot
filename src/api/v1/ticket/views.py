from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api.permissions import HasRole
from core.api.views import BaseAPIView, CreateAPIView, ListAPIView
from core.utils.constants import RoleSlug, TicketTransitionAction
from ticket.models import Ticket, TicketTransition
from ticket.services import (
    assign_ticket,
    log_ticket_transition,
    move_ticket_to_waiting_qc,
    pause_work_session,
    qc_fail_ticket,
    qc_pass_ticket,
    resume_work_session,
    start_work_session,
    start_ticket,
    stop_work_session,
)

from api.v1.ticket.serializers import (
    TicketAssignSerializer,
    TicketSerializer,
    TicketTransitionSerializer,
    WorkSessionSerializer,
)


TicketCreatePermission = HasRole.as_any(RoleSlug.MASTER, RoleSlug.SUPER_ADMIN)
TicketAssignPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER)
TicketWorkPermission = HasRole.as_any(RoleSlug.TECHNICIAN, RoleSlug.SUPER_ADMIN)
TicketQCPermission = HasRole.as_any(RoleSlug.QC_INSPECTOR, RoleSlug.SUPER_ADMIN)


class TicketListAPIView(ListAPIView):
    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician").order_by("-created_at")


class TicketCreateAPIView(CreateAPIView):
    serializer_class = TicketSerializer
    queryset = Ticket.objects.select_related("bike", "master", "technician").all()
    permission_classes = (TicketCreatePermission,)

    def perform_create(self, serializer):
        ticket = serializer.save(master=self.request.user)
        log_ticket_transition(
            ticket=ticket,
            from_status=None,
            to_status=ticket.status,
            action=TicketTransitionAction.CREATED,
            actor_user_id=self.request.user.id,
        )


class TicketAssignAPIView(BaseAPIView):
    serializer_class = TicketAssignSerializer
    permission_classes = (IsAuthenticated, TicketAssignPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assign_ticket(
                ticket=ticket,
                technician_id=serializer.validated_data["technician_id"],
                actor_user_id=request.user.id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketStartAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            start_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketToWaitingQCAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            move_ticket_to_waiting_qc(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketQCPassAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketQCPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            qc_pass_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketQCFailAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketQCPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            qc_fail_ticket(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


class TicketTransitionListAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.only("id"), pk=kwargs["pk"])
        transitions = TicketTransition.objects.filter(ticket=ticket).select_related("actor").order_by("-created_at")
        serializer = TicketTransitionSerializer(transitions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TicketWorkSessionStartAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            session = start_work_session(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)


class TicketWorkSessionPauseAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            session = pause_work_session(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)


class TicketWorkSessionResumeAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            session = resume_work_session(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)


class TicketWorkSessionStopAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, TicketWorkPermission)

    def post(self, request, *args, **kwargs):
        ticket = get_object_or_404(Ticket.objects.select_related("bike", "master", "technician"), pk=kwargs["pk"])
        try:
            session = stop_work_session(ticket=ticket, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkSessionSerializer(session).data, status=status.HTTP_200_OK)
