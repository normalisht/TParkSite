from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from unfold.admin import TabularInline
from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import SEO_FIELDSET, SiteModelAdmin, image_preview
from apps.core.bulk_upload import MultipleImageField, append_images


class CategoryPhotoInline(TabularInline):
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


class CategoryServiceInline(TabularInline):
    model = CategoryService
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["service"]
    fields = ["service", "order"]
    verbose_name_plural = "Услуги"


class ServiceCategoryInline(TabularInline):
    model = CategoryService
    extra = 0
    tab = True
    autocomplete_fields = ["category"]
    fields = ["category"]
    verbose_name_plural = "Категории"


class CategoryAdminForm(forms.ModelForm):
    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")
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


class ServiceAdminForm(forms.ModelForm):
    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")

    class Meta:
        model = Service
        fields = "__all__"


@admin.register(CategoryGroup)
class CategoryGroupAdmin(SiteModelAdmin):
    list_display = ["name", "is_published"]
    list_editable = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    filter_horizontal = ["categories"]
    fields = ["name", "categories", "is_published", "order"]


@admin.register(Category)
class CategoryAdmin(SiteModelAdmin):
    form = CategoryAdminForm
    list_display = ["name", "menu_groups_display", "services_count", "is_published"]
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
                "fields": ["name", "slug", "menu_groups", "description", "preview", "is_published", "order"],
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
            .prefetch_related("groups")
        )

    @admin.display(description="Группы меню")
    def menu_groups_display(self, obj):
        return ", ".join(group.name for group in obj.groups.all()) or "— нет в меню"

    @admin.display(description="Услуг", ordering="services_total")
    def services_count(self, obj):
        return obj.services_total

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.groups.set(form.cleaned_data["menu_groups"])
        append_images(CategoryPhoto, form.cleaned_data.get("bulk_photos") or [], category=form.instance)

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


@admin.register(Service)
class ServiceAdmin(SiteModelAdmin):
    form = ServiceAdminForm
    list_display = ["name", "price_display", "categories", "is_published", "has_page"]
    list_editable = ["is_published"]
    list_filter = [ServicePlacementFilter, "is_published", "has_page", "category_links__category"]
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
        return super().get_queryset(request).prefetch_related("category_links__category")

    @admin.display(description="Категории")
    def categories(self, obj):
        return ", ".join(link.category.name for link in obj.category_links.all()) or "—"

    @admin.display(description="Цена")
    def price_display(self, obj):
        return obj.price_display or "—"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        append_images(ServicePhoto, form.cleaned_data.get("bulk_photos") or [], service=form.instance)
