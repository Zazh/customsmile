from django.contrib import admin, messages
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import StlAnnotation, StlFile, StlScan
from .tasks import extract_stl_files_task


class StlFileInline(admin.TabularInline):
    model = StlFile
    extra = 0
    readonly_fields = ["name", "file", "category"]
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


class StlAnnotationInline(admin.TabularInline):
    model = StlAnnotation
    extra = 0
    readonly_fields = ["x", "y", "z", "text", "created_by", "created_at"]
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StlScan)
class StlScanAdmin(admin.ModelAdmin):
    list_display = ["patient", "description", "file_count", "uploaded_at", "viewer_link"]
    list_filter = ["uploaded_at"]
    search_fields = ["patient__last_name", "patient__first_name", "description"]
    readonly_fields = ["uploaded_at"]
    inlines = [StlFileInline, StlAnnotationInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_file_count=Count("files"))

    def file_count(self, obj):
        return obj._file_count
    file_count.short_description = "Файлов"
    file_count.admin_order_field = "_file_count"

    def viewer_link(self, obj):
        if obj._file_count > 0:
            url = reverse("stl:viewer", kwargs={"scan_pk": obj.pk})
            return format_html('<a href="{}" target="_blank">Просмотр 3D</a>', url)
        return "Обработка..."
    viewer_link.short_description = "Просмотр"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and obj.archive:
            schema_name = request.tenant.schema_name
            extract_stl_files_task.delay(str(obj.pk), schema_name)
            messages.info(request, "Архив сохранён. Распаковка STL идёт в фоне.")
