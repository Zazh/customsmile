import uuid

from django.conf import settings
from django.db import models


class Staff(models.Model):
    class Role(models.TextChoices):
        DOCTOR = "doctor", "Врач"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
    )
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.DOCTOR)
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    specialization = models.CharField("Специализация", max_length=255, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"
