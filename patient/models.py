import uuid

from django.db import models


class Patient(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Мужской"
        FEMALE = "F", "Женский"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField("Имя", max_length=100)
    last_name = models.CharField("Фамилия", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    iin = models.CharField(
        "ИИН", max_length=12, blank=True, unique=True, null=True,
        help_text="Индивидуальный идентификационный номер",
    )
    birth_date = models.DateField("Дата рождения", blank=True, null=True)
    gender = models.CharField("Пол", max_length=1, choices=Gender.choices, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("Почта", blank=True)
    address = models.TextField("Адрес", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "Пациент"
        verbose_name_plural = "Пациенты"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        parts = [self.last_name, self.first_name]
        if self.patronymic:
            parts.append(self.patronymic)
        return " ".join(parts)
