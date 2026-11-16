from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import localize_input
from django.utils.html import format_html
from unfold.admin import TabularInline
from unfold.decorators import action
from unfold.forms import PaginationInlineFormSet
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.content.dzen import DzenEmbedURLField, DzenFetchError, download_poster, fetch_video, validate_embed_url
from apps.content.models import Event, GalleryPhoto, Partner, Review, Video, VideoCollection, VideoCollectionItem
from apps.content.yandex import ReviewFetchError, fetch_review
from apps.core.admin_utils import (
    SEO_FIELDSET,
    DuplicateAdminMixin,
    OrderedInlineMixin,
    SeoGenerateMixin,
    SiteModelAdmin,
    TrashAdminMixin,
    image_preview,
    move_to_top,
    thumbnail_html,
)
from apps.core.bulk_upload import BulkUploadForm, append_images
from apps.core.models import next_order


class EventPeriodFilter(admin.SimpleListFilter):
    title = "Период"
    parameter_name = "period"

    def lookups(self, request, model_admin):
        return [("upcoming", "Предстоящие"), ("past", "Прошедшие")]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == "upcoming":
            return queryset.upcoming(today)
        if self.value() == "past":
            return queryset.past(today)
        return queryset


@admin.register(Event)
class EventAdmin(SeoGenerateMixin, DuplicateAdminMixin, TrashAdminMixin, SiteModelAdmin):
    help_intro = (
        "Предстоящие — на странице «Мероприятия» и до трёх на главной. "
        "На следующий день после окончания мероприятие становится прошедшим."
    )
    help_anchor = "events"
    list_display = ["photo", "title", "date", "status", "is_published", "show_after_date"]
    list_display_links = ["photo", "title"]
    list_editable = ["is_published"]
    list_filter = [EventPeriodFilter, "is_published", "show_after_date"]
    # date_hierarchy убран: годы 2022/2023/2027 сверху списка не помогали найти мероприятие
    search_fields = ["title"]
    slug_source_fields = ("title", "date")
    actions_list = ["trash"]
    actions_detail = ["duplicate"]
    seo_source_fields = ("title", "date", "end_date", "start_time", "venue", "price", "description")
    fieldsets = (
        (
            "Основное",
            {
                "classes": ["tab"],
                "fields": [
                    "title",
                    "slug",
                    ("date", "end_date", "start_time"),
                    "venue",
                    "price",
                    "description",
                    "link",
                    "image",
                    ("is_published", "show_after_date"),
                ],
            },
        ),
        SEO_FIELDSET,
    )

    @action(description="Дублировать", url_path="duplicate", permissions=["duplicate"], icon="content_copy")
    def duplicate(self, request, object_id):
        return self.duplicate_view(
            request, object_id, "Поменяйте дату и опубликуйте — адрес страницы подстроится под название и год."
        )

    @admin.display(description="Фото")
    def photo(self, obj):
        return thumbnail_html(obj, "card_small")

    @admin.display(description="Статус")
    def status(self, obj):
        if not obj.is_published:
            return "Черновик"
        if not obj.is_past:
            return "Предстоящее"
        return "Прошедшее, в архиве" if obj.show_after_date else "Прошедшее, скрыто"


class OrderedPhotoAdmin(SiteModelAdmin):
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Review)
class ReviewAdmin(TrashAdminMixin, SiteModelAdmin):
    help_intro = "Новые сверху — по дате отзыва. Ссылка на отзыв с Яндекса и кнопка «Подтянуть» заполнят текст и дату."
    help_anchor = "reviews"
    # Порядок — по дате (Meta.ordering), без перетаскивания.
    list_display = ["__str__", "date", "is_published"]
    list_editable = ["is_published"]
    search_fields = ["text"]
    list_filter = ["is_published"]
    date_hierarchy = "date"
    fields = ["link", "date", "text", "photo", "is_published"]
    actions_list = ["trash"]

    class Media:
        js = ["js/admin_review_fetch.js"]

    def get_urls(self):
        fetch = path(
            "fetch-yandex/", self.admin_site.admin_view(self.fetch_yandex_view), name="content_review_fetch_yandex"
        )
        return [fetch, *super().get_urls()]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "link":
            # Кнопку «Подтянуть» рядом с полем добавляет admin_review_fetch.js.
            field.widget.attrs["data-yandex-fetch-url"] = reverse("admin:content_review_fetch_yandex")
            field.help_text = (
                "Ссылка на отзыв с Яндекса (reviews.yandex.ru): «Подтянуть» заполнит текст и дату. "
                "Открывается по клику на подпись источника под отзывом."
            )
        return field

    def fetch_yandex_view(self, request):
        """Текст и дата отзыва по ссылке — JSON для кнопки «Подтянуть»."""
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        try:
            review = fetch_review(request.GET.get("url", ""))
        except ReviewFetchError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"text": review.text, "date": localize_input(review.date) if review.date else ""})


@admin.register(Partner)
class PartnerAdmin(OrderedPhotoAdmin):
    help_intro = "Логотипы в блоке «Партнёры» на странице «О нас». Порядок — перетаскиванием."
    help_anchor = "gallery"
    list_display = ["preview", "name", "link"]
    list_display_links = ["preview", "name"]
    fields = ["name", "link", "logo"]
    preview = image_preview("logo_small")


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(OrderedPhotoAdmin):
    help_intro = (
        "Фото для страницы «Галерея» и полосы «Как это выглядит» на главной, «О нас» и «Отзывах». "
        "Порядок — перетаскиванием; новые фото встают в конец — отметьте их и выберите «Поставить в начало»."
    )
    help_anchor = "gallery"
    list_display = ["preview", "caption"]
    list_display_links = ["preview", "caption"]
    list_per_page = 400  # все фото на одной странице: перетаскивание работает только в пределах страницы
    fields = ["image", "caption"]
    actions = ["move_to_top"]
    actions_list = ["bulk_upload"]
    preview = image_preview("thumb", size=96)

    @admin.action(description="Поставить в начало", permissions=["change"])
    def move_to_top(self, request, queryset):
        moved = move_to_top(GalleryPhoto, queryset)
        messages.success(request, f"Поставлено в начало: {moved}.")

    @action(description="Загрузить фото пачкой", url_path="bulk-upload", permissions=["add"])
    def bulk_upload(self, request):
        form = BulkUploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            created = append_images(GalleryPhoto, form.cleaned_data["photos"])
            messages.success(request, f"Загружено фото: {len(created)}.")
            return redirect("admin:content_galleryphoto_changelist")
        context = {
            **self.admin_site.each_context(request),
            "title": "Загрузить фото в галерею",
            "opts": self.model._meta,
            "form": form,
        }
        return render(request, "admin/bulk_upload.html", context)


DZEN_ERROR = (
    "Не удалось получить данные ролика с Дзена: {} Попробуйте позже или заполните название и загрузите обложку вручную."
)


class VideoAdminForm(forms.ModelForm):
    """При новом или сменённом коде ролика берёт с Дзена название, описание, длительность и обложку (`self.dzen`,
    `self.dzen_poster`). Заполняет только поля, которые администратор не задал сам: у новой записи — пустые,
    при смене ролика — все, кроме изменённых в этой же отправке."""

    class Meta:
        model = Video
        fields = "__all__"
        help_texts = {
            "embed_url": (
                "На Дзене под видео «⋯» → «Поделиться» → «Встроить», скопируйте код целиком и вставьте сюда. "
                "Название, описание и обложку можно не заполнять — сайт возьмёт их с Дзена."
            ),
            "title": "Пусто — название ролика на Дзене.",
            "description": "Пусто — описание ролика на Дзене.",
            "poster": "Пусто — обложка ролика на Дзене. Можно загрузить свою, лучше 16:9.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dzen = None
        self.dzen_poster = None
        self.dzen_checked = False
        if "title" in self.fields:
            self.fields["title"].required = False  # пустое заполнится с Дзена; без Дзена проверяет clean()

    def _admin_value(self, cleaned, name: str) -> bool:
        """Значение поля задал администратор — данными Дзена его не заменяем."""
        return bool(cleaned.get(name)) and (self.instance._state.adding or name in self.changed_data)

    def clean_embed_url(self):
        # Валидатор модели срабатывает только после clean(): чужую ссылку отсекаем до запроса к Дзену.
        value = self.cleaned_data["embed_url"]
        validate_embed_url(value)
        return value

    def clean(self):
        cleaned = super().clean()
        if "embed_url" not in self.fields or "embed_url" in self._errors:
            return cleaned
        if self.instance._state.adding or "embed_url" in self.changed_data:
            self._fill_from_dzen(cleaned)
        if not cleaned.get("title") and "title" not in self._errors:
            self.add_error("title", "Заполните название.")
        if not cleaned.get("poster") and "poster" not in self._errors:
            self.add_error("poster", "Загрузите обложку: без неё ролик не показать на сайте.")
        return cleaned

    def _fill_from_dzen(self, cleaned) -> None:
        self.dzen_checked = True
        own_title = self._admin_value(cleaned, "title")
        own_poster = self._admin_value(cleaned, "poster")
        try:
            self.dzen = fetch_video(cleaned["embed_url"])
        except DzenFetchError as exc:
            # Без Дзена сохранить можно, только если название и обложку администратор задал сам.
            if not (own_title and own_poster):
                self.add_error("embed_url", DZEN_ERROR.format(exc))
            return
        if not own_title:
            cleaned["title"] = self.dzen.title
        if not self._admin_value(cleaned, "description"):
            cleaned["description"] = self.dzen.description
        if own_poster:
            return
        try:
            if not self.dzen.thumbnail_url:
                raise DzenFetchError("У ролика на Дзене нет обложки — загрузите её вручную.")
            self.dzen_poster = download_poster(self.dzen.thumbnail_url)
        except DzenFetchError as exc:
            self.add_error("poster", str(exc))
            return
        cleaned["poster"] = self.dzen_poster

    def save(self, commit=True):
        if self.dzen_checked:
            self.instance.duration = self.dzen.duration if self.dzen else None
        return super().save(commit)


class AppendToCollectionFormSet(PaginationInlineFormSet):
    """Ролик, добавленный в подборку из формы ролика, встаёт в конец подборки (а не в начало с order=0)."""

    def save_new(self, form, commit=True):
        form.instance.order = next_order(VideoCollectionItem, collection=form.instance.collection)
        return super().save_new(form, commit)


class VideoCollectionItemInline(TabularInline):
    model = VideoCollectionItem
    fk_name = "video"
    formset = AppendToCollectionFormSet
    extra = 0
    autocomplete_fields = ["collection"]
    fields = ["collection"]
    verbose_name = "Подборка"
    verbose_name_plural = "Подборки"


@admin.register(Video)
class VideoAdmin(OrderedPhotoAdmin):
    help_intro = (
        "Ролики с Дзена для вкладки «Видео» в галерее. Вставьте код «Встроить» — название, описание и обложку "
        "сайт возьмёт с Дзена; новые ролики встают в конец — отметьте их и выберите «Поставить в начало»."
    )
    help_anchor = "gallery"
    form = VideoAdminForm
    formfield_overrides = {DzenEmbedURLField: {"widget": UnfoldAdminTextareaWidget(attrs={"rows": 3})}}
    fields = ["embed_url", "title", "description", "poster", "is_published"]
    inlines = [VideoCollectionItemInline]
    list_display = ["preview", "title", "collections_list", "is_published"]
    list_display_links = ["preview", "title"]
    list_editable = ["is_published"]
    list_filter = ["is_published", "collections"]
    search_fields = ["title"]
    list_per_page = 400  # все ролики на одной странице: перетаскивание работает только в пределах страницы
    actions = ["move_to_top"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("collections")

    @admin.display(description="Обложка")
    def preview(self, obj):
        image = thumbnail_html(obj, "card_small", 96)
        if not obj.duration_text:
            return image
        return format_html('{}<div class="mt-1 text-xs tabular-nums">▶ {}</div>', image, obj.duration_text)

    @admin.display(description="Подборки")
    def collections_list(self, obj):
        return ", ".join(collection.title for collection in obj.collections.all()) or "—"

    @admin.action(description="Поставить в начало", permissions=["change"])
    def move_to_top(self, request, queryset):
        moved = move_to_top(Video, queryset)
        messages.success(request, f"Поставлено в начало: {moved}.")


class CollectionVideoInline(OrderedInlineMixin, TabularInline):
    model = VideoCollectionItem
    fk_name = "collection"
    extra = 0
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["video"]
    fields = ["video", "order"]
    verbose_name = "Ролик"
    verbose_name_plural = "Ролики подборки"


class VideoCollectionAdminForm(forms.ModelForm):
    class Meta:
        model = VideoCollection
        fields = "__all__"
        help_texts = {
            "cover": "Квадратная плитка подборки. Пусто — обложка первого ролика подборки.",
            "description": "Под названием на странице подборки. Необязательно.",
        }


@admin.register(VideoCollection)
class VideoCollectionAdmin(SeoGenerateMixin, OrderedPhotoAdmin):
    help_intro = (
        "Подборки роликов для вкладки «Видео» в галерее, у каждой — своя страница. "
        "Ролики добавляются внизу формы подборки, порядок — перетаскиванием."
    )
    help_anchor = "gallery"
    form = VideoCollectionAdminForm
    fieldsets = (
        (
            "Основное",
            {"classes": ["tab"], "fields": ["title", "slug", "description", "cover", "is_published"]},
        ),
        SEO_FIELDSET,
    )
    seo_source_fields = ("title", "description")
    slug_source_fields = ("title",)
    inlines = [CollectionVideoInline]
    list_display = ["preview", "title", "video_count", "is_published"]
    list_display_links = ["preview", "title"]
    list_editable = ["is_published"]
    search_fields = ["title"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(video_total=Count("items"))

    @admin.display(description="Обложка")
    def preview(self, obj):
        if obj.cover:
            return thumbnail_html(obj, "cover_square")
        video = obj.cover_video
        return thumbnail_html(video, "square") if video else "—"

    @admin.display(description="Роликов", ordering="video_total")
    def video_count(self, obj):
        return obj.video_total
