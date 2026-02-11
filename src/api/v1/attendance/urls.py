from django.urls import path

from api.v1.attendance.views import AttendanceCheckInAPIView, AttendanceCheckOutAPIView, AttendanceTodayAPIView

app_name = "attendance"

urlpatterns = [
    path("today/", AttendanceTodayAPIView.as_view(), name="attendance-today"),
    path("checkin/", AttendanceCheckInAPIView.as_view(), name="attendance-checkin"),
    path("checkout/", AttendanceCheckOutAPIView.as_view(), name="attendance-checkout"),
]
