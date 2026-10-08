from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.admin_utils import image_preview
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
class EventAdmin(ModelAdmin):
    list_display = ["preview", "title", "date", "show_after_date"]
    list_display_links = ["title"]
    list_filter = [EventPeriodFilter, "show_after_date"]
    date_hierarchy = "date"
    search_fields = ["title"]
    fields = ["title", "date", "description", "link", "image", "text_color", "show_after_date"]
    preview = image_preview("card")


class OrderedPhotoAdmin(ModelAdmin):
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Review)
class ReviewAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "author", "is_published"]
    list_display_links = ["author"]
    list_filter = ["is_published"]
    fields = ["author", "text", "photo", "is_published", "order"]
    preview = image_preview("avatar")


@admin.register(Partner)
class PartnerAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "name", "link"]
    list_display_links = ["preview", "name"]
    fields = ["name", "link", "logo", "order"]
    preview = image_preview("logo_small")


@admin.register(Employee)
class EmployeeAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "name", "position"]
    list_display_links = ["name"]
    fields = ["name", "position", "photo", "order"]
    preview = image_preview("portrait")


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "caption"]
    list_display_links = ["preview", "caption"]
    fields = ["image", "caption", "order"]
    actions_list = ["bulk_upload"]
    preview = image_preview("thumb", size=96)

    @action(description="Загрузить фото пачкой", url_path="bulk-upload")
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
