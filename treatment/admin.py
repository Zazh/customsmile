from django.contrib import admin

from staff.models import Staff

from .models import Stage, Treatment


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    ordering = ["order"]


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ["patient", "doctor", "stage", "started_at", "completed_at"]
    list_filter = ["stage", "doctor"]
    search_fields = ["patient__last_name", "patient__first_name"]
    readonly_fields = ["started_at", "completed_at"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "doctor":
            kwargs["queryset"] = Staff.objects.filter(role=Staff.Role.DOCTOR, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
