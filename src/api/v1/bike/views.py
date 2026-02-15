from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from api.v1.bike.filters import BikeFilterSet
from api.v1.bike.serializers import BikeSerializer
from bike.models import Bike
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseModelViewSet
from core.utils.constants import RoleSlug

BikeManagePermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER, RoleSlug.MASTER
)


@extend_schema(
    tags=["Bikes"],
    summary="Bike CRUD",
    description=(
        "Provides bike list/create/update/delete operations. List supports filters "
        "by search query, bike code, status, active flag, active-ticket flag, date "
        "ranges, and ordering."
    ),
)
class BikeViewSet(BaseModelViewSet):
    serializer_class = BikeSerializer
    queryset = Bike.domain.get_queryset().order_by("-created_at")
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BikeFilterSet

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = (IsAuthenticated, BikeManagePermission)
        else:
            permission_classes = (IsAuthenticated,)
        return [permission() for permission in permission_classes]
