from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from account.models import AccessRequest, User
from account.services import (
    approve_access_request,
    ensure_pending_access_request,
    reject_access_request,
)
from api.v1.account.serializers import (
    AccessRequestApproveSerializer,
    AccessRequestCreateSerializer,
    AccessRequestSerializer,
    UserSerializer,
)
from core.api.permissions import HasRole
from core.api.views import BaseAPIView
from core.utils.constants import AccessRequestStatus, RoleSlug

AccessRequestManagerPermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER
)


class MeAPIView(BaseAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RequestAccessAPIView(BaseAPIView):
    serializer_class = AccessRequestCreateSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_request, created = ensure_pending_access_request(
            telegram_id=serializer.validated_data["telegram_id"],
            username=serializer.validated_data.get("username"),
            first_name=serializer.validated_data.get("first_name"),
            last_name=serializer.validated_data.get("last_name"),
            phone=serializer.validated_data.get("phone"),
            note=serializer.validated_data.get("note"),
        )
        output = AccessRequestSerializer(access_request).data
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(output, status=http_status)


class AccessRequestListAPIView(BaseAPIView):
    serializer_class = AccessRequestSerializer
    permission_classes = (IsAuthenticated, AccessRequestManagerPermission)

    def get(self, request, *args, **kwargs):
        status_query = request.query_params.get("status", AccessRequestStatus.PENDING)
        if status_query not in AccessRequestStatus.values:
            return Response(
                {
                    "detail": f"Invalid status value. Allowed: {', '.join(AccessRequestStatus.values)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = (
            AccessRequest.objects.select_related("user")
            .filter(status=status_query)
            .order_by("-created_at")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
        payload = serializer.validated_data
        user_id = payload.get("user_id")
        if user_id:
            user = User.objects.get(pk=user_id)
        else:
            user_data = payload["user"]
            try:
                user = User.objects.create_user(
                    username=user_data["username"],
                    password=None,
                    first_name=user_data["first_name"],
                    email=user_data["email"],
                    last_name=user_data.get("last_name"),
                    patronymic=user_data.get("patronymic"),
                    phone=user_data.get("phone") or access_request.phone,
                )
            except IntegrityError:
                return Response(
                    {"detail": "User with provided identity fields already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        approved = approve_access_request(
            access_request=access_request,
            user=user,
            role_slugs=payload.get("role_slugs", []),
        )
        output = AccessRequestSerializer(approved).data
        return Response(output, status=status.HTTP_200_OK)


class AccessRequestRejectAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated, AccessRequestManagerPermission)

    def post(self, request, *args, **kwargs):
        access_request = get_object_or_404(AccessRequest.objects, pk=kwargs["pk"])
        if access_request.status != AccessRequestStatus.PENDING:
            return Response(
                {"detail": "Access request is already resolved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rejected = reject_access_request(access_request)
        output = AccessRequestSerializer(rejected).data
        return Response(output, status=status.HTTP_200_OK)
