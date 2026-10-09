from urllib.parse import urlsplit

from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet
from apps.core.slugs import unique_slug


class EventQuerySet(models.QuerySet):
    def upcoming(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__gte=today).order_by("date", "id")

    def past_visible(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__lt=today, show_after_date=True).order_by("-date", "-id")

    def visible(self, today=None):
        """Мероприятия, которые видны на сайте: предстоящие и прошедшие с «Показывать после даты»."""
        today = today or timezone.localdate()
        return self.filter(Q(date__gte=today) | Q(show_after_date=True))


class Event(models.Model):
    title = models.CharField("Заголовок", max_length=128)
    slug = models.SlugField(
        "Адрес страницы", max_length=255, unique=True, blank=True, help_text="Пусто — из заголовка и года."
    )
    date = models.DateField("Дата")
    description = HtmlField("Описание")
    link = models.URLField("Ссылка", max_length=500, blank=True, help_text="Соцсеть или сайт мероприятия.")
    text_color = models.CharField(
        "Цвет текста на фото",
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Цвет в формате #RRGGBB.")],
        help_text="Необязательно. По умолчанию белый.",
    )
    show_after_date = models.BooleanField("Показывать после даты", default=False)
    image = photo_field("Фото", "events")
    card = image_spec("image", 800, 600)

    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.title} ({self.date:%d.%m.%Y})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.title} {self.date:%Y}")
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:event", args=[self.slug])


REVIEW_SOURCES = {"yandex.": "Яндекс Карты", "vk.com": "VK", "2gis.": "2ГИС", "google.": "Google"}


class Review(models.Model):
    text = HtmlField("Текст")
    link = models.URLField(
        "Ссылка на отзыв",
        max_length=500,
        blank=True,
        help_text="Например, на отзыв в Яндекс Картах: открывается по клику на подпись источника под отзывом.",
    )
    date = models.DateField("Дата отзыва", null=True, blank=True)
    photo = photo_field("Фото", "reviews")
    avatar = image_spec("photo", 160, 160)
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        # От новых к старым; без даты — в конце, среди них свежедобавленные первыми.
        ordering = [models.F("date").desc(nulls_last=True), "-id"]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        # Имени у отзыва нет (на сайте — «Гость Т-Парка»): в админке узнаём отзыв по началу текста.
        return Truncator(strip_tags(self.text)).chars(60) or f"Отзыв #{self.pk}"

    @property
    def source_label(self) -> str:
        """Откуда отзыв: «Яндекс Карты», «VK»… — по адресу ссылки; без ссылки — пусто."""
        host = (urlsplit(self.link).hostname or "").removeprefix("www.")
        return next((label for key, label in REVIEW_SOURCES.items() if key in host), host)


class Partner(OrderedModel):
    name = models.CharField("Название", max_length=128, blank=True)
    link = models.URLField("Ссылка", max_length=500, blank=True)
    logo = photo_field("Логотип", "partners", size=(800, 800), fmt=None)
    logo_small = image_spec("logo", 600, 600, crop=False)

    class Meta(OrderedModel.Meta):
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"

    def __str__(self):
        return self.name or f"Партнёр #{self.pk}"


class GalleryPhoto(OrderedModel):
    image = photo_field("Фото", "gallery", blank=False)
    caption = models.CharField("Подпись", max_length=255, blank=True)
    thumb = image_spec("image", 600, 600)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото галереи"
        verbose_name_plural = "Галерея"

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"
