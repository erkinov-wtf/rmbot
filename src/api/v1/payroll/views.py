from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.api.permissions import HasRole
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from payroll.services import approve_payroll_month, close_payroll_month, get_payroll_month, parse_month_token

from api.v1.payroll.serializers import PayrollMonthlySerializer


PayrollManagerPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


class PayrollMonthDetailAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def get(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            parse_month_token(month)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payroll_month = get_payroll_month(month_token=month)
        if not payroll_month:
            return Response({"detail": "Payroll month was not generated yet."}, status=status.HTTP_404_NOT_FOUND)

        return Response(PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK)


class PayrollMonthCloseAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def post(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            payroll_month = close_payroll_month(month_token=month, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK)


class PayrollMonthApproveAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def post(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            payroll_month = approve_payroll_month(month_token=month, actor_user_id=request.user.id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK)
