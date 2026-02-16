from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from account.models import AccessRequest, User
from account.services import AccountService
from api.v1.account.filters import AccessRequestFilterSet
from api.v1.account.serializers import (
    AccessRequestApproveSerializer,
    AccessRequestSerializer,
    UserOptionSerializer,
    UserSerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, ListAPIView
from core.utils.constants import AccessRequestStatus, RoleSlug

AccessRequestManagerPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER
)
UserOptionsPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER
)


@extend_schema(
    tags=["Users / Profile"],
    summary="Get current user profile",
    description="Returns the authenticated user's profile, including roles and linked Telegram data.",
)
class MeAPIView(BaseAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Users / Profile"],
    summary="List user options",
    description=(
        "Lists active users for admin/operator assignment flows. "
        "Supports optional free-text q search over identity fields."
    ),
)
class UserOptionListAPIView(ListAPIView):
    serializer_class = UserOptionSerializer
    permission_classes = (IsAuthenticated, UserOptionsPermission)
    queryset = User.objects.filter(is_active=True).prefetch_related("roles").order_by(
        "first_name", "last_name", "username", "id"
    )

    def get_queryset(self):
        queryset = self.queryset
        search = str(self.request.query_params.get("q", "")).strip()
        if not search:
            return queryset

        return queryset.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone__icontains=search)
        )


@extend_schema(
    tags=["Users / Access Requests"],
    summary="List access requests by status",
    description="Lists onboarding access requests filtered by status for manager roles.",
)
class AccessRequestListAPIView(ListAPIView):
    serializer_class = AccessRequestSerializer
    queryset = AccessRequest.objects.select_related("user").order_by(
        "-created_at", "-id"
    )
    permission_classes = (IsAuthenticated, AccessRequestManagerPermission)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AccessRequestFilterSet


@extend_schema(
    tags=["Users / Access Requests"],
    summary="Approve access request",
    description="Approves a pending bot-submitted access request and activates its pre-created user.",
)
class AccessRequestApproveAPIView(BaseAPIView):
    serializer_class = AccessRequestApproveSerializer
    permission_classes = (IsAuthenticated, AccessRequestManagerPermission)

    def post(self, request, *args, **kwargs):
        access_request = get_object_or_404(AccessRequest.objects, pk=kwargs["pk"])
        if access_request.status != AccessRequestStatus.PENDING:
            return Response(
                {"detail": "Access request is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            approved = AccountService.approve_access_request(
                access_request=access_request,
                role_slugs=serializer.validated_data.get("role_slugs", []),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        output = AccessRequestSerializer(approved).data
        return Response(output, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Users / Access Requests"],
    summary="Reject access request",
    description="Rejects a pending onboarding access request and marks it as resolved.",
)
class AccessRequestRejectAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AccessRequestManagerPermission)

    def post(self, request, *args, **kwargs):
        access_request = get_object_or_404(AccessRequest.objects, pk=kwargs["pk"])
        if access_request.status != AccessRequestStatus.PENDING:
            return Response(
                {"detail": "Access request is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rejected = AccountService.reject_access_request(access_request)
        output = AccessRequestSerializer(rejected).data
        return Response(output, status=status.HTTP_200_OK)
