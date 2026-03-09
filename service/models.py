import uuid

from django.db import models


class Service(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(
        "treatment.Stage",
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Этап",
    )
    name = models.CharField("Название", max_length=255)
    code = models.CharField("Код услуги", max_length=50, blank=True, unique=True, null=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["stage__order", "order"]

    def __str__(self):
        return self.name
