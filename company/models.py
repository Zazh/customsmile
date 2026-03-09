from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Company(TenantMixin):
    name = models.CharField("Название клиники", max_length=255)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("Почта", blank=True)
    address = models.TextField("Адрес", blank=True)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    auto_create_schema = True

    class Meta:
        verbose_name = "Клиника"
        verbose_name_plural = "Клиники"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    class Meta:
        verbose_name = "Домен"
        verbose_name_plural = "Домены"
