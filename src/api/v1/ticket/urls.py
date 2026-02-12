from django.urls import path

from api.v1.ticket.views import (
    TicketViewSet,
    TicketWorkflowViewSet,
    TicketWorkSessionViewSet,
)

app_name = "ticket"

urlpatterns = [
    path("", TicketViewSet.as_view({"get": "list"}), name="ticket-list"),
    path("create/", TicketViewSet.as_view({"post": "create"}), name="ticket-create"),
    path("<int:pk>/", TicketViewSet.as_view({"get": "retrieve"}), name="ticket-detail"),
    path(
        "<int:pk>/assign/",
        TicketWorkflowViewSet.as_view({"post": "assign"}),
        name="ticket-assign",
    ),
    path(
        "<int:pk>/transitions/",
        TicketWorkflowViewSet.as_view({"get": "transitions"}),
        name="ticket-transitions",
    ),
    path(
        "<int:pk>/start/",
        TicketWorkflowViewSet.as_view({"post": "start"}),
        name="ticket-start",
    ),
    path(
        "<int:pk>/to-waiting-qc/",
        TicketWorkflowViewSet.as_view({"post": "to_waiting_qc"}),
        name="ticket-to-waiting-qc",
    ),
    path(
        "<int:pk>/qc-pass/",
        TicketWorkflowViewSet.as_view({"post": "qc_pass"}),
        name="ticket-qc-pass",
    ),
    path(
        "<int:pk>/qc-fail/",
        TicketWorkflowViewSet.as_view({"post": "qc_fail"}),
        name="ticket-qc-fail",
    ),
    path(
        "<int:pk>/work-session/start/",
        TicketWorkSessionViewSet.as_view({"post": "start"}),
        name="ticket-work-session-start",
    ),
    path(
        "<int:pk>/work-session/pause/",
        TicketWorkSessionViewSet.as_view({"post": "pause"}),
        name="ticket-work-session-pause",
    ),
    path(
        "<int:pk>/work-session/resume/",
        TicketWorkSessionViewSet.as_view({"post": "resume"}),
        name="ticket-work-session-resume",
    ),
    path(
        "<int:pk>/work-session/stop/",
        TicketWorkSessionViewSet.as_view({"post": "stop"}),
        name="ticket-work-session-stop",
    ),
    path(
        "<int:pk>/work-session/history/",
        TicketWorkSessionViewSet.as_view({"get": "history"}),
        name="ticket-work-session-history",
    ),
]
