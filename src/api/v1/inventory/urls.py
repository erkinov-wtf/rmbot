from django.urls import path

from api.v1.inventory.views import (
    InventoryExportAPIView,
    InventoryImportAPIView,
    InventoryItemCategoryAllAPIView,
    InventoryItemCategoryViewSet,
    InventoryItemPartViewSet,
    InventoryItemViewSet,
    InventoryViewSet,
)

app_name = "inventory"

inventory_item_list = InventoryItemViewSet.as_view({"get": "list", "post": "create"})
inventory_item_detail = InventoryItemViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)
inventory_list = InventoryViewSet.as_view({"get": "list", "post": "create"})
inventory_detail = InventoryViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)
category_list = InventoryItemCategoryViewSet.as_view({"get": "list", "post": "create"})
category_detail = InventoryItemCategoryViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)
part_list = InventoryItemPartViewSet.as_view({"get": "list", "post": "create"})
part_detail = InventoryItemPartViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("", inventory_list, name="inventory-list"),
    path("<int:pk>/", inventory_detail, name="inventory-detail"),
    path("export/", InventoryExportAPIView.as_view(), name="inventory-export"),
    path("import/", InventoryImportAPIView.as_view(), name="inventory-import"),
    path("items/", inventory_item_list, name="inventory-item-list"),
    path("items/<int:pk>/", inventory_item_detail, name="inventory-item-detail"),
    path(
        "categories/all/",
        InventoryItemCategoryAllAPIView.as_view(),
        name="inventory-item-category-all",
    ),
    path("categories/", category_list, name="inventory-item-category-list"),
    path(
        "categories/<int:pk>/",
        category_detail,
        name="inventory-item-category-detail",
    ),
    path("parts/", part_list, name="inventory-item-part-list"),
    path("parts/<int:pk>/", part_detail, name="inventory-item-part-detail"),
]
