from datetime import datetime
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet, SeoModel
from apps.core.slugs import unique_slug


def _not_over(today) -> Q:
    """Ещё не закончилось: начинается сегодня или позже либо идёт сейчас (многодневное)."""
    return Q(date__gte=today) | Q(end_date__gte=today)


class EventQuerySet(models.QuerySet):
    def upcoming(self, today=None):
        """Предстоящие и идущие сейчас — по дате начала."""
        today = today or timezone.localdate()
        return self.filter(_not_over(today)).order_by("date", "id")

    def past(self, today=None):
        today = today or timezone.localdate()
        return self.exclude(_not_over(today))

    def past_visible(self, today=None):
        return self.past(today).filter(show_after_date=True).order_by("-date", "-id")

    def visible(self, today=None):
        """Мероприятия, которые видны на сайте: предстоящие и прошедшие с «Показывать после даты»."""
        today = today or timezone.localdate()
        return self.filter(_not_over(today) | Q(show_after_date=True))


def _days(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} дня"
    return f"{n} дней"


class Event(SeoModel):
    title = models.CharField("Заголовок", max_length=128)
    slug = models.SlugField(
        "Адрес страницы", max_length=255, unique=True, blank=True, help_text="Пусто — из заголовка и года."
    )
    date = models.DateField("Дата")
    end_date = models.DateField(
        "Дата окончания", null=True, blank=True, help_text="Только для многодневных: «с 18 ноября по 17 декабря»."
    )
    start_time = models.TimeField("Время начала", null=True, blank=True)
    price = models.CharField(
        "Стоимость", max_length=100, blank=True, help_text="Коротко: «1000 ₽ с участника», «Бесплатно»."
    )
    description = HtmlField("Описание")
    link = models.URLField("Ссылка", max_length=500, blank=True, help_text="Соцсеть или сайт мероприятия.")
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

    def clean(self):
        if self.end_date and self.date and self.end_date < self.date:
            raise ValidationError({"end_date": "Дата окончания раньше даты начала."})
        if self.end_date == self.date:
            self.end_date = None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f"{self.title} {self.date:%Y}")
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:event", args=[self.slug])

    @property
    def last_date(self):
        return self.end_date or self.date

    @property
    def starts_at(self) -> datetime | None:
        """Начало с часовым поясом сайта; без времени — None."""
        if self.start_time is None:
            return None
        return datetime.combine(self.date, self.start_time, tzinfo=timezone.get_current_timezone())

    @property
    def is_past(self) -> bool:
        return self.last_date < timezone.localdate()

    @property
    def period(self) -> str:
        """«3 декабря 2022», «18–25 ноября 2027», «18 ноября — 17 декабря 2027», «28 декабря 2026 — 5 января 2027»."""
        start, end = self.date, self.last_date
        if start == end:
            return date_format(start, "j E Y")
        if start.year != end.year:
            return f"{date_format(start, 'j E Y')} — {date_format(end, 'j E Y')}"
        if start.month != end.month:
            return f"{date_format(start, 'j E')} — {date_format(end, 'j E Y')}"
        return f"{start.day}–{date_format(end, 'j E Y')}"

    @property
    def timing(self) -> str:
        """Метка относительно сегодня: «Сегодня», «Через 5 дней», «Идёт сейчас», «Прошло»; дальше месяца — пусто."""
        today = timezone.localdate()
        if self.last_date < today:
            return "Прошло"
        if self.date < today or (self.date == today and self.end_date):
            return "Идёт сейчас"
        days = (self.date - today).days
        if days == 0:
            return "Сегодня"
        if days == 1:
            return "Завтра"
        return f"Через {_days(days)}" if days <= 30 else ""


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
