import os
import shutil
from datetime import date

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import ChunkedUpload, DicomStudy
from .tasks import send_to_orthanc
from .widgets import ChunkedUploadWidget


class DicomStudyForm(forms.ModelForm):
    chunked_file = forms.CharField(
        label="DICOM файл (.dcm / .zip)",
        widget=ChunkedUploadWidget,
        required=False,
    )

    class Meta:
        model = DicomStudy
        fields = ["patient", "description"]

    def clean_chunked_file(self):
        upload_id = self.data.get("chunked_upload_id", "").strip()
        if not upload_id and not self.instance.pk:
            raise forms.ValidationError("Загрузите DICOM файл.")
        if upload_id:
            try:
                upload = ChunkedUpload.objects.get(
                    pk=upload_id, status=ChunkedUpload.Status.COMPLETE,
                )
            except ChunkedUpload.DoesNotExist:
                raise forms.ValidationError("Загрузка не найдена или не завершена.")
            return upload
        return None


@admin.register(DicomStudy)
class DicomStudyAdmin(admin.ModelAdmin):
    form = DicomStudyForm
    list_display = ["patient", "description", "uploaded_at", "viewer_link"]
    readonly_fields = ["orthanc_study_id", "uploaded_at", "viewer_link"]

    def viewer_link(self, obj):
        if obj.orthanc_study_id:
            url = reverse("dicom:viewer", kwargs={"study_pk": obj.pk})
            return format_html('<a href="{}" target="_blank">Открыть снимок</a>', url)
        return "Нет данных в Orthanc"

    viewer_link.short_description = "Просмотр"

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("chunked_file")
        if upload and isinstance(upload, ChunkedUpload):
            # Move temp file to media/dicom/YYYY/MM/DD/
            today = date.today()
            rel_dir = os.path.join("dicom", today.strftime("%Y"), today.strftime("%m"), today.strftime("%d"))
            dest_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
            os.makedirs(dest_dir, exist_ok=True)

            dest_path = os.path.join(dest_dir, upload.filename)
            shutil.move(upload.temp_path, dest_path)

            obj.file.name = os.path.join(rel_dir, upload.filename)
            upload.delete()

        super().save_model(request, obj, form, change)

        if obj.file and not obj.orthanc_study_id:
            schema_name = request.tenant.schema_name
            send_to_orthanc.delay(str(obj.pk), obj.file.path, schema_name)
            messages.info(request, "Файл сохранён. Отправка в Orthanc идёт в фоне.")
