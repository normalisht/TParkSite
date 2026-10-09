from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import localize_input
from unfold.decorators import action

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.content.yandex import ReviewFetchError, fetch_review
from apps.core.admin_utils import SEO_FIELDSET, SiteModelAdmin, image_preview
from apps.core.bulk_upload import BulkUploadForm, append_images


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
class EventAdmin(SiteModelAdmin):
    list_display = ["title", "date", "show_after_date"]
    list_filter = [EventPeriodFilter, "show_after_date"]
    date_hierarchy = "date"
    search_fields = ["title"]
    fieldsets = (
        (
            "Основное",
            {
                "classes": ["tab"],
                "fields": [
                    "title",
                    "slug",
                    ("date", "end_date", "start_time"),
                    "price",
                    "description",
                    "link",
                    "image",
                    "show_after_date",
                ],
            },
        ),
        SEO_FIELDSET,
    )


class OrderedPhotoAdmin(SiteModelAdmin):
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Review)
class ReviewAdmin(SiteModelAdmin):
    # Порядок — по дате (Meta.ordering), без перетаскивания.
    list_display = ["__str__", "date", "is_published"]
    list_filter = ["is_published"]
    date_hierarchy = "date"
    fields = ["link", "date", "text", "photo", "is_published"]

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
