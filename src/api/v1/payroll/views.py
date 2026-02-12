from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.payroll.serializers import PayrollMonthlySerializer
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView
from core.utils.constants import RoleSlug
from payroll.services import PayrollService

PayrollManagerPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)


@extend_schema(
    tags=["Payroll"],
    summary="Get payroll month snapshot",
    description="Returns the generated payroll snapshot for the specified month if it exists.",
)
class PayrollMonthDetailAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def get(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            PayrollService.parse_month_token(month)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payroll_month = PayrollService.get_payroll_month(month_token=month)
        if not payroll_month:
            return Response(
                {"detail": "Payroll month was not generated yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Payroll"],
    summary="Close payroll month",
    description="Calculates and stores monthly payroll lines using active rules and marks the month as closed.",
)
class PayrollMonthCloseAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def post(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            payroll_month = PayrollService.close_payroll_month(
                month_token=month, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Payroll"],
    summary="Approve payroll month",
    description="Approves an already closed payroll month for final payout readiness.",
)
class PayrollMonthApproveAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, PayrollManagerPermission)

    def post(self, request, *args, **kwargs):
        month = kwargs["month"]
        try:
            payroll_month = PayrollService.approve_payroll_month(
                month_token=month, actor_user_id=request.user.id
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PayrollMonthlySerializer(payroll_month).data, status=status.HTTP_200_OK
        )
