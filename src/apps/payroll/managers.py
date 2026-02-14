from __future__ import annotations

from django.db import models


class PayrollMonthlyQuerySet(models.QuerySet):
    def with_related(self):
        return (
            self.select_related("closed_by", "approved_by")
            .prefetch_related("lines__user")
            .prefetch_related("allowance_gate_decisions__decided_by")
        )

    def for_month(self, *, month_start):
        return self.filter(month=month_start)


class PayrollMonthlyDomainManager(models.Manager.from_queryset(PayrollMonthlyQuerySet)):
    def get_for_month(self, *, month_start):
        return (
            self.get_queryset()
            .with_related()
            .for_month(month_start=month_start)
            .first()
        )

    def get_for_month_for_update(self, *, month_start):
        return (
            self.get_queryset()
            .select_for_update()
            .for_month(month_start=month_start)
            .first()
        )

    def get_or_create_for_month_for_update(self, *, month_start):
        return self.get_queryset().select_for_update().get_or_create(month=month_start)
