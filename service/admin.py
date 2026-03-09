from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "stage", "code", "order", "is_active"]
    list_filter = ["stage", "is_active"]
    search_fields = ["name", "code"]
