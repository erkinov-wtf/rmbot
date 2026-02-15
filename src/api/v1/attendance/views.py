from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.attendance.filters import AttendanceRecordFilterSet
from api.v1.attendance.serializers import (
    AttendanceRecordListItemSerializer,
    AttendanceRecordSerializer,
    AttendanceTechnicianInputSerializer,
)
from attendance.models import AttendanceRecord
from attendance.services import AttendanceService
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, ListAPIView
from core.utils.constants import RoleSlug

AttendanceManagerPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN,
    RoleSlug.OPS_MANAGER,
    RoleSlug.MASTER,
)


@extend_schema(
    tags=["Attendance"],
    summary="List attendance records for a day with filters",
    description=(
        "Returns attendance records for the selected work date (defaults to current "
        "business date). Supports optional filtering by technician and punctuality "
        "bucket (`early`, `on_time`, `late`)."
    ),
)
class AttendanceRecordsAPIView(ListAPIView):
    permission_classes = (IsAuthenticated, AttendanceManagerPermission)
    serializer_class = AttendanceRecordListItemSerializer
    queryset = (
        AttendanceRecord.domain.get_queryset()
        .select_related("user")
        .order_by("user_id", "id")
    )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AttendanceRecordFilterSet

    def get_queryset(self):
        return self.queryset


@extend_schema(
    tags=["Attendance"],
    summary="Check in technician for today",
    description="Checks the selected technician in for today and returns the attendance "
    "record with awarded XP.",
)
class AttendanceCheckInAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AttendanceManagerPermission)
    serializer_class = AttendanceTechnicianInputSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            record, xp_awarded = AttendanceService.check_in(
                user_id=serializer.validated_data["technician_id"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "attendance": AttendanceRecordSerializer(record).data,
                "xp_awarded": xp_awarded,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Attendance"],
    summary="Check out technician for today",
    description="Checks the selected technician out for today and returns the updated "
    "attendance record.",
)
class AttendanceCheckOutAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AttendanceManagerPermission)
    serializer_class = AttendanceTechnicianInputSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            record = AttendanceService.check_out(
                user_id=serializer.validated_data["technician_id"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AttendanceRecordSerializer(record).data, status=status.HTTP_200_OK
        )
