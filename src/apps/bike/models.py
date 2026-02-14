from django.db import models

from bike.managers import BikeDomainManager
from core.models import SoftDeleteModel, TimestampedModel
from core.utils.constants import BikeStatus


class Bike(TimestampedModel, SoftDeleteModel):
    domain = BikeDomainManager()

    bike_code = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=BikeStatus,
        default=BikeStatus.READY,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "is_active"]),
        ]

    def mark_in_service(self) -> None:
        if self.status == BikeStatus.IN_SERVICE:
            return
        self.status = BikeStatus.IN_SERVICE
        self.save(update_fields=["status"])

    def mark_ready(self) -> None:
        if self.status == BikeStatus.READY:
            return
        self.status = BikeStatus.READY
        self.save(update_fields=["status"])

    def __str__(self) -> str:
        return f"{self.bike_code} ({self.status})"
