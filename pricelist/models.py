import uuid

from django.db import models


class PriceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "service.Service",
        on_delete=models.CASCADE,
        related_name="price_items",
        verbose_name="Услуга",
    )
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Цена услуги"
        verbose_name_plural = "Прайс-лист"
        ordering = ["service__stage__order", "service__order"]

    def __str__(self):
        return f"{self.service} — {self.price} ₸"
