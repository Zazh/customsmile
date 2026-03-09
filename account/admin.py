from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "phone", "first_name", "last_name", "is_active"]
    search_fields = ["username", "email", "phone", "first_name", "last_name"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Дополнительно", {"fields": ("phone",)}),
    )
