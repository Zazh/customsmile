import uuid

from django.conf import settings
from django.db import models


class StlScan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.PROTECT,
        related_name="stl_scans",
        verbose_name="Пациент",
    )
    description = models.CharField("Описание", max_length=255, blank=True)
    archive = models.FileField("ZIP архив", upload_to="stl/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        verbose_name = "STL снимок"
        verbose_name_plural = "STL снимки"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.patient} — {self.description or 'STL снимок'}"


class StlFile(models.Model):
    class Category(models.TextChoices):
        UPPER = "upper", "Верхняя челюсть"
        LOWER = "lower", "Нижняя челюсть"
        BUCCAL = "buccal", "Буккальный"
        OTHER = "other", "Другое"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.ForeignKey(
        StlScan,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name="Снимок",
    )
    name = models.CharField("Имя файла", max_length=255)
    file = models.FileField("STL файл", upload_to="stl/files/%Y/%m/%d/")
    category = models.CharField(
        "Категория",
        max_length=10,
        choices=Category.choices,
        default=Category.OTHER,
    )

    class Meta:
        verbose_name = "STL файл"
        verbose_name_plural = "STL файлы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StlAnnotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scan = models.ForeignKey(
        StlScan,
        on_delete=models.CASCADE,
        related_name="annotations",
        verbose_name="Снимок",
    )
    x = models.FloatField()
    y = models.FloatField()
    z = models.FloatField()
    text = models.TextField("Заметка")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Автор",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Аннотация"
        verbose_name_plural = "Аннотации"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.text[:50]}"


class StlSegmentation(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Ручная"
        AUTO = "auto", "Автоматическая"
        CORRECTED = "corrected", "Скорректированная"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stl_file = models.ForeignKey(
        StlFile,
        on_delete=models.CASCADE,
        related_name="segmentations",
        verbose_name="STL файл",
    )
    source = models.CharField(
        "Источник",
        max_length=10,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    labels = models.JSONField(
        "Метки сегментации",
        default=dict,
        help_text='{"tooth_11": [0, 1, 2, ...], "gingiva": [55, 56, ...]}',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Автор",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Сегментация"
        verbose_name_plural = "Сегментации"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.stl_file.name} — {self.get_source_display()}"
