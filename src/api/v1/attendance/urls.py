from django.urls import path

from api.v1.attendance.views import (
    AttendanceCheckInAPIView,
    AttendanceCheckOutAPIView,
    AttendanceRecordsAPIView,
)

app_name = "attendance"

urlpatterns = [
    path("records/", AttendanceRecordsAPIView.as_view(), name="attendance-records"),
    path("checkin/", AttendanceCheckInAPIView.as_view(), name="attendance-checkin"),
    path("checkout/", AttendanceCheckOutAPIView.as_view(), name="attendance-checkout"),
]
