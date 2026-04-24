import uuid

from django.db import models
from django.utils import timezone


class Stage(models.Model):
    """Справочник этапов лечения."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Название", max_length=255, unique=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Этап (справочник)"
        verbose_name_plural = "Этапы (справочник)"
        ordering = ["order"]

    def __str__(self):
        return self.name


class Treatment(models.Model):
    """Тонкая связка: пациент + врач + этап."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "patient.Patient",
        on_delete=models.PROTECT,
        related_name="treatments",
        verbose_name="Пациент",
    )
    doctor = models.ForeignKey(
        "staff.Staff",
        on_delete=models.SET_NULL,
        null=True,
        related_name="treatments",
        verbose_name="Врач",
    )
    stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        related_name="treatments",
        verbose_name="Этап",
    )
    started_at = models.DateTimeField("Дата начала", default=timezone.now, editable=False)
    completed_at = models.DateTimeField("Дата завершения", null=True, blank=True, editable=False)
    notes = models.TextField("Заметки", blank=True)

    class Meta:
        verbose_name = "Лечение"
        verbose_name_plural = "Лечения"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.patient} — {self.stage}"

    def complete(self):
        """Завершить текущий этап."""
        self.completed_at = timezone.now()
        self.save(update_fields=["completed_at"])
