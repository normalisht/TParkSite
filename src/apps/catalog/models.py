from django.db import models
from django.urls import reverse

from apps.catalog.prices import format_price
from apps.core.fields import HtmlField, full_spec, image_spec, image_specs, og_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet, SeoModel
from apps.core.slugs import unique_slug


class CategoryGroup(OrderedModel):
    name = models.CharField("Название", max_length=128)
    categories = models.ManyToManyField("Category", related_name="groups", blank=True, verbose_name="Категории")
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Группа категорий"
        verbose_name_plural = "Группы категорий"

    def __str__(self):
        return self.name


class Category(SeoModel, OrderedModel):
    name = models.CharField("Название", max_length=128)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    description = HtmlField("Описание")
    preview = photo_field("Превью для главной", "catalog/previews", size=(1080, 720))
    preview_card, preview_card_avif = image_specs("preview", 640, 427)
    preview_large, preview_large_avif = image_specs(
        "preview", 1080, 720
    )  # шапка страницы категории: srcset с preview_card
    og = og_spec("preview")
    is_published = models.BooleanField("Опубликовано", default=False)

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", args=[self.slug])

    def published_services(self) -> list[Service]:
        links = (
            self.service_links.filter(service__is_published=True)
            .select_related("service")
            .prefetch_related("service__photos")
            .order_by("order", "id")
        )
        return [link.service for link in links]

    def related_categories(self, limit: int = 4) -> list[Category]:
        """Опубликованные категории из тех же групп меню — «Другие категории» внизу страницы."""
        related = (
            Category.objects.published()
            .filter(groups__in=self.groups.filter(is_published=True))
            .exclude(pk=self.pk)
            .distinct()
        )
        return list(related[:limit])


class CategoryPhoto(OrderedModel):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="photos")
    image = photo_field("Фото", "catalog/categories", blank=False)
    # Слайдер — рамка 16:9 с object-cover: режем так же на сервере, чтобы ширины в srcset были настоящими.
    slide, slide_avif = image_specs("image", 1600, 900)
    slide_small, slide_small_avif = image_specs("image", 800, 450)  # слайдер на телефоне: srcset со slide
    thumb = image_spec("image", 320, 240)
    full = full_spec("image")
    og = og_spec("image")

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото категории"
        verbose_name_plural = "Фото категории"

    def __str__(self):
        return f"Фото #{self.pk}"


class Service(SeoModel):
    name = models.CharField("Название", max_length=128)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    short_description = HtmlField("Краткое описание")
    description = HtmlField("Полное описание")
    price = models.CharField(
        "Цена",
        max_length=32,
        blank=True,
        help_text="Число («1500», «от 3500») — на сайте с «₽». Или текстом: «договорная».",
    )
    price_unit = models.CharField("За что", max_length=128, blank=True, help_text="Например: час, сутки, человек.")
    is_published = models.BooleanField("Опубликовано", default=True)
    has_page = models.BooleanField(
        "Отдельная страница", default=False, help_text="Карточка в категории ведёт на страницу услуги."
    )

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("catalog:service", args=[self.slug])

    @property
    def price_amount(self) -> str:
        """Цена без единицы: «₽» только у числа, «договорная» — как есть."""
        return format_price(self.price)

    @property
    def price_display(self) -> str:
        if not self.price:
            return ""
        amount = self.price_amount
        return f"{amount} / {self.price_unit}" if self.price_unit else amount

    @property
    def cover(self) -> ServicePhoto | None:
        """Первое фото — обложка карточки (берёт из prefetch, если он был)."""
        photos = self.photos.all()
        return photos[0] if photos else None


class CategoryService(OrderedModel):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="service_links", verbose_name="Категория"
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="category_links", verbose_name="Услуга")

    class Meta(OrderedModel.Meta):
        verbose_name = "Услуга в категории"
        verbose_name_plural = "Услуги в категории"
        unique_together = [("category", "service")]

    def __str__(self):
        return f"{self.category} → {self.service}"


class ServicePhoto(OrderedModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="photos")
    image = photo_field("Фото", "catalog/services", blank=False)
    # Слайдер — рамка 16:9 с object-cover: режем так же на сервере, чтобы ширины в srcset были настоящими.
    slide, slide_avif = image_specs("image", 1600, 900)
    slide_small, slide_small_avif = image_specs("image", 800, 450)  # слайдер на телефоне: srcset со slide
    thumb = image_spec("image", 320, 240)
    full = full_spec("image")
    og = og_spec("image")
    card, card_avif = image_specs("image", 640, 480)
    row, row_avif = image_specs("image", 336, 336)  # квадрат в строке услуги на телефоне (112 px × 3)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото услуги"
        verbose_name_plural = "Фото услуги"

    def __str__(self):
        return f"Фото #{self.pk}"
