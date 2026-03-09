from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import DicomStudy
from .services import upload_to_orthanc


@admin.register(DicomStudy)
class DicomStudyAdmin(admin.ModelAdmin):
    list_display = ["patient_name", "description", "uploaded_at", "viewer_link"]
    readonly_fields = ["orthanc_study_id", "uploaded_at", "viewer_link"]

    def viewer_link(self, obj):
        if obj.orthanc_study_id:
            url = reverse("dicom:viewer", kwargs={"study_pk": obj.pk})
            return format_html('<a href="{}" target="_blank">Открыть снимок</a>', url)
        return "Нет данных в Orthanc"

    viewer_link.short_description = "Просмотр"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.file and not obj.orthanc_study_id:
            study_id = upload_to_orthanc(obj.file.path)
            if study_id:
                obj.orthanc_study_id = study_id
                obj.save(update_fields=["orthanc_study_id"])
                messages.success(request, "DICOM загружен в Orthanc.")
            else:
                messages.error(request, "Ошибка загрузки в Orthanc. Проверьте формат файла.")
