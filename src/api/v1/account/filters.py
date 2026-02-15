from django_filters import rest_framework as filters

from account.models import AccessRequest
from core.utils.constants import AccessRequestStatus

ORDERING_CHOICES = (
    ("created_at", "created_at"),
    ("-created_at", "-created_at"),
    ("resolved_at", "resolved_at"),
    ("-resolved_at", "-resolved_at"),
)


class AccessRequestFilterSet(filters.FilterSet):
    status = filters.ChoiceFilter(
        field_name="status", choices=AccessRequestStatus.choices
    )
    ordering = filters.ChoiceFilter(method="filter_ordering", choices=ORDERING_CHOICES)

    class Meta:
        model = AccessRequest
        fields = ("status", "ordering")

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if self.form.cleaned_data.get("status") is None:
            queryset = queryset.filter(status=AccessRequestStatus.PENDING)
        return queryset

    @staticmethod
    def filter_ordering(queryset, name, value):
        return queryset.order_by(value, "-id")
