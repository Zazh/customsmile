import uuid

from django.conf import settings
from django.db import models


class ChunkedUpload(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading", "Загружается"
        COMPLETE = "complete", "Завершён"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь",
    )
    filename = models.CharField("Имя файла", max_length=255)
    total_size = models.BigIntegerField("Размер файла (байт)")
    offset = models.BigIntegerField("Загружено (байт)", default=0)
    status = models.CharField(
        "Статус", max_length=20,
        choices=Status.choices, default=Status.UPLOADING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Загрузка чанками"
        verbose_name_plural = "Загрузки чанками"

    def __str__(self):
        return f"{self.filename} ({self.offset}/{self.total_size})"

    @property
    def temp_path(self):
        upload_dir = getattr(settings, "CHUNKED_UPLOAD_DIR", settings.MEDIA_ROOT / "chunked_tmp")
        return str(upload_dir / str(self.pk))

    @property
    def is_complete(self):
        return self.offset >= self.total_size


class DicomStudy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.PROTECT,
        related_name="dicom_studies",
        verbose_name="Пациент",
    )
    description = models.CharField("Описание исследования", max_length=255, blank=True)
    file = models.FileField("DICOM файл (.dcm / .zip)", upload_to="dicom/%Y/%m/%d/")
    orthanc_study_id = models.CharField(max_length=255, blank=True, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DICOM исследование"
        verbose_name_plural = "DICOM исследования"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.patient} — {self.description or 'без описания'}"
