from datetime import datetime
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.content.dzen import DzenEmbedURLField, format_duration, validate_dzen_page_url
from apps.core.fields import HtmlField, full_spec, image_spec, image_specs, og_spec, photo_field
from apps.core.files import clone_file
from apps.core.indexnow import remember_page_change
from apps.core.models import COPY_SUFFIX, OrderedModel, PublishedQuerySet, SeoModel, TrashableModel
from apps.core.redirects import remember_slug_change
from apps.core.rotation import daily_pick
from apps.core.slugs import SLUG_HELP, unique_slug


def _not_over(today) -> Q:
    """Ещё не закончилось: начинается сегодня или позже либо идёт сейчас (многодневное)."""
    return Q(date__gte=today) | Q(end_date__gte=today)


class EventQuerySet(PublishedQuerySet):
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


class Event(TrashableModel, SeoModel):
    title = models.CharField("Заголовок", max_length=128)
    slug = models.SlugField(
        "Адрес страницы",
        max_length=255,
        unique=True,
        blank=True,
        help_text=(
            "Пусто — из заголовка и года. Если поменять, со старого адреса будет автоматический редирект "
            "(раздел «Редиректы»), но лучше не менять адрес страниц, которые уже в поиске."
        ),
    )
    date = models.DateField("Дата")
    end_date = models.DateField(
        "Дата окончания", null=True, blank=True, help_text="Только для многодневных: «с 18 ноября по 17 декабря»."
    )
    start_time = models.TimeField("Время начала", null=True, blank=True)
    venue = models.CharField("Место проведения", max_length=255, blank=True, help_text="Пусто — в Т-Парке.")
    price = models.CharField(
        "Стоимость", max_length=100, blank=True, help_text="Коротко: «1000 ₽ с участника», «Бесплатно»."
    )
    description = HtmlField("Описание")
    link = models.URLField("Ссылка", max_length=500, blank=True, help_text="Соцсеть или сайт мероприятия.")
    show_after_date = models.BooleanField(
        "Показывать после даты",
        default=False,
        help_text="Оставить в списке «Прошедшие» и в поиске. Без галочки прошедшее открывается только по прямой ссылке.",
    )
    is_published = models.BooleanField(
        "Опубликовано", default=True, help_text="Снимите, чтобы подготовить мероприятие заранее: на сайте его не будет."
    )
    image = photo_field("Фото", "events")
    card, card_avif = image_specs("image", 800, 600)
    card_small, card_small_avif = image_specs("image", 640, 480)  # карточки в сетке и на телефоне: srcset с card
    og = og_spec("image")

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

    def slug_source(self) -> str:
        return f"{self.title} {self.date:%Y}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.slug_source())
        with transaction.atomic():
            remember_slug_change(self)
            remember_page_change(self)
            super().save(*args, **kwargs)

    def duplicate(self) -> Event:
        """Черновик-копия для повторяющихся мероприятий: дату и описание администратор поправит."""
        return Event.objects.create(
            title=f"{self.title[:120]}{COPY_SUFFIX}",
            date=self.date,
            end_date=self.end_date,
            start_time=self.start_time,
            venue=self.venue,
            price=self.price,
            description=self.description,
            link=self.link,
            image=clone_file(self.image) or "",
            show_after_date=self.show_after_date,
            is_published=False,
        )

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


REVIEW_SOURCES = {"yandex.": "Яндекс Карты", "vk.com": "ВКонтакте", "2gis.": "2ГИС", "google.": "Google"}


class Review(TrashableModel):
    text = HtmlField("Текст")
    link = models.URLField(
        "Ссылка на отзыв",
        max_length=500,
        blank=True,
        help_text="Например, на отзыв в Яндекс Картах: открывается по клику на подпись источника под отзывом.",
    )
    date = models.DateField(
        "Дата отзыва",
        null=True,
        blank=True,
        help_text="От неё зависит порядок: новые сверху, без даты — в конце. «Подтянуть» заполнит её сама.",
    )
    photo = photo_field(
        "Фото",
        "reviews",
        help_text="Маленький кружок рядом с подписью «Гость Т-Парка», кадр обрезается до квадрата. Необязательно.",
    )
    avatar, avatar_avif = image_specs("photo", 160, 160)
    is_published = models.BooleanField("Опубликовано", default=True, help_text="Снимите, чтобы скрыть отзыв на сайте.")

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
        """Откуда отзыв: «Яндекс Карты», «ВКонтакте»… — по адресу ссылки; без ссылки — пусто."""
        host = (urlsplit(self.link).hostname or "").removeprefix("www.")
        return next((label for key, label in REVIEW_SOURCES.items() if key in host), host)


class Partner(OrderedModel):
    name = models.CharField(
        "Название",
        max_length=128,
        blank=True,
        help_text="Описание логотипа для поисковиков; без логотипа на сайте будет плитка с этим названием.",
    )
    link = models.URLField(
        "Ссылка", max_length=500, blank=True, help_text="Откроется в новой вкладке. Пусто — логотип без ссылки."
    )
    logo = photo_field(
        "Логотип",
        "partners",
        size=(800, 800),
        fmt=None,
        help_text="На «О нас» — целиком, без обрезки. Лучше PNG с прозрачным или белым фоном.",
    )
    logo_small = image_spec("logo", 600, 600, crop=False)

    class Meta(OrderedModel.Meta):
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"

    def __str__(self):
        return self.name or f"Партнёр #{self.pk}"


class GalleryPhoto(OrderedModel):
    STRIP_SIZE = 6  # фото в полосе «Как это выглядит» (главная, «О нас», отзывы)

    image = photo_field(
        "Фото", "gallery", blank=False, help_text="В галерее — квадратом с обрезкой краёв, по клику — целиком."
    )
    caption = models.CharField(
        "Подпись",
        max_length=255,
        blank=True,
        help_text="Видна при просмотре фото на весь экран и описывает фото для поисковиков.",
    )
    thumb, thumb_avif = image_specs("image", 600, 600)
    thumb_small, thumb_small_avif = image_specs("image", 400, 400)  # сетка на телефоне: srcset с thumb
    full = full_spec("image")

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото галереи"
        verbose_name_plural = "Галерея"

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"

    @classmethod
    def strip_photos(cls, key: str, size: int = STRIP_SIZE) -> list[GalleryPhoto]:
        """Фото для полосы «Как это выглядит»: на каждой странице (key) свои, меняются раз в сутки."""
        ids = daily_pick(list(cls.objects.values_list("pk", flat=True)), size, key)
        photos = cls.objects.in_bulk(ids)
        return [photos[pk] for pk in ids]


class Video(OrderedModel):
    embed_url = DzenEmbedURLField("Видео с Дзена", max_length=255, unique=True)
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    duration = models.PositiveIntegerField("Длительность, сек", null=True, blank=True)
    dzen_url = models.URLField(
        "Ролик на Дзене",
        max_length=255,
        blank=True,
        validators=[validate_dzen_page_url],
        help_text="Ссылка «Открыть на Дзене» под плеером в просмотре ролика. Пусто — при добавлении или смене ролика "
        "сайт возьмёт адрес с Дзена вместе с названием; без адреса ссылки нет.",
    )
    # Пустой в БД бывает только до сохранения формы: форма админки гарантирует обложку.
    poster = photo_field("Обложка", "gallery/video", blank=True)
    is_published = models.BooleanField("Опубликовано", default=True)
    updated_at = models.DateTimeField(auto_now=True)
    collections = models.ManyToManyField(
        "VideoCollection", verbose_name="Подборки", through="VideoCollectionItem", related_name="videos", blank=True
    )
    show_collection_tags = models.BooleanField(
        "Показывать подборки на карточке",
        default=True,
        help_text="Под описанием ролика — ссылки на его подборки. Снимите, чтобы не показывать их у этого ролика; "
        "ссылки на услуги останутся.",
    )
    services = models.ManyToManyField(
        "catalog.Service",
        verbose_name="Услуги",
        related_name="videos",
        blank=True,
        help_text="Ссылки на страницы услуг под описанием ролика. Видны только услуги, чья страница открыта на сайте: "
        "опубликованные, с отдельной страницей, в опубликованной категории.",
    )
    card, card_avif = image_specs("poster", 800, 450)
    card_small, card_small_avif = image_specs("poster", 480, 270)
    square, square_avif = image_specs("poster", 400, 400)
    og = og_spec("poster")

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Видео"
        verbose_name_plural = "Видео"

    def __str__(self):
        return self.title

    @property
    def duration_text(self) -> str:
        return format_duration(self.duration)


class VideoCollectionQuerySet(PublishedQuerySet):
    def shown(self):
        """Опубликованные подборки, где есть хотя бы один опубликованный ролик."""
        return (
            self.published()
            .annotate(video_count=Count("items", filter=Q(items__video__is_published=True), distinct=True))
            .filter(video_count__gt=0)
            .order_by("order", "id")
        )

    def with_first_video(self):
        """+ `first_video_id` — первый опубликованный ролик подборки по её порядку (обложка, если своей нет)."""
        first = (
            VideoCollectionItem.objects.filter(collection=OuterRef("pk"), video__is_published=True)
            .order_by("order", "id")
            .values("video_id")[:1]
        )
        return self.annotate(first_video_id=Subquery(first))


class VideoCollection(SeoModel, OrderedModel):
    title = models.CharField("Название", max_length=255)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True, help_text=SLUG_HELP)
    description = models.TextField("Описание", blank=True)
    cover = photo_field("Обложка", "gallery/collections")
    is_published = models.BooleanField("Опубликовано", default=True)
    cover_square, cover_square_avif = image_specs("cover", 400, 400)
    cover_og = og_spec("cover")

    objects = VideoCollectionQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Подборка видео"
        verbose_name_plural = "Подборки видео"

    def __str__(self):
        return self.title

    def slug_source(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.slug_source())
        with transaction.atomic():
            remember_slug_change(self)
            remember_page_change(self)
            super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("content:video_collection", args=[self.slug])

    @property
    def has_page(self) -> bool:
        """Страница подборки без опубликованных роликов — 404 (`views.video_collection`): IndexNow её не шлёт."""
        return self.pk is not None and self.items.filter(video__is_published=True).exists()

    def shown_videos(self) -> list[Video]:
        return list(
            Video.objects.published()
            .filter(collection_items__collection=self)
            .order_by("collection_items__order", "collection_items__id")
        )

    @cached_property
    def cover_video(self) -> Video | None:
        return next(iter(self.shown_videos()), None)


class VideoCollectionItem(models.Model):
    collection = models.ForeignKey(
        VideoCollection, verbose_name="Подборка", on_delete=models.CASCADE, related_name="items"
    )
    video = models.ForeignKey(Video, verbose_name="Видео", on_delete=models.CASCADE, related_name="collection_items")
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Видео в подборке"
        verbose_name_plural = "Видео в подборках"
        constraints = [
            models.UniqueConstraint(fields=["collection", "video"], name="unique_video_in_collection"),
        ]

    def __str__(self):
        return f"{self.collection_id}: {self.video_id}"
