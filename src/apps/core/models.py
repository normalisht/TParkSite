import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Max, Q
from django.urls import reverse

from apps.core import about_defaults, seasons
from apps.core.fields import INFO_HTML_EXTENSIONS, HtmlField, image_specs, logo_spec, og_spec, photo_field
from apps.core.maps import MapEmbedURLField
from apps.core.seasons import format_day_month, validate_day_month, validate_site_link
from apps.core.slugs import SLUG_HELP, unique_slug


class OrderedModel(models.Model):
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


def next_order(model, **scope) -> int:
    """Порядок для новой записи — после последней (в пределах `scope`, например `category=…`)."""
    return (model._default_manager.filter(**scope).aggregate(m=Max("order"))["m"] or 0) + 1


PARK_ADDRESS = "Калужская область, Жуковский район, село Восход"
DEFAULT_TITLE_SUFFIX = "Т-Парк, Калужская область"
# Высота логотипа в шапке, px (класс h-11 в partials/header.html и 500.html).
HEADER_LOGO_HEIGHT = 44


def logo_display_width(width: int | None, height: int | None) -> int | None:
    """Ширина логотипа в шапке при высоте `HEADER_LOGO_HEIGHT` — для width/height у <img> (без сдвига вёрстки)."""
    if not (width and height):
        return None
    return round(HEADER_LOGO_HEIGHT * width / height)


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
    updated_at = models.DateTimeField("Изменено", auto_now=True)
    header_logo = photo_field(
        "Логотип",
        "logo",
        size=(3000, 1000),
        fmt=None,
        width_field="header_logo_width",
        height_field="header_logo_height",
        help_text="PNG с прозрачным фоном, горизонтальный, высотой от 132 px. В шапке — высотой 44 px, по центру "
        "между краями картинки: если над надписью что-то выступает (как солнце), оставьте снизу прозрачное поле той же "
        "высоты, иначе надпись окажется ниже кнопок. Ещё логотип попадает в разметку для поисковиков. "
        "Пусто — стандартный логотип.",
    )
    header_logo_width = models.PositiveIntegerField(null=True, editable=False)
    header_logo_height = models.PositiveIntegerField(null=True, editable=False)
    header_logo_img = logo_spec("header_logo", HEADER_LOGO_HEIGHT * 3)
    address = models.CharField(
        "Адрес",
        max_length=255,
        blank=True,
        default=PARK_ADDRESS,
        help_text="Главная, подвал, «Контакты», «О нас» и место мероприятий без своего адреса.",
    )
    map_embed_url = MapEmbedURLField(
        "Яндекс Карта на странице контактов",
        max_length=1000,
        blank=True,
        help_text="В Яндекс Картах: «Поделиться» → «Встроить карту» → скопируйте код и вставьте сюда целиком.",
    )
    vk_url = models.URLField(
        "ВКонтакте",
        max_length=500,
        blank=True,
        help_text="Кнопка в «Связаться», в подвале и на «Контактах». Пусто — кнопки нет.",
    )
    max_url = models.URLField(
        "MAX", max_length=500, blank=True, help_text="Ссылка на профиль или канал в MAX. Пусто — кнопки нет."
    )
    reviews_url = models.URLField(
        "Отзывы на Яндекс Картах",
        max_length=500,
        blank=True,
        help_text=(
            "Страница отзывов о Т-Парке: кнопка «Все отзывы на Яндекс Картах» на странице отзывов и «Оставить отзыв» — "
            "там же, на «Контактах» и на главной. Пусто — кнопок нет."
        ),
    )
    home_intro = HtmlField(
        "Вступление на главной",
        help_text="Текст в начале главной. Он же — описание сайта для поисковиков и соцсетей по умолчанию.",
    )
    home_show_events = models.BooleanField(
        "Ближайшие мероприятия на главной",
        default=True,
        help_text="Блок появляется, только если есть предстоящие мероприятия.",
    )
    events_intro = HtmlField("Вступление на странице мероприятий", help_text="Текст в начале страницы «Мероприятия».")
    contacts_text = HtmlField("Текст на странице контактов", help_text="Дополнительный текст на странице «Контакты».")

    # Страница «О нас»
    about_motto = models.CharField(
        "Цитата в шапке",
        max_length=255,
        blank=True,
        default=about_defaults.MOTTO,
        help_text="Одна фраза крупным шрифтом в начале страницы.",
    )
    about_photo = photo_field("Фото в шапке", "about", help_text="Лучше горизонтальное: парк, лес, река, люди.")
    about_card, about_card_avif = image_specs("about_photo", 960, 720)
    about_og = og_spec("about_photo")
    about_text = HtmlField("О нас")
    founder_name = models.CharField("Основатель: имя", max_length=128, blank=True, default=about_defaults.FOUNDER_NAME)
    founder_lead = models.CharField(
        "Основатель: подзаголовок", max_length=255, blank=True, default=about_defaults.FOUNDER_LEAD
    )
    founder_photo = photo_field("Основатель: фото", "about", help_text="Портрет, лучше вертикальный.")
    founder_card, founder_card_avif = image_specs("founder_photo", 600, 750)
    founder_text = HtmlField("Основатель: о нём", help_text="Регалии и роли — удобнее списком.")
    nearby_text = HtmlField("Что рядом", help_text="Блок «Что рядом» на «О нас»: достопримечательности, жильё, кафе.")
    safety_page = models.ForeignKey(
        "InfoPage",
        verbose_name="Правила безопасности",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=(
            "Инфо-страница, на которую ведёт плашка «Правила безопасности» на «О нас». "
            "Ссылка в подвале — галочкой «В подвале» у самой страницы."
        ),
    )
    privacy_page = models.ForeignKey(
        "InfoPage",
        verbose_name="Политика конфиденциальности",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=(
            "Инфо-страница, на которую ведёт ссылка в баннере cookie. Пока не указана или не опубликована — ссылки нет. "
            "Ссылка в подвале — галочкой «В подвале» у самой страницы."
        ),
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
        help_text="Показывается в превью ссылки во ВКонтакте, Telegram и мессенджерах, если у страницы нет своего фото. "
        "Лучше горизонтальная, 1200×630.",
    )
    og_card = og_spec("og_image")
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

    @classmethod
    def for_request(cls, request) -> SiteSettings:
        """Настройки один раз на запрос (контекст-процессоры, JSON-LD); без запроса — как `load()`."""
        if request is None:
            return cls.load()
        from apps.core.request_cache import cached_on_request

        return cached_on_request(request, "site_settings", cls.load)


class Phone(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="phones")
    number = models.CharField(
        "Номер",
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", "10 цифр без +7 и 8, например 9029856594.")],
        help_text="10 цифр без +7, 8 и пробелов. Первый номер — главный в кнопке «Связаться».",
    )
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)
    is_whatsapp = models.BooleanField(
        "WhatsApp", default=False, help_text="Кнопка WhatsApp ведёт на этот номер. Можно отметить только у одного."
    )
    is_telegram = models.BooleanField(
        "Telegram", default=False, help_text="Кнопка Telegram ведёт на этот номер. Можно отметить только у одного."
    )

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


class Season(models.Model):
    """Сезонное оформление (apps/core/seasons.py): по записи на сезон, набор сезонов фиксирован (`Kind`)."""

    Kind = seasons.Kind
    Mode = seasons.Mode
    DEFAULT_DATES = {
        Kind.NEW_YEAR: ("15.12", "14.01"),
        Kind.WINTER: ("01.12", "28.02"),
        Kind.AUTUMN: ("01.09", "31.10"),
    }

    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="seasons")
    kind = models.CharField("Сезон", max_length=16, choices=Kind.choices, unique=True, editable=False)
    mode = models.CharField(
        "Показ",
        max_length=8,
        choices=Mode.choices,
        default=Mode.AUTO,
        help_text="«По датам» — тема сама включается и выключается каждый год. «Включено» — сразу для всех "
        "посетителей и без учёта дат, пока не вернёте «По датам» (например, ранний снег). Если подходят несколько "
        "сезонов, показывается старший: «Новый год», затем «Зима», затем «Осень» — даже когда младший включён вручную.",
    )
    start = models.CharField("С", max_length=5, validators=[validate_day_month], help_text="День и месяц: 15.12.")
    end = models.CharField(
        "По",
        max_length=5,
        validators=[validate_day_month],
        help_text="Включительно. Может быть в следующем году: 15.12 — 14.01.",
    )
    logo = photo_field(
        "Логотип на сезон",
        "logo",
        size=(3000, 1000),
        fmt=None,
        width_field="logo_width",
        height_field="logo_height",
        help_text="Заменяет логотип в шапке, пока тема показывается; требования — как у основного логотипа "
        "(вкладка «Логотип»). В разметку для поисковиков не попадает. Пусто — стандартный логотип в сезонном "
        "варианте (зимой — со снегом, на Новый год — ещё с шариками и звездой, осенью — с листьями), а если загружен "
        "свой основной логотип — он.",
    )
    logo_width = models.PositiveIntegerField(null=True, editable=False)
    logo_height = models.PositiveIntegerField(null=True, editable=False)
    logo_img = logo_spec("logo", HEADER_LOGO_HEIGHT * 3)

    class Meta:
        verbose_name = "Сезонное оформление"
        verbose_name_plural = "Сезонное оформление"
        ordering = ["kind"]  # new_year < winter — как в seasons.PRIORITY

    def __str__(self):
        return self.get_kind_display()

    def clean(self):
        for field in ("start", "end"):
            try:
                setattr(self, field, format_day_month(getattr(self, field)))
            except ValueError:
                pass  # ошибку покажет валидатор поля

    @classmethod
    def ensure_for(cls, site: SiteSettings) -> None:
        """Создаёт недостающие сезоны: импорт со сбросом удаляет их вместе с настройками, а добавлять в админке нельзя."""
        for kind, (start, end) in cls.DEFAULT_DATES.items():
            cls.objects.get_or_create(kind=kind, defaults={"settings": site, "start": start, "end": end})


class AnnouncementQuerySet(models.QuerySet):
    def current(self, day: date) -> Announcement | None:
        """Плашка для показа в этот день: первая по порядку включённая, у которой подходят даты."""
        return (
            self.filter(is_published=True)
            .filter(Q(starts_on__isnull=True) | Q(starts_on__lte=day))
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=day))
            .order_by("order", "id")
            .first()
        )


class Announcement(OrderedModel):
    """Плашка под шапкой на всех страницах (partials/site_banner.html); одновременно показывается одна."""

    text = models.CharField(
        "Текст",
        max_length=160,
        help_text="Одна фраза в полосе под шапкой на всех страницах сайта, например «Новогодние корпоративы — "
        "бронируйте даты заранее».",
    )
    link = models.CharField(
        "Ссылка",
        max_length=500,
        blank=True,
        validators=[validate_site_link],
        help_text="Куда ведёт плашка: адрес страницы сайта (/events/…) или полная ссылка (https://…). "
        "Пусто — плашка без ссылки.",
    )
    is_published = models.BooleanField(
        "Показывать",
        default=True,
        help_text="Снимите галочку, чтобы убрать плашку с сайта, не удаляя её. Одновременно показывается одна плашка — "
        "первая по порядку в списке из тех, что включены и подходят по датам.",
    )
    starts_on = models.DateField(
        "Показывать с", null=True, blank=True, help_text="Необязательно: до этой даты плашки на сайте нет."
    )
    ends_on = models.DateField(
        "по", null=True, blank=True, help_text="Включительно. Необязательно: после этой даты плашка пропадёт сама."
    )

    objects = AnnouncementQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Плашка"
        verbose_name_plural = "Плашки"

    def __str__(self):
        return self.text

    def clean(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Дата окончания раньше даты начала."})


class InfoPage(SeoModel, OrderedModel):
    class Layout(models.TextChoices):
        TEXT = "text", "Текст"
        RULES = "rules", "Правила"
        FAQ = "faq", "Вопросы и ответы"

    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True, help_text=SLUG_HELP)
    lead = models.CharField(
        "Подзаголовок",
        max_length=300,
        blank=True,
        help_text="Одна-две фразы под заголовком страницы. Он же — описание для поисковиков, если на вкладке SEO оно пустое.",
    )
    cover = photo_field("Фото в шапке", "info", help_text="Необязательно. Справа от заголовка, обрезается до 4:3.")
    cover_card, cover_card_avif = image_specs("cover", 960, 720)
    cover_og = og_spec("cover")
    layout = models.CharField(
        "Оформление",
        max_length=8,
        choices=Layout.choices,
        default=Layout.TEXT,
        help_text=(
            "«Текст» — обычная статья. «Правила» — каждый раздел (заголовок H2) карточкой с номером, пункты списков "
            "с галочками. «Вопросы и ответы» — каждый заголовок H3 — вопрос, ответ раскрывается по нажатию."
        ),
    )
    body = HtmlField(
        "Текст",
        extensions=INFO_HTML_EXTENSIONS,
        help_text=(
            "Заголовки H2 делят текст на разделы (от трёх разделов появляется оглавление). "
            "Кнопка «Цитата» — выноска «Важно», таблица — кнопкой редактора."
        ),
    )
    is_published = models.BooleanField(
        "Опубликовано",
        default=True,
        help_text="Снятая — страница не откроется, ссылок на неё в подвале и на «О нас» не будет.",
    )
    show_in_footer = models.BooleanField(
        "В подвале",
        default=False,
        help_text="Ссылка на страницу внизу каждой страницы сайта, рядом с «© Т-Парк». Только у опубликованной.",
    )

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Инфо-страница"
        verbose_name_plural = "Инфо-страницы"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        from apps.core.redirects import remember_slug_change

        with transaction.atomic():
            remember_slug_change(self)
            super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("core:info", args=[self.slug])


SITE_PATH_RE = re.compile(r"^/(?![/\\])[^\s\\]*\Z")


def is_site_path(value: str) -> bool:
    """Путь внутри сайта: начинается с одного «/», без схемы, хоста, обратных слэшей и пробелов."""
    return bool(SITE_PATH_RE.match(value or ""))


def validate_site_path(value: str) -> None:
    if not is_site_path(value):
        raise ValidationError("Нужен путь от корня сайта, например /category/shkola/ (без https:// и домена).")


class Redirect(models.Model):
    """301 со старого адреса страницы на новый. Создаётся сам при смене slug (`apps.core.redirects`), можно и вручную."""

    old_path = models.CharField(
        "Старый адрес",
        max_length=255,
        unique=True,
        validators=[validate_site_path],
        help_text="Путь от корня сайта: /category/shkola-2026/",
    )
    new_path = models.CharField(
        "Новый адрес",
        max_length=255,
        validators=[validate_site_path],
        help_text="Путь от корня сайта: /category/shkola/",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Редирект"
        verbose_name_plural = "Редиректы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.old_path} → {self.new_path}"

    def clean(self):
        if "?" in self.old_path or "#" in self.old_path:
            raise ValidationError({"old_path": "Старый адрес — только путь, без «?» и «#»."})
        if self.old_path == self.new_path:
            raise ValidationError({"new_path": "Новый адрес совпадает со старым — получится бесконечный редирект."})
