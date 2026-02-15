from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from bike.models import Bike
from bike.services import BikeService
from core.utils.constants import BikeStatus

ORDERING_CHOICES = (
    ("created_at", "created_at"),
    ("-created_at", "-created_at"),
    ("updated_at", "updated_at"),
    ("-updated_at", "-updated_at"),
    ("bike_code", "bike_code"),
    ("-bike_code", "-bike_code"),
    ("status", "status"),
    ("-status", "-status"),
)


class BikeFilterSet(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    bike_code = filters.CharFilter(method="filter_bike_code")
    status = filters.ChoiceFilter(field_name="status", choices=BikeStatus.choices)
    is_active = filters.BooleanFilter(field_name="is_active")
    has_active_ticket = filters.BooleanFilter(method="filter_has_active_ticket")
    created_from = filters.DateFilter(field_name="created_at__date", lookup_expr="gte")
    created_to = filters.DateFilter(field_name="created_at__date", lookup_expr="lte")
    updated_from = filters.DateFilter(field_name="updated_at__date", lookup_expr="gte")
    updated_to = filters.DateFilter(field_name="updated_at__date", lookup_expr="lte")
    ordering = filters.ChoiceFilter(method="filter_ordering", choices=ORDERING_CHOICES)

    class Meta:
        model = Bike
        fields = (
            "q",
            "bike_code",
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
        query = BikeService.normalize_bike_code(value)
        if len(query) < BikeService.SUGGESTION_MIN_CHARS:
            raise ValidationError({"q": "q must contain at least 2 characters."})

        suggestions = BikeService.suggest_codes(
            query,
            limit=BikeService.LIST_SEARCH_SUGGESTION_LIMIT,
        )
        return queryset.filter(
            Q(bike_code__icontains=query) | Q(bike_code__in=suggestions)
        )

    def filter_bike_code(self, queryset, name, value):
        normalized_bike_code = BikeService.normalize_bike_code(value)
        return queryset.by_code(normalized_bike_code)

    @staticmethod
    def filter_has_active_ticket(queryset, name, value):
        if value:
            return queryset.with_active_ticket()
        return queryset.without_active_ticket()

    @staticmethod
    def filter_ordering(queryset, name, value):
        return queryset.order_by(value, "id")
