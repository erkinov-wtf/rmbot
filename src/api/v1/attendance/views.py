from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.services import check_in, check_out, get_today_record
from core.api.views import BaseAPIView

from api.v1.attendance.serializers import AttendanceRecordSerializer


class AttendanceTodayAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        record = get_today_record(user_id=request.user.id)
        if not record:
            return Response(None, status=status.HTTP_200_OK)
        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_200_OK)


class AttendanceCheckInAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            record, xp_awarded = check_in(user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "attendance": AttendanceRecordSerializer(record).data,
                "xp_awarded": xp_awarded,
            },
            status=status.HTTP_200_OK,
        )


class AttendanceCheckOutAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            record = check_out(user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_200_OK)
