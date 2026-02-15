from django.db.models import Q
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceRecord
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import ListAPIView
from core.utils.constants import RoleSlug
from gamification.models import XPTransaction
from ticket.models import TicketTransition


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class AuditFeedEventSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return instance


@extend_schema(
    tags=["System / Health"],
    summary="Health check",
    description="Lightweight service health endpoint for readiness and uptime checks.",
)
class HealthAPIView(generics.RetrieveAPIView):
    permission_classes = []
    serializer_class = HealthSerializer

    def retrieve(self, request, *args, **kwargs):
        return Response(data={"status": "ok"}, status=200)


AuditFeedPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


@extend_schema(
    tags=["System / Audit Feed"],
    summary="List recent audit feed events",
    description=(
        "Returns recent operational events merged from ticket transitions, "
        "XP transaction changes, and attendance actions."
    ),
)
class AuditFeedAPIView(ListAPIView):
    permission_classes = (IsAuthenticated, AuditFeedPermission)
    serializer_class = AuditFeedEventSerializer

    def get_queryset(self):
        requested_page = self._safe_positive_int(
            raw_value=self.request.query_params.get("page"),
            fallback=1,
        )
        default_per_page = getattr(self.pagination_class, "page_size", 10)
        requested_per_page = self._safe_positive_int(
            raw_value=self.request.query_params.get("per_page"),
            fallback=default_per_page,
        )
        pool_size = min(max(requested_page * requested_per_page * 4, 50), 5000)
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

        xp_transactions = XPTransaction.objects.select_related("user").order_by(
            "-created_at"
        )[:pool_size]
        for xp in xp_transactions:
            events.append(
                {
                    "timestamp_dt": xp.created_at,
                    "timestamp": xp.created_at.isoformat(),
                    "event_type": "xp_transaction",
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
        for payload in events:
            payload.pop("timestamp_dt", None)
        return events

    @staticmethod
    def _safe_positive_int(*, raw_value: str | None, fallback: int) -> int:
        try:
            parsed_value = int(raw_value)
            if parsed_value > 0:
                return parsed_value
        except (TypeError, ValueError):
            pass
        return fallback
