from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from account.models import AccessRequest, Role, User
from account.services import AccountService
from api.v1.account.filters import AccessRequestFilterSet
from api.v1.account.serializers import (
    AccessRequestApproveSerializer,
    AccessRequestSerializer,
    RoleSerializer,
    UserManagementSerializer,
    UserManagementUpdateSerializer,
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
UserManagementPermission = HasRole.as_any(RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER)
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
    tags=["Users / Management"],
    summary="List system roles",
    description="Returns active role list for user-management role assignment.",
)
class RoleListAPIView(ListAPIView):
    serializer_class = RoleSerializer
    permission_classes = (IsAuthenticated, UserManagementPermission)
    queryset = Role.objects.filter(deleted_at__isnull=True).order_by("name", "id")


@extend_schema(
    tags=["Users / Management"],
    summary="List users",
    description=(
        "Lists users with profile, role, and telegram linkage data. "
        "Supports q search, role_slug, is_active, and ordering."
    ),
)
class UserManagementListAPIView(ListAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = (IsAuthenticated, UserManagementPermission)
    queryset = (
        User.objects.filter(deleted_at__isnull=True)
        .prefetch_related("roles", "telegram_profiles")
        .order_by("-created_at", "-id")
    )

    def get_queryset(self):
        queryset = self.queryset

        search = str(self.request.query_params.get("q", "")).strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
            )

        role_slug = str(self.request.query_params.get("role_slug", "")).strip()
        if role_slug:
            queryset = queryset.filter(
                roles__slug=role_slug,
                roles__deleted_at__isnull=True,
            ).distinct()

        is_active_raw = self.request.query_params.get("is_active")
        if is_active_raw is not None:
            normalized = str(is_active_raw).strip().lower()
            if normalized in {"1", "true", "yes"}:
                queryset = queryset.filter(is_active=True)
            elif normalized in {"0", "false", "no"}:
                queryset = queryset.filter(is_active=False)

        ordering = str(
            self.request.query_params.get("ordering", "-created_at")
        ).strip()
        allowed_orderings = {
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
            "username",
            "-username",
            "last_login",
            "-last_login",
        }
        if ordering not in allowed_orderings:
            ordering = "-created_at"
        return queryset.order_by(ordering, "-id")


@extend_schema(
    tags=["Users / Management"],
    summary="Get/update user management data",
    description=(
        "Returns a user by id and allows updating role assignments, active state, and level."
    ),
)
class UserManagementDetailAPIView(BaseAPIView):
    serializer_class = UserManagementUpdateSerializer
    permission_classes = (IsAuthenticated, UserManagementPermission)

    @staticmethod
    def _get_user_queryset():
        return User.objects.filter(deleted_at__isnull=True).prefetch_related(
            "roles",
            "telegram_profiles",
        )

    def get(self, request, *args, **kwargs):
        user = get_object_or_404(self._get_user_queryset(), pk=kwargs["pk"])
        output = UserManagementSerializer(user).data
        return Response(output, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        user = get_object_or_404(self._get_user_queryset(), pk=kwargs["pk"])

        if user.is_superuser and not request.user.is_superuser:
            return Response(
                {"detail": "Only super admins can update superuser accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(instance=user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if user.pk == request.user.pk and serializer.validated_data.get("is_active") is False:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        user.refresh_from_db()
        output = UserManagementSerializer(user).data
        return Response(output, status=status.HTTP_200_OK)


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
