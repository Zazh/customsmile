from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import SmileAnalysis, SmilePhoto
from .tasks import analyze_smile_task


class SmileAnalysisInline(admin.StackedInline):
    model = SmileAnalysis
    extra = 0
    readonly_fields = [
        "status", "error_message", "contour_image", "guidelines_image",
        "cutout_image", "masked_image", "created_at", "updated_at",
    ]
    exclude = ["landmarks", "teeth_contour", "lip_contour", "guidelines"]
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SmilePhoto)
class SmilePhotoAdmin(admin.ModelAdmin):
    list_display = ["patient", "description", "analysis_status", "uploaded_at", "editor_link"]
    list_filter = ["uploaded_at"]
    search_fields = ["patient__last_name", "patient__first_name", "description"]
    readonly_fields = ["uploaded_at", "uploaded_by"]
    inlines = [SmileAnalysisInline]

    def analysis_status(self, obj):
        analysis = obj.analyses.first()
        if not analysis:
            return "—"
        colors = {
            "pending": "#999",
            "processing": "#f0ad4e",
            "done": "#5cb85c",
            "failed": "#d9534f",
        }
        color = colors.get(analysis.status, "#999")
        return format_html(
            '<span style="color: {}">{}</span>',
            color,
            analysis.get_status_display(),
        )
    analysis_status.short_description = "Статус анализа"

    def editor_link(self, obj):
        analysis = obj.analyses.first()
        if analysis and analysis.status == "done":
            url = reverse("smile:editor", kwargs={"analysis_pk": analysis.pk})
            return format_html('<a href="{}" target="_blank">Редактор</a>', url)
        return "—"
    editor_link.short_description = "Редактор"

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

        if not change and obj.image:
            analysis = SmileAnalysis.objects.create(photo=obj)
            schema_name = request.tenant.schema_name
            analyze_smile_task.delay(str(analysis.pk), schema_name)
            messages.info(request, "Фото сохранено. Анализ улыбки запущен в фоне.")
