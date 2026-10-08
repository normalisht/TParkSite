from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.utils import timezone
from unfold.decorators import action

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.admin_utils import SiteModelAdmin, image_preview
from apps.core.bulk_upload import BulkUploadForm, append_images


class EventPeriodFilter(admin.SimpleListFilter):
    title = "Период"
    parameter_name = "period"

    def lookups(self, request, model_admin):
        return [("upcoming", "Предстоящие"), ("past", "Прошедшие")]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == "upcoming":
            return queryset.filter(date__gte=today)
        if self.value() == "past":
            return queryset.filter(date__lt=today)
        return queryset


@admin.register(Event)
class EventAdmin(SiteModelAdmin):
    list_display = ["title", "date", "show_after_date"]
    list_filter = [EventPeriodFilter, "show_after_date"]
    date_hierarchy = "date"
    search_fields = ["title"]
    fields = ["title", "slug", "date", "description", "link", "image", "text_color", "show_after_date"]


class OrderedPhotoAdmin(SiteModelAdmin):
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Review)
class ReviewAdmin(SiteModelAdmin):
    # Порядок — по дате (Meta.ordering), без перетаскивания.
    list_display = ["preview", "author", "date", "is_published"]
    list_display_links = ["author"]
    list_filter = ["is_published"]
    date_hierarchy = "date"
    fields = ["author", "date", "text", "link", "photo", "is_published"]
    preview = image_preview("avatar")


@admin.register(Partner)
class PartnerAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "name", "link"]
    list_display_links = ["preview", "name"]
    fields = ["name", "link", "logo", "order"]
    preview = image_preview("logo_small")


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "caption"]
    list_display_links = ["preview", "caption"]
    fields = ["image", "caption", "order"]
    actions_list = ["bulk_upload"]
    preview = image_preview("thumb", size=96)

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
