from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from rules.models import RulesConfigAction, RulesConfigVersion

ORDERING_CHOICES = (
    ("version", "version"),
    ("-version", "-version"),
    ("created_at", "created_at"),
    ("-created_at", "-created_at"),
)


class RulesConfigHistoryFilterSet(filters.FilterSet):
    version = filters.NumberFilter(method="filter_version")
    action = filters.ChoiceFilter(
        field_name="action", choices=RulesConfigAction.choices
    )
    created_by_id = filters.NumberFilter(method="filter_created_by_id")
    source_version = filters.NumberFilter(method="filter_source_version")
    ordering = filters.ChoiceFilter(method="filter_ordering", choices=ORDERING_CHOICES)

    class Meta:
        model = RulesConfigVersion
        fields = ("version", "action", "created_by_id", "source_version", "ordering")

    def filter_version(self, queryset, name, value):
        version = self._validate_positive_int(value=value, field_name=name)
        return queryset.filter(version=version)

    def filter_created_by_id(self, queryset, name, value):
        created_by_id = self._validate_positive_int(value=value, field_name=name)
        return queryset.filter(created_by_id=created_by_id)

    def filter_source_version(self, queryset, name, value):
        source_version = self._validate_positive_int(value=value, field_name=name)
        return queryset.filter(source_version__version=source_version)

    @staticmethod
    def filter_ordering(queryset, name, value):
        return queryset.order_by(value, "-id")

    @staticmethod
    def _validate_positive_int(*, value, field_name: str) -> int:
        int_value = int(value)
        if int_value < 1:
            raise ValidationError({field_name: f"{field_name} must be greater than 0."})
        return int_value
