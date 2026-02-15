from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from account.models import User
from attendance.models import AttendanceRecord
from attendance.services import AttendanceService
from core.utils.constants import RoleSlug


class AttendanceRecordFilterSet(filters.FilterSet):
    work_date = filters.DateFilter(field_name="work_date")
    technician_id = filters.NumberFilter(method="filter_technician_id")
    punctuality = filters.ChoiceFilter(
        method="filter_punctuality",
        choices=(
            ("early", "Early"),
            ("on_time", "On time"),
            ("late", "Late"),
        ),
    )
    ordering = filters.ChoiceFilter(
        method="filter_ordering",
        choices=(
            ("user_id", "user_id"),
            ("-user_id", "-user_id"),
            ("check_in_at", "check_in_at"),
            ("-check_in_at", "-check_in_at"),
            ("created_at", "created_at"),
            ("-created_at", "-created_at"),
        ),
    )

    class Meta:
        model = AttendanceRecord
        fields = ("work_date", "technician_id", "punctuality", "ordering")

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if self.form.cleaned_data.get("work_date") is None:
            business_date = AttendanceService._business_date(timezone.now())
            queryset = queryset.filter(work_date=business_date)
        return queryset

    def filter_technician_id(self, queryset, name, value):
        technician_id = self._validate_positive_int(value=value, field_name=name)
        has_technician_role = User.objects.filter(
            pk=technician_id,
            is_active=True,
            roles__slug=RoleSlug.TECHNICIAN,
        ).exists()
        if not has_technician_role:
            raise ValidationError({"technician_id": "Technician user does not exist."})
        return queryset.filter(user_id=technician_id)

    def filter_punctuality(self, queryset, name, value):
        matching_ids = [
            record_id
            for record_id, check_in_at in queryset.values_list("id", "check_in_at")
            if AttendanceService.resolve_punctuality_status(check_in_at) == value
        ]
        if not matching_ids:
            return queryset.none()
        return queryset.filter(id__in=matching_ids)

    def filter_ordering(self, queryset, name, value):
        return queryset.order_by(value, "id")

    @staticmethod
    def _validate_positive_int(*, value, field_name: str) -> int:
        int_value = int(value)
        if int_value < 1:
            raise ValidationError({field_name: f"{field_name} must be greater than 0."})
        return int_value
