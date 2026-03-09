from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "patronymic", "iin", "phone"]
    list_filter = ["gender"]
    search_fields = ["last_name", "first_name", "iin", "phone"]
