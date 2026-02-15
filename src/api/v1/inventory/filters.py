from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from core.utils.constants import InventoryItemStatus
from inventory.models import InventoryItem
from inventory.services import InventoryItemService

ORDERING_CHOICES = (
    ("created_at", "created_at"),
    ("-created_at", "-created_at"),
    ("updated_at", "updated_at"),
    ("-updated_at", "-updated_at"),
    ("serial_number", "serial_number"),
    ("-serial_number", "-serial_number"),
    ("status", "status"),
    ("-status", "-status"),
)


class InventoryItemFilterSet(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    serial_number = filters.CharFilter(method="filter_serial_number")
    inventory = filters.NumberFilter(field_name="inventory_id")
    category = filters.NumberFilter(field_name="category_id")
    status = filters.ChoiceFilter(
        field_name="status", choices=InventoryItemStatus.choices
    )
    is_active = filters.BooleanFilter(field_name="is_active")
    has_active_ticket = filters.BooleanFilter(method="filter_has_active_ticket")
    created_from = filters.DateFilter(field_name="created_at__date", lookup_expr="gte")
    created_to = filters.DateFilter(field_name="created_at__date", lookup_expr="lte")
    updated_from = filters.DateFilter(field_name="updated_at__date", lookup_expr="gte")
    updated_to = filters.DateFilter(field_name="updated_at__date", lookup_expr="lte")
    ordering = filters.ChoiceFilter(method="filter_ordering", choices=ORDERING_CHOICES)

    class Meta:
        model = InventoryItem
        fields = (
            "q",
            "serial_number",
            "inventory",
            "category",
            "status",
            "is_active",
            "has_active_ticket",
            "created_from",
            "created_to",
            "updated_from",
            "updated_to",
            "ordering",
        )

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        created_from = self.form.cleaned_data.get("created_from")
        created_to = self.form.cleaned_data.get("created_to")
        if created_from and created_to and created_from > created_to:
            raise ValidationError(
                {
                    "created_to": "created_to must be greater than or equal to created_from."
                }
            )

        updated_from = self.form.cleaned_data.get("updated_from")
        updated_to = self.form.cleaned_data.get("updated_to")
        if updated_from and updated_to and updated_from > updated_to:
            raise ValidationError(
                {
                    "updated_to": "updated_to must be greater than or equal to updated_from."
                }
            )
        return queryset

    def filter_q(self, queryset, name, value):
        query = InventoryItemService.normalize_serial_number(value)
        if len(query) < InventoryItemService.SUGGESTION_MIN_CHARS:
            raise ValidationError({"q": "q must contain at least 2 characters."})

        suggestions = InventoryItemService.suggest_serial_numbers(
            query,
            limit=InventoryItemService.LIST_SEARCH_SUGGESTION_LIMIT,
        )
        return queryset.filter(
            Q(serial_number__icontains=query) | Q(serial_number__in=suggestions)
        )

    def filter_serial_number(self, queryset, name, value):
        normalized_serial_number = InventoryItemService.normalize_serial_number(value)
        return queryset.by_serial_number(normalized_serial_number)

    @staticmethod
    def filter_has_active_ticket(queryset, name, value):
        if value:
            return queryset.with_active_ticket()
        return queryset.without_active_ticket()

    @staticmethod
    def filter_ordering(queryset, name, value):
        return queryset.order_by(value, "id")
