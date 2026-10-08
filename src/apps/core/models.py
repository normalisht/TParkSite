from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.fields import HtmlField
from apps.core.maps import MapEmbedURLField
from apps.core.slugs import unique_slug


class OrderedModel(models.Model):
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class SiteSettings(models.Model):
    address = models.CharField("Адрес", max_length=255, blank=True)
    map_embed_url = MapEmbedURLField(
        "Яндекс Карта на странице контактов",
        max_length=1000,
        blank=True,
        help_text="В Яндекс Картах: «Поделиться» → «Встроить карту» → скопируйте код и вставьте сюда целиком.",
    )
    vk_url = models.URLField("VK", max_length=500, blank=True)
    reviews_url = models.URLField(
        "Отзывы на Яндекс Картах",
        max_length=500,
        blank=True,
        help_text="Страница отзывов о Т-Парке: кнопки «Все отзывы» и «Оставить отзыв» на странице отзывов.",
    )
    home_intro = HtmlField("Вступление на главной")
    events_intro = HtmlField("Вступление на странице мероприятий")
    about_text = HtmlField("О нас")
    philosophy_text = HtmlField("Философия")
    nearby_text = HtmlField("Что рядом")
    contacts_text = HtmlField("Текст на странице контактов")

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> SiteSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Phone(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="phones")
    number = models.CharField(
        "Номер",
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", "10 цифр без +7 и 8, например 9029856594.")],
    )
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)
    is_whatsapp = models.BooleanField("WhatsApp", default=False)
    is_telegram = models.BooleanField("Telegram", default=False)

    class Meta:
        verbose_name = "Телефон"
        verbose_name_plural = "Телефоны"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["settings"], condition=Q(is_whatsapp=True), name="one_whatsapp_phone"),
            models.UniqueConstraint(fields=["settings"], condition=Q(is_telegram=True), name="one_telegram_phone"),
        ]

    def __str__(self):
        return self.display

    @property
    def tel_url(self) -> str:
        return f"tel:+7{self.number}"

    @property
    def whatsapp_url(self) -> str:
        return f"https://wa.me/7{self.number}"

    @property
    def telegram_url(self) -> str:
        return f"https://t.me/+7{self.number}"

    @property
    def display(self) -> str:
        n = self.number
        return f"+7 ({n[:3]}) {n[3:6]}-{n[6:8]}-{n[8:]}" if len(n) == 10 else n


class InfoPage(models.Model):
    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    body = HtmlField("Текст")
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Инфо-страница"
        verbose_name_plural = "Инфо-страницы"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("core:info", args=[self.slug])
