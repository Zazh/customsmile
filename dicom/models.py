import uuid

from django.db import models


class DicomStudy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient_name = models.CharField("Имя пациента", max_length=255)
    description = models.CharField("Описание исследования", max_length=255, blank=True)
    file = models.FileField("DICOM файл (.dcm / .zip)", upload_to="dicom/%Y/%m/%d/")
    orthanc_study_id = models.CharField(max_length=255, blank=True, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DICOM исследование"
        verbose_name_plural = "DICOM исследования"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.patient_name} — {self.description or 'без описания'}"
