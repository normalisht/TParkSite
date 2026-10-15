from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from unfold.admin import TabularInline
from unfold.forms import PaginationInlineFormSet
from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import SEO_FIELDSET, OrderedInlineMixin, SiteModelAdmin, image_preview, thumbnail_html
from apps.core.bulk_upload import MultipleImageField, append_images
from apps.core.models import next_order


class CategoryPhotoInline(OrderedInlineMixin, TabularInline):
    model = CategoryPhoto
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["preview", "image", "order"]
    readonly_fields = ["preview"]
    preview = image_preview("thumb")


class ServicePhotoInline(CategoryPhotoInline):
    model = ServicePhoto


class CategoryServiceInline(OrderedInlineMixin, TabularInline):
    model = CategoryService
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["service"]
    fields = ["service", "order"]
    verbose_name_plural = "Услуги"


class AppendToCategoryFormSet(PaginationInlineFormSet):
    """Услуга, добавленная в категорию из формы услуги, встаёт в конец категории (а не в начало с order=0)."""

    def save_new(self, form, commit=True):
        form.instance.order = next_order(CategoryService, category=form.instance.category)
        return super().save_new(form, commit)


class ServiceCategoryInline(TabularInline):
    model = CategoryService
    formset = AppendToCategoryFormSet
    extra = 0
    tab = True
    autocomplete_fields = ["category"]
    fields = ["category"]
    verbose_name_plural = "Категории"


class BulkPhotosForm(forms.ModelForm):
    """Поле «Загрузить фото пачкой»; фото добавляет `BulkPhotosAdminMixin.save_related`."""

    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")


class BulkPhotosAdminMixin:
    """После сохранения формы добавляет фото из `bulk_photos` в конец (`photo_model` с FK `photo_owner`)."""

    photo_model: type
    photo_owner: str

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        photos = form.cleaned_data.get("bulk_photos") or []  # в форме списка (list_editable) этого поля нет
        append_images(self.photo_model, photos, **{self.photo_owner: form.instance})


class CategoryAdminForm(BulkPhotosForm):
    menu_groups = forms.ModelMultipleChoiceField(
        CategoryGroup.objects.order_by("order", "id"),
        required=False,
        label="Группы меню",
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        help_text="Где категория видна в меню «Услуги» и на главной. Без группы её найдут только по прямой ссылке.",
    )

    class Meta:
        model = Category
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["menu_groups"].initial = list(self.instance.groups.all())


class ServiceAdminForm(BulkPhotosForm):
    class Meta:
        model = Service
        fields = "__all__"


@admin.register(CategoryGroup)
class CategoryGroupAdmin(SiteModelAdmin):
    help_intro = "Разделы меню «Услуги» в шапке и блоки категорий на главной. Порядок — перетаскиванием."
    help_anchor = "catalog"
    list_display = ["name", "is_published"]
    list_editable = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    filter_horizontal = ["categories"]
    fields = ["name", "categories", "is_published"]


@admin.register(Category)
class CategoryAdmin(BulkPhotosAdminMixin, SiteModelAdmin):
    help_intro = (
        "Страницы с услугами. В меню и на главной категория появится, когда опубликованы и она, и её группа. "
        "Новая категория — черновик."
    )
    help_anchor = "catalog"
    form = CategoryAdminForm
    photo_model = CategoryPhoto
    photo_owner = "category"
    list_display = ["photo", "name", "menu_groups_display", "services_count", "is_published"]
    list_display_links = ["photo", "name"]
    list_editable = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryPhotoInline, CategoryServiceInline]
    fieldsets = (
        (
            "Основное",
            {
                "classes": ["tab"],
                "fields": ["name", "slug", "menu_groups", "description", "preview", "is_published"],
            },
        ),
        ("Загрузка фото", {"classes": ["tab"], "fields": ["bulk_photos"]}),
        SEO_FIELDSET,
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(services_total=Count("service_links", distinct=True))
            .prefetch_related("groups", "photos")
        )

    @admin.display(description="Фото")
    def photo(self, obj):
        if obj.preview:
            return thumbnail_html(obj, "preview_card")
        photos = obj.photos.all()  # prefetch_related в get_queryset
        return thumbnail_html(photos[0], "thumb") if photos else "—"

    @admin.display(description="Группы меню")
    def menu_groups_display(self, obj):
        return ", ".join(group.name for group in obj.groups.all()) or "— нет в меню"

    @admin.display(description="Услуг", ordering="services_total")
    def services_count(self, obj):
        return obj.services_total

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if "menu_groups" in form.cleaned_data:  # в форме списка (list_editable) этого поля нет
            form.instance.groups.set(form.cleaned_data["menu_groups"])

    def delete_view(self, request, object_id, extra_context=None):
        category = self.get_object(request, object_id)
        if request.method == "GET" and category:
            names = list(category.services_only_here().values_list("name", flat=True))
            if names:
                messages.warning(
                    request,
                    f"Без категории останутся услуги ({len(names)}): {', '.join(names)}. "
                    "На сайте их не будет в меню — привяжите их к другой категории или снимите с публикации.",
                )
        return super().delete_view(request, object_id, extra_context)


class ServicePlacementFilter(admin.SimpleListFilter):
    title = "Видна на сайте"
    parameter_name = "placement"

    def lookups(self, request, model_admin):
        return [
            ("none", "Без категории"),
            ("hidden", "Нет в меню (без опубликованной категории)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "none":
            return queryset.filter(category_links__isnull=True)
        if self.value() == "hidden":
            return queryset.exclude(category_links__category__is_published=True)
        return queryset


class ServiceGapsFilter(admin.SimpleListFilter):
    title = "Чего не хватает"
    parameter_name = "gaps"

    def lookups(self, request, model_admin):
        return [("photo", "Нет фото"), ("price", "Нет цены"), ("short", "Нет краткого описания")]

    def queryset(self, request, queryset):
        if self.value() == "photo":
            return queryset.filter(photos__isnull=True)
        if self.value() == "price":
            return queryset.filter(price="")
        if self.value() == "short":
            return queryset.filter(short_description__in=["", "<p></p>"])  # пустой prose-editor сохраняет <p></p>
        return queryset


@admin.register(Service)
class ServiceAdmin(BulkPhotosAdminMixin, SiteModelAdmin):
    help_intro = (
        "Услуги показываются на страницах категорий, в которые добавлены. "
        "Фильтр «Видна на сайте» находит услуги, которых посетители не увидят, "
        "«Чего не хватает» — услуги без фото, цены или краткого описания."
    )
    help_anchor = "catalog"
    form = ServiceAdminForm
    photo_model = ServicePhoto
    photo_owner = "service"
    list_display = ["photo", "name", "price_display", "categories", "is_published", "has_page"]
    list_display_links = ["photo", "name"]
    list_editable = ["is_published"]
    list_filter = [ServicePlacementFilter, ServiceGapsFilter, "is_published", "has_page", "category_links__category"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ServicePhotoInline, ServiceCategoryInline]
    fieldsets = (
        (
            "Основное",
            {
                "classes": ["tab"],
                "fields": [
                    "name",
                    "slug",
                    ("price", "price_unit"),
                    "short_description",
                    "description",
                    ("is_published", "has_page"),
                ],
            },
        ),
        ("Загрузка фото", {"classes": ["tab"], "fields": ["bulk_photos"]}),
        SEO_FIELDSET,
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("category_links__category", "photos")

    @admin.display(description="Фото")
    def photo(self, obj):
        photos = obj.photos.all()  # prefetch_related в get_queryset
        return thumbnail_html(photos[0], "thumb") if photos else "—"

    @admin.display(description="Категории")
    def categories(self, obj):
        return ", ".join(link.category.name for link in obj.category_links.all()) or "—"

    @admin.display(description="Цена")
    def price_display(self, obj):
        return obj.price_display or "—"
