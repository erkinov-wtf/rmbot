from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceRecord
from core.api.permissions import HasRole
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from gamification.models import XPLedger
from ticket.models import TicketTransition


class HealthAPIView(generics.RetrieveAPIView):
    permission_classes = []

    def retrieve(self, request, *args, **kwargs):
        return Response(data={"status": "ok"}, status=200)


class TestAPIView(generics.RetrieveAPIView):
    permission_classes = []

    def retrieve(self, request, *args, **kwargs):
        return Response(data={"message": "This is a test endpoint."}, status=200)


AuditFeedPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


class AuditFeedAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AuditFeedPermission)

    def get(self, request, *args, **kwargs):
        try:
            requested_limit = int(request.query_params.get("limit", "50"))
        except ValueError:
            return Response(
                {"detail": "limit must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit = max(1, min(requested_limit, 200))
        pool_size = max(limit * 3, 50)
        events = []

        transitions = TicketTransition.objects.select_related(
            "actor", "ticket"
        ).order_by("-created_at")[:pool_size]
        for tr in transitions:
            events.append(
                {
                    "timestamp_dt": tr.created_at,
                    "timestamp": tr.created_at.isoformat(),
                    "event_type": "ticket_transition",
                    "entity_id": tr.id,
                    "ticket_id": tr.ticket_id,
                    "actor_id": tr.actor_id,
                    "action": tr.action,
                    "from_status": tr.from_status,
                    "to_status": tr.to_status,
                    "metadata": tr.metadata or {},
                }
            )

        xp_entries = XPLedger.objects.select_related("user").order_by("-created_at")[
            :pool_size
        ]
        for xp in xp_entries:
            events.append(
                {
                    "timestamp_dt": xp.created_at,
                    "timestamp": xp.created_at.isoformat(),
                    "event_type": "xp_ledger",
                    "entity_id": xp.id,
                    "user_id": xp.user_id,
                    "amount": xp.amount,
                    "entry_type": xp.entry_type,
                    "reference": xp.reference,
                    "payload": xp.payload or {},
                }
            )

        attendance_records = AttendanceRecord.objects.filter(
            Q(check_in_at__isnull=False) | Q(check_out_at__isnull=False)
        ).order_by("-updated_at")[:pool_size]
        for row in attendance_records:
            if row.check_in_at:
                events.append(
                    {
                        "timestamp_dt": row.check_in_at,
                        "timestamp": row.check_in_at.isoformat(),
                        "event_type": "attendance_check_in",
                        "entity_id": row.id,
                        "user_id": row.user_id,
                        "work_date": row.work_date.isoformat(),
                    }
                )
            if row.check_out_at:
                events.append(
                    {
                        "timestamp_dt": row.check_out_at,
                        "timestamp": row.check_out_at.isoformat(),
                        "event_type": "attendance_check_out",
                        "entity_id": row.id,
                        "user_id": row.user_id,
                        "work_date": row.work_date.isoformat(),
                    }
                )

        events.sort(key=lambda item: item["timestamp_dt"], reverse=True)
        result = []
        for item in events[:limit]:
            payload = dict(item)
            payload.pop("timestamp_dt", None)
            result.append(payload)

        return Response(result, status=status.HTTP_200_OK)
