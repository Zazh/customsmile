from django.contrib import admin

from .models import PriceItem


@admin.register(PriceItem)
class PriceItemAdmin(admin.ModelAdmin):
    list_display = ["service", "price"]
    list_filter = ["service__stage"]
    search_fields = ["service__name"]
