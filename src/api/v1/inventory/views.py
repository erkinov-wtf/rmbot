from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.inventory.filters import InventoryItemFilterSet
from api.v1.inventory.serializers import (
    InventoryItemCategorySerializer,
    InventoryItemPartSerializer,
    InventoryItemSerializer,
    InventorySerializer,
)
from core.api.permissions import HasRole
from core.api.schema import extend_schema
from core.api.views import BaseAPIView, BaseModelViewSet
from core.utils.constants import RoleSlug
from inventory.models import (
    Inventory,
    InventoryItem,
    InventoryItemCategory,
    InventoryItemPart,
)

InventoryManagePermission = HasRole.as_any(
    RoleSlug.SUPER_ADMIN,
    RoleSlug.OPS_MANAGER,
    RoleSlug.MASTER,
)


class InventoryManageMixin:
    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            permission_classes = (IsAuthenticated, InventoryManagePermission)
        else:
            permission_classes = (IsAuthenticated,)
        return [permission() for permission in permission_classes]


@extend_schema(
    tags=["Inventory"],
    summary="Inventory items CRUD",
    description=(
        "Provides inventory-item list/create/update/delete operations. List supports "
        "filters by search query, serial number, inventory, category, status, "
        "active flag, active-ticket flag, date ranges, and ordering."
    ),
)
class InventoryItemViewSet(InventoryManageMixin, BaseModelViewSet):
    serializer_class = InventoryItemSerializer
    queryset = InventoryItem.domain.get_queryset().order_by("-created_at")
    filter_backends = (DjangoFilterBackend,)
    filterset_class = InventoryItemFilterSet


@extend_schema(
    tags=["Inventory"],
    summary="Inventory CRUD",
    description="Provides inventory list/create/update/delete operations.",
)
class InventoryViewSet(InventoryManageMixin, BaseModelViewSet):
    serializer_class = InventorySerializer
    queryset = Inventory.domain.get_queryset().order_by("name", "id")


@extend_schema(
    tags=["Inventory"],
    summary="Inventory item categories CRUD",
    description="Provides inventory-item category list/create/update/delete operations.",
)
class InventoryItemCategoryViewSet(InventoryManageMixin, BaseModelViewSet):
    serializer_class = InventoryItemCategorySerializer
    queryset = InventoryItemCategory.domain.get_queryset().order_by("name", "id")


@extend_schema(
    tags=["Inventory"],
    summary="Inventory category parts CRUD",
    description=(
        "Provides category-level inventory part list/create/update/delete operations."
    ),
)
class InventoryItemPartViewSet(InventoryManageMixin, BaseModelViewSet):
    serializer_class = InventoryItemPartSerializer
    queryset = InventoryItemPart.domain.get_queryset().order_by(
        "category_id", "name", "id"
    )

    def get_queryset(self):
        queryset = self.queryset
        category_id_raw = self.request.query_params.get("category")
        if not category_id_raw:
            return queryset
        try:
            category_id = int(category_id_raw)
        except (TypeError, ValueError):
            return queryset.none()
        if category_id < 1:
            return queryset.none()
        return queryset.filter(category_id=category_id)


@extend_schema(
    tags=["Inventory"],
    summary="Get all inventory item categories",
    description=(
        "Returns full non-paginated list of active inventory item categories. "
        "Useful for frontend dropdowns and selectors."
    ),
)
class InventoryItemCategoryAllAPIView(BaseAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = InventoryItemCategorySerializer

    def get(self, request, *args, **kwargs):
        queryset = InventoryItemCategory.domain.get_queryset().order_by("name", "id")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
