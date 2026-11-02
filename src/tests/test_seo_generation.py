import io
import json
from urllib.error import HTTPError, URLError

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core import seo_generation
from apps.core.models import InfoPage
from apps.core.seo_generation import SeoDraft, SeoGenerationError, generate_seo

pytestmark = pytest.mark.django_db

GENERATE_URL = "admin:catalog_service_seo_generate"
FACTS = {"Название": "Фрироуп", "Цена": "от 1500"}


class FakeResponse(io.BytesIO):
    pass


def _answer(content) -> bytes:
    return json.dumps({"choices": [{"message": {"content": content}}]}, ensure_ascii=False).encode()


@pytest.fixture
def api_key(settings):
    settings.OPENROUTER_API_KEY = "test-key"
    settings.OPENROUTER_MODEL = "test/model"


@pytest.fixture
def openrouter(monkeypatch, api_key):
    """Подменяет сеть: `openrouter.body` — ответ сервиса, `openrouter.requests` — что ему отправили."""

    class Stub:
        body = _answer('{"title": "Заголовок", "description": "Описание"}')
        requests = []

    Stub.requests = []

    def urlopen(request, timeout):
        Stub.requests.append(request)
        return FakeResponse(Stub.body)

    monkeypatch.setattr(seo_generation, "urlopen", urlopen)
    return Stub


def test_generate_seo_returns_draft(openrouter):
    assert generate_seo("Услуга", FACTS) == SeoDraft(title="Заголовок", description="Описание")


def test_generate_seo_sends_facts_and_key(openrouter):
    generate_seo("Услуга", FACTS)
    request = openrouter.requests[0]
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    payload = json.loads(request.data)
    assert payload["model"] == "test/model"
    prompt = json.dumps(payload["messages"], ensure_ascii=False)
    assert "Услуга" in prompt and "Цена: от 1500" in prompt


def test_generate_seo_without_key_makes_no_request(openrouter, settings):
    settings.OPENROUTER_API_KEY = ""
    with pytest.raises(SeoGenerationError, match="OPENROUTER_API_KEY"):
        generate_seo("Услуга", FACTS)
    assert openrouter.requests == []


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"title": "Т", "description": "О"}\n```',
        'Вот результат: {"title": "Т", "description": "О"} Готово.',
        '<think>Формат {"x": 1}?</think>{"title": "Т", "description": "О"}',
    ],
    ids=["code-fence", "text-around", "reasoning"],
)
def test_generate_seo_finds_json_in_answer(openrouter, content):
    openrouter.body = _answer(content)
    assert generate_seo("Услуга", FACTS) == SeoDraft(title="Т", description="О")


def test_generate_seo_fits_fields_and_strips_html(openrouter):
    long_title = "слово " * 30
    long_description = "текст " * 60
    openrouter.body = _answer(json.dumps({"title": f"<b>{long_title}</b>", "description": long_description}))
    draft = generate_seo("Услуга", FACTS)
    assert len(draft.title) <= 70 and "<b>" not in draft.title
    assert len(draft.description) <= 160


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        b'{"choices": []}',
        _answer(None),
        _answer("без JSON"),
        _answer('{"title": "Только заголовок"}'),
        _answer('{"title": "", "description": "О"}'),
        _answer('{"title": 1, "description": "О"}'),
    ],
    ids=["not-json", "no-choices", "empty-choices", "null", "no-object", "no-description", "empty-title", "not-string"],
)
def test_generate_seo_rejects_bad_answer(openrouter, body):
    openrouter.body = body
    with pytest.raises(SeoGenerationError):
        generate_seo("Услуга", FACTS)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b'{"error": {"code": 429, "message": "rate"}}', "Лимит"),
        (b'{"error": {"code": 502, "message": "down"}}', "недоступна"),
        (b'{"choices": [{"error": {"code": 429}, "message": {"content": "{}"}}]}', "Лимит"),
    ],
    ids=["limit", "provider-down", "error-in-choice"],
)
def test_generate_seo_reports_error_in_ok_response(openrouter, body, message):
    openrouter.body = body
    with pytest.raises(SeoGenerationError, match=message):
        generate_seo("Услуга", FACTS)


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "OPENROUTER_API_KEY"), (402, "средств"), (429, "Лимит"), (404, "недоступна"), (503, "недоступна")],
)
def test_generate_seo_explains_http_errors(monkeypatch, api_key, status, message):
    def urlopen(request, timeout):
        raise HTTPError(request.full_url, status, "error", None, io.BytesIO(b"{}"))

    monkeypatch.setattr(seo_generation, "urlopen", urlopen)
    with pytest.raises(SeoGenerationError, match=message):
        generate_seo("Услуга", FACTS)


@pytest.mark.parametrize("error", [URLError("down"), TimeoutError()], ids=["url-error", "timeout"])
def test_generate_seo_explains_network_errors(monkeypatch, api_key, error):
    def urlopen(request, timeout):
        raise error

    monkeypatch.setattr(seo_generation, "urlopen", urlopen)
    with pytest.raises(SeoGenerationError, match="не ответил"):
        generate_seo("Услуга", FACTS)


def _stub_generate(monkeypatch):
    calls = []

    def fake(page_kind, facts):
        calls.append((page_kind, facts))
        return SeoDraft(title="Заголовок", description="Описание")

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", fake)
    return calls


def test_view_generates_from_form_values(admin_client, monkeypatch):
    calls = _stub_generate(monkeypatch)
    response = admin_client.post(
        reverse(GENERATE_URL),
        {"name": "Фрироуп", "price": "от 1500", "price_unit": "", "short_description": "<p>Верёвки &amp; лес</p>"},
    )
    assert response.status_code == 200
    assert response.json() == {"title": "Заголовок", "description": "Описание", "saved": []}
    assert calls == [
        ("Услуга", {"Название": "Фрироуп", "Цена": "от 1500", "Краткое описание": "Верёвки & лес"}),
    ]


@pytest.mark.parametrize(
    "data",
    [{"name": "", "description": "<p>Текст</p>"}, {"name": "Фрироуп", "description": "<p></p>"}],
    ids=["no-name", "only-name"],
)
def test_view_requires_name_and_details(admin_client, monkeypatch, data):
    calls = _stub_generate(monkeypatch)
    response = admin_client.post(reverse(GENERATE_URL), data)
    assert response.status_code == 400
    assert "Сначала заполните" in response.json()["error"]
    assert calls == []


def test_view_shows_generation_error(admin_client, monkeypatch):
    def fail(page_kind, facts):
        raise SeoGenerationError("Лимит исчерпан")

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", fail)
    response = admin_client.post(reverse(GENERATE_URL), {"name": "Фрироуп", "description": "<p>Текст</p>"})
    assert response.status_code == 400
    assert response.json() == {"error": "Лимит исчерпан"}


def test_view_rejects_get(admin_client, monkeypatch):
    calls = _stub_generate(monkeypatch)
    assert admin_client.get(reverse(GENERATE_URL)).status_code == 405
    assert calls == []


def test_view_requires_staff(client, monkeypatch):
    calls = _stub_generate(monkeypatch)
    response = client.post(reverse(GENERATE_URL), {"name": "Фрироуп", "description": "<p>Текст</p>"})
    assert response.status_code == 302
    assert calls == []


def test_view_requires_edit_permission(client, django_user_model, monkeypatch):
    calls = _stub_generate(monkeypatch)
    client.force_login(django_user_model.objects.create_user("staff", password="pass", is_staff=True))
    response = client.post(reverse(GENERATE_URL), {"name": "Фрироуп", "description": "<p>Текст</p>"})
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize(
    ("add_url", "generate_url", "sources"),
    [
        ("admin:catalog_service_add", GENERATE_URL, "name,price,price_unit,short_description,description"),
        ("admin:catalog_category_add", "admin:catalog_category_seo_generate", "name,description"),
        (
            "admin:content_event_add",
            "admin:content_event_seo_generate",
            "title,date,end_date,start_time,venue,price,description",
        ),
        ("admin:core_infopage_add", "admin:core_infopage_seo_generate", "title,lead,body"),
    ],
    ids=["service", "category", "event", "info-page"],
)
def test_form_has_generate_hook(admin_client, settings, add_url, generate_url, sources):
    settings.OPENROUTER_API_KEY = "test-key"
    html = admin_client.get(reverse(add_url)).content.decode()
    assert f'data-seo-generate-url="{reverse(generate_url)}"' in html
    assert f'data-seo-source-fields="{sources}"' in html


def test_form_without_key_has_no_button(admin_client, settings):
    settings.OPENROUTER_API_KEY = ""
    html = admin_client.get(reverse("admin:catalog_service_add")).content.decode()
    assert "data-seo-generate-url" not in html


def test_trash_preview_has_no_button(admin_client, settings):
    settings.OPENROUTER_API_KEY = "test-key"
    category = Category.objects.create(name="Удалённая", description="<p>Текст</p>")
    category.move_to_trash()
    url = reverse("admin:catalog_category_trash_detail", args=[category.pk])
    assert "data-seo-generate-url" not in admin_client.get(url).content.decode()


@pytest.fixture
def auto_generated(monkeypatch, settings):
    """Сайт с ключом: фоновая задача выполняется сразу, сеть подменена. Список — вызовы нейросети."""
    settings.OPENROUTER_API_KEY = "test-key"
    calls = []

    def fake(page_kind, facts):
        calls.append((page_kind, facts))
        return SeoDraft(title="Сгенерированный заголовок", description="Сгенерированное описание")

    monkeypatch.setattr(seo_generation, "generate_seo", fake)
    monkeypatch.setattr(seo_generation, "run_in_background", lambda fn: fn())
    return calls


INFO_PAGE_FORM = {
    "title": "Правила",
    "slug": "",
    "lead": "",
    "layout": "text",
    "body": "<p>Текст правил</p>",
    "is_published": "on",
    "seo_title": "",
    "seo_description": "",
}


def _save_info_page(admin_client, capture, **fields):
    with capture(execute=True):
        response = admin_client.post(reverse("admin:core_infopage_add"), {**INFO_PAGE_FORM, **fields})
    assert response.status_code == 302, response.content.decode()
    return InfoPage.objects.get(title=INFO_PAGE_FORM["title"])


def test_save_fills_empty_seo(admin_client, auto_generated, django_capture_on_commit_callbacks):
    page = _save_info_page(admin_client, django_capture_on_commit_callbacks)
    assert page.seo_title == "Сгенерированный заголовок"
    assert page.seo_description == "Сгенерированное описание"
    assert auto_generated == [("Инфо-страница", {"Заголовок": "Правила", "Текст": "Текст правил"})]


def test_save_warns_that_text_goes_live_unchecked(admin_client, auto_generated, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(reverse("admin:core_infopage_add"), INFO_PAGE_FORM, follow=True)
    assert "заполнит нейросеть" in response.content.decode()


def test_save_keeps_filled_field(admin_client, auto_generated, django_capture_on_commit_callbacks):
    page = _save_info_page(admin_client, django_capture_on_commit_callbacks, seo_title="Свой заголовок")
    assert page.seo_title == "Свой заголовок"
    assert page.seo_description == "Сгенерированное описание"


def test_save_with_both_fields_makes_no_request(admin_client, auto_generated, django_capture_on_commit_callbacks):
    _save_info_page(admin_client, django_capture_on_commit_callbacks, seo_title="Свой", seo_description="Своё")
    assert auto_generated == []


def test_save_without_key_makes_no_request(admin_client, auto_generated, settings, django_capture_on_commit_callbacks):
    settings.OPENROUTER_API_KEY = ""
    page = _save_info_page(admin_client, django_capture_on_commit_callbacks)
    assert auto_generated == []
    assert page.seo_title == ""


def test_generation_waits_for_commit(admin_client, auto_generated, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        admin_client.post(reverse("admin:core_infopage_add"), INFO_PAGE_FORM)
    assert auto_generated == []  # запрос к сервису не держит транзакцию (и блокировку записи SQLite)
    assert callbacks


def test_save_does_not_overwrite_text_entered_during_generation(monkeypatch, db):
    page = InfoPage.objects.create(title="Правила", body="<p>Текст</p>")

    def typed_meanwhile(page_kind, facts):
        InfoPage.objects.filter(pk=page.pk).update(seo_title="Свой заголовок")
        return SeoDraft(title="Сгенерированный", description="Сгенерированное")

    monkeypatch.setattr(seo_generation, "generate_seo", typed_meanwhile)
    seo_generation.fill_empty_seo(InfoPage, page.pk, {"Заголовок": "Правила"})
    page.refresh_from_db()
    assert page.seo_title == "Свой заголовок"
    assert page.seo_description == "Сгенерированное"


def test_failed_generation_leaves_fields_empty(monkeypatch, db, caplog):
    page = InfoPage.objects.create(title="Правила", body="<p>Текст</p>")

    def fail(page_kind, facts):
        raise SeoGenerationError("Лимит исчерпан")

    monkeypatch.setattr(seo_generation, "generate_seo", fail)
    seo_generation.fill_empty_seo(InfoPage, page.pk, {"Заголовок": "Правила"})
    page.refresh_from_db()
    assert page.seo_title == ""
    assert "Лимит исчерпан" in caplog.text


def test_unexpected_generation_error_is_logged(monkeypatch, db, caplog):
    def fail(page_kind, facts):
        raise RuntimeError("сбой")

    monkeypatch.setattr(seo_generation, "generate_seo", fail)
    seo_generation.fill_empty_seo(InfoPage, 1, {"Заголовок": "Правила"})  # исключение терялось бы в потоке
    assert "сбой" in caplog.text


def test_page_without_details_has_no_facts():
    # Только название: модель выдумала бы содержание. Форма записи требует текст, поэтому — напрямую.
    admin = django_admin.site.get_model_admin(InfoPage)
    assert admin._seo_facts(lambda name: "Правила" if name == "title" else "") is None


def test_list_editable_save_makes_no_request(admin_client, auto_generated, django_capture_on_commit_callbacks):
    category = Category.objects.create(name="Категория", description="<p>Текст</p>", is_published=False)
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-id": str(category.pk),
        "form-0-is_published": "on",
        "form-0-order": "1",
        "_save": "Сохранить",
    }
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(reverse("admin:catalog_category_changelist"), data)
    assert response.status_code == 302
    category.refresh_from_db()
    assert category.is_published  # сохранение прошло, но генерация — только из формы записи
    assert auto_generated == []


def test_event_dates_reach_generation(admin_client, auto_generated, django_capture_on_commit_callbacks):
    form = {
        "title": "Слёт",
        "slug": "",
        "date": "01.05.2027",
        "end_date": "",
        "start_time": "",
        "venue": "",
        "price": "",
        "description": "<p>Тренинги</p>",
        "link": "",
        "seo_title": "",
        "seo_description": "",
    }
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(reverse("admin:content_event_add"), form)
    assert response.status_code == 302, response.content.decode()
    assert auto_generated == [("Мероприятие", {"Заголовок": "Слёт", "Дата": "01.05.2027", "Описание": "Тренинги"})]


BUTTON_FORM = {"name": "Фрироуп", "description": "<p>Текст</p>"}


@pytest.fixture
def service():
    return Service.objects.create(name="Фрироуп", short_description="<p>Лес</p>", description="<p>Подробно</p>")


def _press_button(client, service_id):
    return client.post(f"{reverse(GENERATE_URL)}?object={service_id}", BUTTON_FORM)


def test_button_saves_empty_fields_of_record(admin_client, monkeypatch, service):
    _stub_generate(monkeypatch)
    response = _press_button(admin_client, service.pk)
    assert response.json() == {
        "title": "Заголовок",
        "description": "Описание",
        "saved": ["seo_title", "seo_description"],
    }
    service.refresh_from_db()
    assert service.seo_title == "Заголовок"
    assert service.seo_description == "Описание"


def test_button_does_not_replace_filled_field_in_database(admin_client, monkeypatch, service):
    _stub_generate(monkeypatch)
    Service.objects.filter(pk=service.pk).update(seo_title="Свой заголовок")
    response = _press_button(admin_client, service.pk)
    # В форму — оба новых текста, в базу — только пустое поле.
    assert response.json() == {"title": "Заголовок", "description": "Описание", "saved": ["seo_description"]}
    service.refresh_from_db()
    assert service.seo_title == "Свой заголовок"
    assert service.seo_description == "Описание"


def test_button_with_filled_fields_saves_nothing(admin_client, monkeypatch, service):
    _stub_generate(monkeypatch)
    Service.objects.filter(pk=service.pk).update(seo_title="Свой", seo_description="Своё")
    assert _press_button(admin_client, service.pk).json()["saved"] == []
    service.refresh_from_db()
    assert (service.seo_title, service.seo_description) == ("Свой", "Своё")


def test_saved_seo_updates_sitemap_date(admin_client, monkeypatch, service):
    _stub_generate(monkeypatch)
    before = service.updated_at
    _press_button(admin_client, service.pk)
    service.refresh_from_db()
    assert service.updated_at > before


@pytest.mark.parametrize("bad_id", ["abc", "999999"])
def test_button_with_unknown_record_saves_nothing(admin_client, monkeypatch, service, bad_id):
    _stub_generate(monkeypatch)
    response = _press_button(admin_client, bad_id)
    assert response.status_code == 200
    assert response.json()["saved"] == []
    service.refresh_from_db()
    assert service.seo_title == ""


def test_button_does_not_save_to_trashed_record(admin_client, monkeypatch, service):
    _stub_generate(monkeypatch)
    service.move_to_trash()
    assert _press_button(admin_client, service.pk).json()["saved"] == []
    service.refresh_from_db()
    assert service.seo_title == ""


def test_button_needs_change_permission_to_save(client, django_user_model, monkeypatch, service):
    _stub_generate(monkeypatch)
    user = django_user_model.objects.create_user("adder", password="pass", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="add_service"))
    client.force_login(user)
    response = _press_button(client, service.pk)
    assert response.status_code == 200
    assert response.json()["saved"] == []  # черновик для новой записи можно, чужую запись менять нельзя
    service.refresh_from_db()
    assert service.seo_title == ""


def test_change_form_tells_button_which_record(admin_client, settings, service):
    settings.OPENROUTER_API_KEY = "test-key"
    html = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    assert f'data-seo-generate-url="{reverse(GENERATE_URL)}?object={service.pk}"' in html
