from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["last_name", "first_name", "phone"]
