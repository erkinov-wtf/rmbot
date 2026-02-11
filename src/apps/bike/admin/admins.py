from django.contrib import admin

from bike.models import Bike
from core.admin import BaseModelAdmin


@admin.register(Bike)
class BikeAdmin(BaseModelAdmin):
    list_display = ("id", "bike_code", "status", "is_active", "created_at")
    search_fields = ("bike_code",)
    list_filter = ("status", "is_active")
