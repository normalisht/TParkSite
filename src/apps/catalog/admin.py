from django import forms
from django.contrib import admin
from unfold.admin import TabularInline

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import SiteModelAdmin, image_preview
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

    class Meta:
        model = Category
        fields = "__all__"


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
    list_display = ["name", "is_published"]
    list_editable = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryPhotoInline, CategoryServiceInline]
    fieldsets = (
        ("Основное", {"fields": ["name", "slug", "description", "preview", "is_published", "order"]}),
        ("Загрузка фото", {"fields": ["bulk_photos"]}),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        append_images(CategoryPhoto, form.cleaned_data.get("bulk_photos") or [], category=form.instance)


@admin.register(Service)
class ServiceAdmin(SiteModelAdmin):
    form = ServiceAdminForm
    list_display = ["name", "price_display", "is_published", "has_page"]
    list_editable = ["is_published"]
    list_filter = ["is_published", "has_page", "category_links__category"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ServicePhotoInline, ServiceCategoryInline]
    fieldsets = (
        (
            "Основное",
            {
                "fields": [
                    "name",
                    "slug",
                    ("price", "price_unit"),
                    "short_description",
                    "description",
                    ("is_published", "has_page"),
                ]
            },
        ),
        ("Загрузка фото", {"fields": ["bulk_photos"]}),
    )

    @admin.display(description="Цена")
    def price_display(self, obj):
        return obj.price_display or "—"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        append_images(ServicePhoto, form.cleaned_data.get("bulk_photos") or [], service=form.instance)
