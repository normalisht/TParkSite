from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import TrashAdminMixin
from apps.core.models import InfoPage, SiteSettings
from apps.core.trash import purge_expired

pytestmark = pytest.mark.django_db


@pytest.fixture
def service(make_image):
    category = Category.objects.create(name="Аквазона", is_published=True)
    service = Service.objects.create(name="Батут", has_page=True)
    CategoryService.objects.create(category=category, service=service, order=1)
    ServicePhoto.objects.create(service=service, image=make_image())
    return service


def test_delete_moves_to_trash(admin_client, client, service):
    url = reverse("admin:catalog_service_delete", args=[service.pk])
    assert "корзин" in admin_client.get(url).content.decode()
    response = admin_client.post(url, {"post": "yes"})
    assert response.status_code == 302
    service.refresh_from_db()
    assert service.in_trash and not service.is_published
    photo = service.photos.get()
    assert photo.image.storage.exists(photo.image.name)  # фото и файл на месте
    assert service.category_links.exists()
    listed = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list
    assert service not in listed
    assert admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).status_code == 302
    assert client.get(service.get_absolute_url()).status_code == 404


def test_restore_returns_draft(admin_client, service):
    service.move_to_trash()
    response = admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "restore": "1"})
    change_url = reverse("admin:catalog_service_change", args=[service.pk])
    assert response.status_code == 302 and response.url == change_url  # сразу в форму: проверить и опубликовать
    page = admin_client.get(change_url).content.decode()
    assert "восстановлено черновиком — проверьте и опубликуйте" in page
    service.refresh_from_db()
    assert not service.in_trash and not service.is_published
    assert service in admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list


def test_purge_returns_to_trash_list(admin_client, service):
    service.move_to_trash()
    url = reverse("admin:catalog_service_trash")
    response = admin_client.post(url, {"pk": service.pk, "purge": "1"})
    assert response.status_code == 302 and response.url == url


def test_purge_deletes_forever(admin_client, service, django_capture_on_commit_callbacks):
    service.move_to_trash()
    photo = service.photos.get()
    storage, name = photo.image.storage, photo.image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "purge": "1"})
    assert not Service.objects.filter(pk=service.pk).exists()
    assert not storage.exists(name)


def test_expired_items_purged_on_open(admin_client, service):
    service.move_to_trash()
    Service.objects.filter(pk=service.pk).update(deleted_at=timezone.now() - timedelta(days=31))
    assert admin_client.get(reverse("admin:catalog_service_trash")).status_code == 200
    assert not Service.objects.filter(pk=service.pk).exists()


def test_bulk_action_moves_to_trash(admin_client, service):
    url = reverse("admin:catalog_service_changelist")
    actions = dict(admin_client.get(url).context["action_form"].fields["action"].choices)
    assert "delete_selected" not in actions and "move_selected_to_trash" in actions
    admin_client.post(url, {"action": "move_selected_to_trash", "_selected_action": [service.pk]})
    service.refresh_from_db()
    assert service.in_trash


def test_trashed_hidden_from_autocomplete_and_inlines(admin_client, service):
    category = Category.objects.get()
    category.move_to_trash()
    response = admin_client.get(
        reverse("admin:autocomplete"),
        {"term": "Аква", "app_label": "catalog", "model_name": "categoryservice", "field_name": "category"},
    )
    assert response.json()["results"] == []
    page = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    assert "Аквазона" not in page  # не «Парк»: он есть в заголовке «Т-Парк»


def test_trashed_privacy_page_disappears_from_site(client):
    page = InfoPage.objects.create(title="Политика", body="<p>Текст</p>", is_published=True)
    site = SiteSettings.load()
    site.privacy_page = page
    site.save()
    page.move_to_trash()
    response = client.get("/")
    assert response.status_code == 200
    assert page.get_absolute_url() not in response.content.decode()


def test_every_trash_admin_has_trash_button():
    for model, model_admin in admin.site._registry.items():
        if isinstance(model_admin, TrashAdminMixin):
            assert "trash" in model_admin.actions_list, model


def _trash_button(admin_client, url_name):
    actions = admin_client.get(reverse(url_name)).context["actions_list"]
    return next(a["title"] for a in actions if a["path"].endswith("/trash/"))


def test_trash_button_and_title_show_count(admin_client, service):
    assert _trash_button(admin_client, "admin:catalog_service_changelist") == "Корзина"
    service.move_to_trash()
    assert _trash_button(admin_client, "admin:catalog_service_changelist") == "Корзина (1)"
    page = admin_client.get(reverse("admin:catalog_service_trash")).content.decode()
    assert "Корзина: Услуги (1)" in page


def test_trash_buttons_have_pointer_cursor(admin_client, service):
    confirm = admin_client.get(reverse("admin:catalog_service_delete", args=[service.pk])).content.decode()
    assert 'type="submit" class="cursor-pointer' in confirm
    service.move_to_trash()
    page = admin_client.get(reverse("admin:catalog_service_trash")).content.decode()
    assert 'name="restore" value="1" class="cursor-pointer' in page
    assert 'name="purge" value="1" class="cursor-pointer' in page
    assert "кнопкой «В корзину»" in page


def test_trashed_record_opens_read_only(admin_client, service):
    Service.objects.filter(pk=service.pk).update(description="<p>Текст <em>курсив</em></p>")
    service.refresh_from_db()
    service.move_to_trash()
    url = reverse("admin:catalog_service_trash_detail", args=[service.pk])
    assert url in admin_client.get(reverse("admin:catalog_service_trash")).content.decode()
    response = admin_client.get(url)
    assert response.status_code == 200
    page = response.content.decode()
    assert "В корзине с" in page and "удалится навсегда" in page
    assert 'name="restore"' in page and 'name="purge"' in page and reverse("admin:catalog_service_trash") in page
    assert "Батут" in page and "Аквазона" in page  # поле и вкладка «Категории»
    assert 'name="_save"' not in page and 'name="name"' not in page and 'type="file"' not in page
    assert "<em>курсив</em>" in page  # HTML-текст — как на сайте, а не исходником
    assert "В корзину" not in page  # нет кнопки удаления
    assert admin_client.post(url, {"name": "Взлом"}).status_code == 403
    service.refresh_from_db()
    assert service.name == "Батут"


def test_trash_detail_does_not_leak(admin_client, service):
    live_url = reverse("admin:catalog_service_trash_detail", args=[service.pk])
    assert admin_client.get(live_url).status_code == 404
    assert admin_client.get(reverse("admin:catalog_service_trash_detail", args=["abc"])).status_code == 404
    service.move_to_trash()
    assert admin_client.get(live_url).status_code == 200
    # Обычная форма и список после просмотра по-прежнему не видят запись в корзине.
    assert admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).status_code == 302
    listed = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list
    assert service not in listed


def test_trash_detail_requires_view_permission(client, service):
    from django.contrib.auth.models import Permission, User

    user = User.objects.create_user("editor", password="x", is_staff=True)
    client.force_login(user)
    service.move_to_trash()
    url = reverse("admin:catalog_service_trash_detail", args=[service.pk])
    assert client.get(url).status_code == 403
    user.user_permissions.add(Permission.objects.get(codename="view_service"))
    assert client.get(url).status_code == 200


def test_trash_post_rejects_live_and_bad_pk(admin_client, service):
    url = reverse("admin:catalog_service_trash")
    assert admin_client.post(url, {"pk": service.pk, "purge": "1"}).status_code == 404
    assert admin_client.post(url, {"pk": "abc", "restore": "1"}).status_code == 404
    assert Service.objects.filter(pk=service.pk, deleted_at__isnull=True).exists()


def test_restore_requires_change_permission(client, service):
    from django.contrib.auth.models import Permission, User

    user = User.objects.create_user("cleaner", password="x", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=["view_service", "delete_service"]))
    client.force_login(user)
    service.move_to_trash()
    response = client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "restore": "1"})
    assert response.status_code == 403
    service.refresh_from_db()
    assert service.in_trash


def test_purge_keeps_records_younger_than_30_days(service):
    service.move_to_trash()
    Service.objects.filter(pk=service.pk).update(deleted_at=timezone.now() - timedelta(days=29))
    assert purge_expired(Service) == 0
    assert Service.objects.filter(pk=service.pk).exists()


def test_list_columns_and_filters_ignore_trash(admin_client, service):
    from apps.catalog.models import CategoryGroup

    category = Category.objects.get()
    group = CategoryGroup.objects.create(name="Летом")
    group.categories.add(category)
    other = Service.objects.create(name="Каяк")
    CategoryService.objects.create(category=category, service=other, order=2)
    other.move_to_trash()
    group.move_to_trash()

    cl = admin_client.get(reverse("admin:catalog_category_changelist")).context["cl"]
    row = cl.result_list[0]
    assert cl.model_admin.services_count(row) == 1
    assert cl.model_admin.menu_groups_display(row) == "— нет в меню"

    category.move_to_trash()
    cl = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"]
    assert cl.model_admin.categories(cl.result_list[0]) == "—"
    url = reverse("admin:catalog_service_changelist") + "?placement=none"
    assert list(admin_client.get(url).context["cl"].result_list) == [service]


def test_trashed_category_view_shows_menu_groups(admin_client):
    from apps.catalog.models import CategoryGroup

    category = Category.objects.create(name="Аквазона")
    CategoryGroup.objects.create(name="Летом").categories.add(category)
    category.move_to_trash()
    page = admin_client.get(reverse("admin:catalog_category_trash_detail", args=[category.pk])).content.decode()
    assert "Группы меню" in page and "Летом" in page


def test_restore_from_read_only_view_opens_form(admin_client, service):
    service.move_to_trash()
    page = admin_client.get(reverse("admin:catalog_service_trash_detail", args=[service.pk])).content.decode()
    trash_url = reverse("admin:catalog_service_trash")
    assert f'action="{trash_url}"' in page  # кнопки плашки шлют POST в корзину
    assert reverse("admin:catalog_service_history", args=[service.pk]) not in page  # история не нашла бы запись
    assert "/admin/r/" not in page  # «На сайте» (admin:view_on_site) — 404 для записи в корзине
    response = admin_client.post(trash_url, {"pk": service.pk, "restore": "1"})
    assert response.url == reverse("admin:catalog_service_change", args=[service.pk])


def test_read_only_banner_form_is_outside_change_form(admin_client, service):
    # Вложенный <form> браузер выбрасывает — кнопки плашки слали бы POST в форму записи (403).
    service.move_to_trash()
    page = admin_client.get(reverse("admin:catalog_service_trash_detail", args=[service.pk])).content.decode()
    banner = page.index(f'action="{reverse("admin:catalog_service_trash")}"')
    assert banner < page.index('id="service_form"')


def test_read_only_info_page_keeps_tables(admin_client):
    # Очистка — своим набором расширений поля (у инфо-страниц есть таблицы и выноска).
    body = "<table><tbody><tr><td><p>Ячейка</p></td></tr></tbody></table><blockquote><p>Важно</p></blockquote>"
    page = InfoPage.objects.create(title="Правила", body=body)
    page.move_to_trash()
    html = admin_client.get(reverse("admin:core_infopage_trash_detail", args=[page.pk])).content.decode()
    assert "<td>" in html and "<blockquote>" in html


def test_services_only_here_ignores_trash():
    category, trashed, live = (Category.objects.create(name=n) for n in ("Парк", "Старая", "Сплавы"))
    names = {}
    for name, others in (("Зиплайн", [trashed]), ("Каяк", [live]), ("Батут", []), ("Удалённая", [])):
        names[name] = Service.objects.create(name=name)
        for other in [category, *others]:
            CategoryService.objects.create(category=other, service=names[name])
    trashed.move_to_trash()
    names["Удалённая"].move_to_trash()
    assert set(category.services_only_here().values_list("name", flat=True)) == {"Зиплайн", "Батут"}


def test_bulk_trash_of_categories_warns_about_orphans(admin_client):
    from django.contrib.messages import get_messages

    first, second, live = (Category.objects.create(name=n) for n in ("Парк", "Сплавы", "Зима"))
    for name, categories in (("Зиплайн", [first, second]), ("Каяк", [second, live]), ("Батут", [first])):
        service = Service.objects.create(name=name)
        for category in categories:
            CategoryService.objects.create(category=category, service=service)
    response = admin_client.post(
        reverse("admin:catalog_category_changelist"),
        {"action": "move_selected_to_trash", "_selected_action": [first.pk, second.pk]},
    )
    texts = [str(m) for m in get_messages(response.wsgi_request)]
    warning = next(t for t in texts if t.startswith("Без категории остались"))
    assert "Батут" in warning and "Зиплайн" in warning and "Каяк" not in warning
    assert Category.objects.filter(deleted_at__isnull=False).count() == 2


def _labels(field):
    return {str(label) for value, label in field.choices if value}


def test_trashed_choices_are_labelled(admin_client):
    from apps.catalog.models import CategoryGroup

    live, trashed = Category.objects.create(name="Сплавы"), Category.objects.create(name="Старая")
    old_group = CategoryGroup.objects.create(name="Летом")
    old_group.categories.add(live, trashed)
    CategoryGroup.objects.create(name="Зимой")
    trashed.move_to_trash()
    old_group.move_to_trash()

    form = admin_client.get(reverse("admin:catalog_category_change", args=[live.pk])).context["adminform"].form
    assert _labels(form.fields["menu_groups"]) == {"Зимой", "Летом (в корзине)"}

    group = CategoryGroup.objects.get(name="Зимой")
    form = admin_client.get(reverse("admin:catalog_categorygroup_change", args=[group.pk])).context["adminform"].form
    assert _labels(form.fields["categories"]) == {"Сплавы", "Старая (в корзине)"}


def test_service_category_filter_hides_trashed(admin_client):
    Category.objects.create(name="Сплавы")
    Category.objects.create(name="Зима")
    Category.objects.create(name="Старая").move_to_trash()
    cl = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"]
    spec = next(s for s in cl.filter_specs if getattr(s, "field_path", "") == "category_links__category")
    assert [name for _pk, name in spec.lookup_choices] == ["Сплавы", "Зима"]


def test_settings_label_trashed_choices(admin_client):
    # Выбранная страница в корзине остаётся в списке (форма настроек сохраняется), но с пометкой.
    page = InfoPage.objects.create(title="Политика", body="<p>Текст</p>")
    site = SiteSettings.load()
    site.privacy_page = page
    site.save()
    page.move_to_trash()
    Category.objects.create(name="Старая").move_to_trash()
    response = admin_client.get(reverse("admin:core_sitesettings_change", args=[site.pk]))
    form = response.context["adminform"].form
    assert "Политика (в корзине)" in _labels(form.fields["privacy_page"])
    formats = next(f for f in response.context["inline_admin_formsets"] if f.formset.prefix == "park_formats")
    assert "Старая (в корзине)" in _labels(formats.formset.form.base_fields["category"])
