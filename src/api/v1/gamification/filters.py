from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.utils.constants import RoleSlug, XPTransactionEntryType
from gamification.models import XPTransaction

PRIVILEGED_TRANSACTION_VIEW_ROLES = {RoleSlug.SUPER_ADMIN, RoleSlug.OPS_MANAGER}
ORDERING_CHOICES = (
    ("created_at", "created_at"),
    ("-created_at", "-created_at"),
    ("amount", "amount"),
    ("-amount", "-amount"),
)


def can_view_all_transaction_entries(user) -> bool:
    role_slugs = set(user.roles.values_list("slug", flat=True))
    return bool(role_slugs & PRIVILEGED_TRANSACTION_VIEW_ROLES)


class XPTransactionFilterSet(filters.FilterSet):
    user_id = filters.NumberFilter(method="filter_user_id")
    ticket_id = filters.NumberFilter(method="filter_ticket_id")
    entry_type = filters.ChoiceFilter(
        field_name="entry_type", choices=XPTransactionEntryType.choices
    )
    reference = filters.CharFilter(field_name="reference", lookup_expr="icontains")
    created_from = filters.DateFilter(field_name="created_at__date", lookup_expr="gte")
    created_to = filters.DateFilter(field_name="created_at__date", lookup_expr="lte")
    amount_min = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = filters.NumberFilter(field_name="amount", lookup_expr="lte")
    ordering = filters.ChoiceFilter(method="filter_ordering", choices=ORDERING_CHOICES)

    class Meta:
        model = XPTransaction
        fields = (
            "user_id",
            "ticket_id",
            "entry_type",
            "reference",
            "created_from",
            "created_to",
            "amount_min",
            "amount_max",
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

        amount_min = self.form.cleaned_data.get("amount_min")
        amount_max = self.form.cleaned_data.get("amount_max")
        if (
            amount_min is not None
            and amount_max is not None
            and amount_min > amount_max
        ):
            raise ValidationError(
                {
                    "amount_max": "amount_max must be greater than or equal to amount_min."
                }
            )

        return queryset

    def filter_user_id(self, queryset, name, value):
        user_id = self._validate_positive_int(value=value, field_name=name)
        request = self.request
        if request is None:
            return queryset.filter(user_id=user_id)

        if can_view_all_transaction_entries(request.user):
            return queryset.filter(user_id=user_id)

        if user_id != request.user.id:
            raise PermissionDenied("You can only view your own XP transaction entries.")

        return queryset.filter(user_id=request.user.id)

    def filter_ticket_id(self, queryset, name, value):
        ticket_id = self._validate_positive_int(value=value, field_name=name)
        return queryset.filter(
            Q(payload__ticket_id=ticket_id)
            | Q(reference=f"ticket_base_xp:{ticket_id}")
            | Q(reference=f"ticket_qc_first_pass_bonus:{ticket_id}")
            | Q(reference__startswith=f"ticket_qc_status_update:{ticket_id}:")
        )

    def filter_ordering(self, queryset, name, value):
        return queryset.order_by(value, "-id")

    @staticmethod
    def _validate_positive_int(value, field_name: str) -> int:
        int_value = int(value)
        if int_value < 1:
            raise ValidationError({field_name: f"{field_name} must be greater than 0."})
        return int_value
