from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Company, Domain


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


@admin.register(Company)
class CompanyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "schema_name", "phone", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "phone", "email"]
    inlines = [DomainInline]
