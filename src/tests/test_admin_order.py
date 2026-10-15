import pytest
from django.contrib import admin
from django.urls import reverse

from apps.catalog.admin import CategoryPhotoInline, CategoryServiceInline, ServiceCategoryInline
from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service
from apps.content.models import Partner
from apps.core.models import next_order

pytestmark = pytest.mark.django_db


def test_next_order():
    assert next_order(CategoryGroup) == 1
    CategoryGroup.objects.create(name="А", order=7)
    assert next_order(CategoryGroup) == 8


def test_service_added_from_its_form_goes_last_in_category(rf, admin_user):
    category = Category.objects.create(name="К")
    for i, name in enumerate(["А", "Б"], start=1):
        CategoryService.objects.create(category=category, service=Service.objects.create(name=name), order=i)
    service = Service.objects.create(name="Новая")
    request = rf.get("/")
    request.user = admin_user
    FormSet = ServiceCategoryInline(Service, admin.site).get_formset(request, service)
    data = {
        "category_links-TOTAL_FORMS": "1",
        "category_links-INITIAL_FORMS": "0",
        "category_links-0-category": str(category.pk),
    }
    formset = FormSet(data=data, instance=service, prefix="category_links")
    assert formset.is_valid(), formset.errors
    formset.save()
    assert CategoryService.objects.get(service=service).order == 3


def test_new_inline_rows_start_after_last(rf, admin_user, make_image):
    category = Category.objects.create(name="К")
    CategoryPhoto.objects.create(category=category, image=make_image(), order=5)
    CategoryService.objects.create(category=category, service=Service.objects.create(name="А"), order=2)
    request = rf.get("/")
    request.user = admin_user
    photos = CategoryPhotoInline(Category, admin.site).get_formset(request, category)
    links = CategoryServiceInline(Category, admin.site).get_formset(request, category)
    assert photos.form.base_fields["order"].initial == 6
    assert links.form.base_fields["order"].initial == 3


def test_posted_order_wins(rf, admin_user):
    """Новую строку перетащили первой — order=0 из формы сохраняется."""
    category = Category.objects.create(name="К")
    CategoryService.objects.create(category=category, service=Service.objects.create(name="А"), order=1)
    new = Service.objects.create(name="Б")
    request = rf.get("/")
    request.user = admin_user
    FormSet = CategoryServiceInline(Category, admin.site).get_formset(request, category)
    link = CategoryService.objects.get()
    data = {
        "service_links-TOTAL_FORMS": "2",
        "service_links-INITIAL_FORMS": "1",
        "service_links-0-id": str(link.pk),
        "service_links-0-category": str(category.pk),
        "service_links-0-service": str(link.service_id),
        "service_links-0-order": "1",
        "service_links-1-category": str(category.pk),
        "service_links-1-service": str(new.pk),
        "service_links-1-order": "0",
    }
    formset = FormSet(data=data, instance=category, prefix="service_links")
    assert formset.is_valid(), formset.errors
    formset.save()
    assert CategoryService.objects.get(service=new).order == 0


def test_partner_added_in_admin_goes_last(admin_client, make_image):
    Partner.objects.create(name="Старый", logo=make_image(), order=4)
    response = admin_client.post(
        reverse("admin:content_partner_add"), {"name": "Новый", "link": "", "logo": make_image("new.jpg")}
    )
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert Partner.objects.get(name="Новый").order == 5


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:catalog_categorygroup_add",
        "admin:catalog_category_add",
        "admin:content_partner_add",
        "admin:content_galleryphoto_add",
        "admin:core_announcement_add",
        "admin:core_infopage_add",
    ],
)
def test_order_field_hidden_in_forms(admin_client, url_name):
    form = admin_client.get(reverse(url_name)).context["adminform"].form
    assert "order" not in form.fields
