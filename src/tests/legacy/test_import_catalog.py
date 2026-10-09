import pytest

from apps.catalog.models import Category, CategoryGroup, CategoryService, Service

pytestmark = pytest.mark.django_db(transaction=True)


def test_categories_with_photos_and_preview(legacy):
    legacy.insert("category", id=5, name="Байдарки", description="<p>Сплавы</p>", status=1, number=3)
    legacy.insert("category", id=6, name="Скрытая", status=0, number=None)
    for name in ["10.jpg", "2.jpg", "1.jpg"]:
        legacy.image(f"category/5/{name}", size=(40 + int(name.split(".")[0]), 30))
    legacy.image("category/preview/5.jpg")
    legacy.run()
    category = Category.objects.get(id=5)
    assert (category.name, category.order, category.is_published, category.slug) == ("Байдарки", 3, True, "baidarki")
    assert category.description == "<p>Сплавы</p>"
    assert category.preview
    widths = [photo.image.width for photo in category.photos.all()]
    assert widths == [41, 42, 50]
    assert Category.objects.get(id=6).is_published is False


def test_groups_and_orphan_links(legacy):
    legacy.insert("category", id=1, name="A", status=1, number=1)
    legacy.insert("type", id=1, name="Активный отдых", number=2)
    legacy.insert("category_type", id=1, type_id=1, category_id=1)
    legacy.insert("category_type", id=2, type_id=1, category_id=99)
    report = legacy.run()
    group = CategoryGroup.objects.get()
    assert (group.name, group.order) == ("Активный отдых", 2)
    assert list(group.categories.values_list("id", flat=True)) == [1]
    assert any("#2" in w for w in report.warnings)


def test_services_and_links(legacy):
    legacy.insert("category", id=1, name="A", status=1, number=1)
    legacy.insert(
        "service", id=21, name="Сплав", price="500", time="час", status=None, next=1, short_description="<p>к</p>"
    )
    legacy.insert("service", id=22, name="Палатка", price=None, time=None, status=0, next=0)
    legacy.insert("service_category", id=1, service_id=21, category_id=1, number=2)
    legacy.insert("service_category", id=2, service_id=22, category_id=1, number=None)
    legacy.insert("service_category", id=3, service_id=21, category_id=1, number=5)
    legacy.insert("service_category", id=4, service_id=999, category_id=1, number=1)
    legacy.image("service/21/1.jpg")
    report = legacy.run()
    splav = Service.objects.get(id=21)
    assert (splav.price, splav.price_unit, splav.is_published, splav.has_page) == ("500", "час", True, True)
    assert splav.photos.count() == 1
    tent = Service.objects.get(id=22)
    assert (tent.price, tent.is_published, tent.has_page) == ("", False, False)
    links = list(CategoryService.objects.order_by("order").values_list("service_id", "order"))
    assert links == [(21, 2), (22, 10000)]
    assert any("#4" in w for w in report.warnings)


def test_detached_links_and_category_outside_menu(legacy):
    legacy.insert("category", id=1, name="  Сплавы   и\nпоходы ", status=1, number=1)
    legacy.insert("category", id=2, name="Скрытая", status=0, number=2)
    legacy.insert("type", id=1, name="Активный отдых", number=1)
    legacy.insert("category_type", id=7, type_id=None, category_id=1)
    legacy.insert("category_type", id=8, type_id=None, category_id=2)
    report = legacy.run()
    assert Category.objects.get(id=1).name == "Сплавы и походы"
    assert "Пропущены связи группа–категория без группы (2): #7, #8" in report.warnings
    outside = [w for w in report.warnings if "ни в одну группу" in w]
    assert len(outside) == 1 and "#1" in outside[0]
