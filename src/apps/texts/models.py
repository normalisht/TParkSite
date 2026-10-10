from django.db import models
from simple_history.models import HistoricalRecords

from apps.texts.registry import Page


class SiteText(models.Model):
    """Текущее значение текста сайта; набор ключей, подписи и тексты по умолчанию — в `registry.py`."""

    key = models.CharField("Ключ", max_length=64, unique=True)
    page = models.CharField("Страница", max_length=16, choices=Page.choices)
    label = models.CharField("Название", max_length=128)
    text = models.TextField("Текст", blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    updated_at = models.DateTimeField("Изменён", auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "текст сайта"
        verbose_name_plural = "тексты сайта"
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.get_page_display()}: {self.label}"
