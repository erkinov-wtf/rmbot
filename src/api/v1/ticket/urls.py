from django.urls import path

from api.v1.ticket.views import (
    TicketAssignAPIView,
    TicketCreateAPIView,
    TicketListAPIView,
    TicketQCFailAPIView,
    TicketQCPassAPIView,
    TicketStartAPIView,
    TicketToWaitingQCAPIView,
    TicketTransitionListAPIView,
    TicketWorkSessionPauseAPIView,
    TicketWorkSessionResumeAPIView,
    TicketWorkSessionStartAPIView,
    TicketWorkSessionStopAPIView,
)

app_name = "ticket"

urlpatterns = [
    path("", TicketListAPIView.as_view(), name="ticket-list"),
    path("create/", TicketCreateAPIView.as_view(), name="ticket-create"),
    path("<int:pk>/assign/", TicketAssignAPIView.as_view(), name="ticket-assign"),
    path(
        "<int:pk>/transitions/",
        TicketTransitionListAPIView.as_view(),
        name="ticket-transitions",
    ),
    path("<int:pk>/start/", TicketStartAPIView.as_view(), name="ticket-start"),
    path(
        "<int:pk>/to-waiting-qc/",
        TicketToWaitingQCAPIView.as_view(),
        name="ticket-to-waiting-qc",
    ),
    path("<int:pk>/qc-pass/", TicketQCPassAPIView.as_view(), name="ticket-qc-pass"),
    path("<int:pk>/qc-fail/", TicketQCFailAPIView.as_view(), name="ticket-qc-fail"),
    path(
        "<int:pk>/work-session/start/",
        TicketWorkSessionStartAPIView.as_view(),
        name="ticket-work-session-start",
    ),
    path(
        "<int:pk>/work-session/pause/",
        TicketWorkSessionPauseAPIView.as_view(),
        name="ticket-work-session-pause",
    ),
    path(
        "<int:pk>/work-session/resume/",
        TicketWorkSessionResumeAPIView.as_view(),
        name="ticket-work-session-resume",
    ),
    path(
        "<int:pk>/work-session/stop/",
        TicketWorkSessionStopAPIView.as_view(),
        name="ticket-work-session-stop",
    ),
]
