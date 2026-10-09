from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core import about_defaults
from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.maps import MapEmbedURLField
from apps.core.slugs import unique_slug


class OrderedModel(models.Model):
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


PARK_ADDRESS = "Калужская область, Жуковский район, село Восход"
DEFAULT_TITLE_SUFFIX = "Т-Парк, Калужская область"


class SeoModel(models.Model):
    """SEO-поля страницы: свой title и description (пусто — собираются из названия и текста) и дата изменения для sitemap."""

    seo_title = models.CharField(
        "Заголовок для поисковиков (title)",
        max_length=70,
        blank=True,
        help_text="До 60–70 символов, выводится как есть. Пусто — «Название — Т-Парк, Калужская область».",
    )
    seo_description = models.CharField(
        "Описание для поисковиков (description)",
        max_length=300,
        blank=True,
        help_text="Лучше 120–160 символов: это текст под ссылкой в выдаче. Пусто — начало текста страницы.",
    )
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        abstract = True


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


def _seo_pair(page: str):
    title = models.CharField(f"{page}: title", max_length=70, blank=True)
    description = models.CharField(f"{page}: description", max_length=300, blank=True)
    return title, description


class SiteSettings(models.Model):
    address = models.CharField("Адрес", max_length=255, blank=True, default=PARK_ADDRESS)
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
    contacts_text = HtmlField("Текст на странице контактов")

    # Страница «О нас»
    about_motto = models.CharField(
        "Цитата в шапке",
        max_length=255,
        blank=True,
        default=about_defaults.MOTTO,
        help_text="Одна фраза крупным шрифтом в начале страницы.",
    )
    about_photo = photo_field("Фото в шапке", "about", help_text="Лучше горизонтальное: парк, лес, река, люди.")
    about_card = image_spec("about_photo", 960, 720)
    about_text = HtmlField("О нас")
    founder_name = models.CharField("Основатель: имя", max_length=128, blank=True, default=about_defaults.FOUNDER_NAME)
    founder_lead = models.CharField(
        "Основатель: подзаголовок", max_length=255, blank=True, default=about_defaults.FOUNDER_LEAD
    )
    founder_photo = photo_field("Основатель: фото", "about", help_text="Портрет, лучше вертикальный.")
    founder_card = image_spec("founder_photo", 600, 750)
    founder_text = HtmlField("Основатель: о нём", help_text="Регалии и роли — удобнее списком.")
    nearby_text = HtmlField("Что рядом")
    safety_page = models.ForeignKey(
        "InfoPage",
        verbose_name="Правила безопасности",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Инфо-страница, на которую ведёт плашка «Правила безопасности» на странице «О нас».",
    )

    # Разметка организации (schema.org LocalBusiness)
    address_region = models.CharField("Регион", max_length=128, blank=True, default="Калужская область")
    address_locality = models.CharField(
        "Населённый пункт", max_length=128, blank=True, default="Жуковский район, село Восход"
    )
    street_address = models.CharField("Улица, дом", max_length=255, blank=True)
    postal_code = models.CharField("Индекс", max_length=6, blank=True)
    latitude = models.DecimalField("Широта", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Долгота", max_digits=9, decimal_places=6, null=True, blank=True)
    opening_hours = models.CharField(
        "Часы работы", max_length=128, blank=True, help_text="В формате schema.org, например: Mo-Su 09:00-21:00."
    )
    price_range = models.CharField("Уровень цен", max_length=32, blank=True, help_text="Например: ₽₽ или 500–5000 ₽.")
    yandex_maps_url = models.URLField(
        "Т-Парк на Яндекс Картах",
        max_length=500,
        blank=True,
        help_text="Ссылка на карточку организации: поисковики свяжут сайт с карточкой, её рейтингом и отзывами.",
    )

    # SEO
    seo_title_suffix = models.CharField(
        "Окончание заголовков",
        max_length=64,
        blank=True,
        default=DEFAULT_TITLE_SUFFIX,
        help_text="Добавляется к названию страницы: «Сплавы — Т-Парк, Калужская область».",
    )
    og_image = photo_field(
        "Картинка для соцсетей",
        "seo",
        size=(2400, 1260),
        help_text="Показывается в превью ссылки в VK, Telegram и мессенджерах, если у страницы нет своего фото. "
        "Лучше горизонтальная, 1200×630.",
    )
    og_card = image_spec("og_image", 1200, 630)
    seo_home_title, seo_home_description = _seo_pair("Главная")
    seo_events_title, seo_events_description = _seo_pair("Мероприятия")
    seo_about_title, seo_about_description = _seo_pair("О нас")
    seo_reviews_title, seo_reviews_description = _seo_pair("Отзывы")
    seo_gallery_title, seo_gallery_description = _seo_pair("Галерея")
    seo_contacts_title, seo_contacts_description = _seo_pair("Контакты")

    # Вебмастер и Метрика
    yandex_verification = models.CharField(
        "Код подтверждения Яндекс Вебмастера",
        max_length=64,
        blank=True,
        help_text='Из мета-тега: content="…". Регион сайта (Калужская область) задаётся в Вебмастере: '
        "«Информация о сайте» → «Региональность».",
    )
    google_verification = models.CharField("Код подтверждения Google Search Console", max_length=128, blank=True)
    yandex_metrika_id = models.CharField(
        "Номер счётчика Яндекс Метрики",
        max_length=16,
        blank=True,
        validators=[RegexValidator(r"^\d+$", "Только цифры номера счётчика.")],
    )

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


class ParkFormat(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="park_formats")
    name = models.CharField("Название", max_length=32, help_text="Например: T-park.")
    caption = models.CharField("Подпись", max_length=128, help_text="Например: тренинг-парк.")
    description = models.CharField("Описание", max_length=255, blank=True, help_text="Одна-две фразы, необязательно.")
    category = models.ForeignKey(
        "catalog.Category",
        verbose_name="Ссылка на категорию",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Карточка станет ссылкой, если категория опубликована.",
    )
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        verbose_name = "Формат"
        verbose_name_plural = "Форматы (О нас)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    @property
    def url(self) -> str:
        category = self.category
        return category.get_absolute_url() if category and category.is_published else ""


class FounderFact(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="founder_facts")
    value = models.CharField("Число", max_length=16, help_text="Например: 1000+.")
    label = models.CharField("Подпись", max_length=128, help_text="Например: тренингов провёл.")
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        verbose_name = "Цифра"
        verbose_name_plural = "Основатель в цифрах (О нас)"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.value} {self.label}"


class InfoPage(SeoModel):
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
