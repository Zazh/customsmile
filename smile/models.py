import uuid

from django.conf import settings
from django.db import models


class SmilePhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.PROTECT,
        related_name="smile_photos",
        verbose_name="Пациент",
    )
    image = models.ImageField("Фото улыбки", upload_to="smile/photos/%Y/%m/%d/")
    description = models.CharField("Описание", max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Загрузил",
    )
    uploaded_at = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        verbose_name = "Фото улыбки"
        verbose_name_plural = "Фото улыбок"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.patient} — {self.description or 'Фото улыбки'}"


class SmileAnalysis(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        PROCESSING = "processing", "Обработка"
        DONE = "done", "Готово"
        FAILED = "failed", "Ошибка"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    photo = models.ForeignKey(
        SmilePhoto,
        on_delete=models.CASCADE,
        related_name="analyses",
        verbose_name="Фото",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error_message = models.TextField("Ошибка", blank=True)

    # Stage 1: MediaPipe landmarks (478 points)
    landmarks = models.JSONField(
        "Landmarks лица",
        default=dict,
        blank=True,
        help_text="Все 478 точек MediaPipe Face Mesh: {idx: {x, y, z}}",
    )

    # Stage 2: smile contour
    teeth_contour = models.JSONField(
        "Контур зубов",
        default=list,
        blank=True,
        help_text="Видимая зона зубов (нижний край верхней губы + верхний край нижней губы): [{x, y}, ...]",
    )
    lip_contour = models.JSONField(
        "Контур губ",
        default=list,
        blank=True,
        help_text="Внешний контур губ (справочный): [{x, y}, ...]",
    )
    contour_image = models.ImageField(
        "Фото с контуром",
        upload_to="smile/contours/%Y/%m/%d/",
        blank=True,
    )

    # Stage 3: guidelines
    guidelines = models.JSONField(
        "Направляющие",
        default=dict,
        blank=True,
        help_text='{"facial_midline": {...}, "smile_arc": [...], ...}',
    )
    guidelines_image = models.ImageField(
        "Фото с направляющими",
        upload_to="smile/guidelines/%Y/%m/%d/",
        blank=True,
    )

    # Stage 4: cutout
    cutout_image = models.ImageField(
        "Вырезка улыбки (прозрачный фон)",
        upload_to="smile/cutouts/%Y/%m/%d/",
        blank=True,
    )
    masked_image = models.ImageField(
        "Фото с прозрачной зоной улыбки",
        upload_to="smile/masked/%Y/%m/%d/",
        blank=True,
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Анализ улыбки"
        verbose_name_plural = "Анализы улыбок"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.photo.patient} — {self.get_status_display()}"
