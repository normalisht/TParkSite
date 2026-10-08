from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet


class EventQuerySet(models.QuerySet):
    def upcoming(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__gte=today).order_by("date", "id")

    def past_visible(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__lt=today, show_after_date=True).order_by("-date", "-id")


class Event(models.Model):
    title = models.CharField("Заголовок", max_length=128)
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


class Review(OrderedModel):
    author = models.CharField("Имя", max_length=128)
    text = HtmlField("Текст")
    photo = photo_field("Фото", "reviews")
    avatar = image_spec("photo", 160, 160)
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return self.author or f"Отзыв #{self.pk}"


class Partner(OrderedModel):
    name = models.CharField("Название", max_length=128, blank=True)
    link = models.URLField("Ссылка", max_length=500, blank=True)
    logo = photo_field("Логотип", "partners", size=(600, 300), fmt=None)
    logo_small = image_spec("logo", 300, 150, crop=False)

    class Meta(OrderedModel.Meta):
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"

    def __str__(self):
        return self.name or f"Партнёр #{self.pk}"


class Employee(OrderedModel):
    name = models.CharField("Имя", max_length=128)
    position = models.CharField("Должность", max_length=128, blank=True)
    photo = photo_field("Фото", "employees")
    portrait = image_spec("photo", 400, 500)

    class Meta(OrderedModel.Meta):
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return self.name


class GalleryPhoto(OrderedModel):
    image = photo_field("Фото", "gallery", blank=False)
    caption = models.CharField("Подпись", max_length=255, blank=True)
    thumb = image_spec("image", 600, 600)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото галереи"
        verbose_name_plural = "Галерея"

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"
