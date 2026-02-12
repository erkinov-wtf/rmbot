from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.attendance.serializers import AttendanceRecordSerializer
from attendance.services import AttendanceService
from core.api.schema import extend_schema
from core.api.views import BaseAPIView


@extend_schema(
    tags=["Attendance"],
    summary="Get attendance record for today",
    description=(
        "Returns the authenticated user's attendance record for the current day. "
        "Returns null when no record exists yet."
    ),
)
class AttendanceTodayAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        record = AttendanceService.get_today_record(user_id=request.user.id)
        if not record:
            return Response(None, status=status.HTTP_200_OK)
        return Response(
            AttendanceRecordSerializer(record).data, status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Attendance"],
    summary="Check in for today",
    description="Checks the authenticated user in for today and returns the attendance record with awarded XP.",
)
class AttendanceCheckInAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            record, xp_awarded = AttendanceService.check_in(user_id=request.user.id)
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
    summary="Check out for today",
    description="Checks the authenticated user out for today and returns the updated attendance record.",
)
class AttendanceCheckOutAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            record = AttendanceService.check_out(user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AttendanceRecordSerializer(record).data, status=status.HTTP_200_OK
        )
