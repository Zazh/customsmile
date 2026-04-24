from django.contrib import admin

from .models import Staff

TENANT_ALLOWED_ROLES = [
    (Staff.Role.DOCTOR, Staff.Role.DOCTOR.label),
    (Staff.Role.MANAGER, Staff.Role.MANAGER.label),
]


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["last_name", "first_name", "phone"]

    def _is_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        return tenant and tenant.schema_name != "public"

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role" and self._is_tenant(request):
            kwargs["choices"] = TENANT_ALLOWED_ROLES
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._is_tenant(request):
            qs = qs.exclude(role=Staff.Role.ADMIN)
        return qs

    def save_model(self, request, obj, form, change):
        if self._is_tenant(request) and obj.role == Staff.Role.ADMIN:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Тенант не может назначать роль Администратор.")
        super().save_model(request, obj, form, change)
