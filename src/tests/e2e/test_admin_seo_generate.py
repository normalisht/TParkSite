"""Кнопка «Сгенерировать» на вкладке SEO в браузере: что уходит на сервер и что попадает в поля.

Запуск: `make e2e`.
"""

import threading

import pytest

pytest.importorskip("playwright")

from apps.catalog.models import Service
from apps.core import seo_generation
from apps.core.seo_generation import SeoDraft, SeoGenerationError

REAL_RUN_IN_BACKGROUND = seo_generation.run_in_background  # в остальных тестах conftest его отключает

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin_page(page, live_server, client, django_user_model, settings):
    settings.OPENROUTER_API_KEY = "test-key"
    client.force_login(django_user_model.objects.create_superuser("admin", "admin@example.com", "pass"))
    page.context.add_cookies(
        [{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}]
    )
    return page


@pytest.fixture
def service():
    return Service.objects.create(
        name="Фрироуп", short_description="<p>Верёвки в лесу</p>", description="<p>Подробно</p>", price="1500"
    )


@pytest.fixture
def generated(monkeypatch):
    calls = []

    def fake(page_kind, facts):
        calls.append(facts)
        return SeoDraft(title="Фрироуп в Т-Парке", description="Верёвочный маршрут в лесу.")

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", fake)
    return calls


def _open_seo_tab(page, live_server, service):
    page.goto(f"{live_server.url}/admin/catalog/service/{service.pk}/change/")
    page.get_by_role("link", name="SEO", exact=True).click()


def test_fills_empty_fields_from_unsaved_form(admin_page, live_server, service, generated):
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/{service.pk}/change/")
    page.locator("#id_name").fill("Фрироуп новый")
    page.get_by_role("link", name="SEO", exact=True).click()
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Готово: текст уже на сайте").wait_for()
    assert page.locator("#id_seo_title").input_value() == "Фрироуп в Т-Парке"
    assert page.locator("#id_seo_description").input_value() == "Верёвочный маршрут в лесу."
    assert generated[0]["Название"] == "Фрироуп новый"
    assert generated[0]["Краткое описание"] == "Верёвки в лесу"
    # Счётчик и превью реагируют на вставленный текст; пустые поля уже в базе.
    assert page.locator(".seo-preview [data-seo-preview-title]").inner_text() == "Фрироуп в Т-Парке"
    assert page.get_by_text("17 символов").is_visible()
    service.refresh_from_db()
    assert service.seo_title == "Фрироуп в Т-Парке"


def test_keeps_filled_fields_when_replacement_declined(admin_page, live_server, service, generated):
    Service.objects.filter(pk=service.pk).update(seo_title="Свой заголовок")
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Сгенерировать").click()
    assert page.locator("#id_seo_title").input_value() == "Свой заголовок"
    assert generated == []


def test_replaces_filled_fields_after_confirmation(admin_page, live_server, service, generated):
    Service.objects.filter(pk=service.pk).update(seo_title="Свой заголовок")
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Готово: описание уже на сайте, заголовок заменится после «Сохранить»").wait_for()
    assert page.locator("#id_seo_title").input_value() == "Фрироуп в Т-Парке"
    service.refresh_from_db()
    assert service.seo_title == "Свой заголовок"
    assert service.seo_description == "Верёвочный маршрут в лесу."


def test_shows_error_and_keeps_fields(admin_page, live_server, service, monkeypatch):
    def fail(page_kind, facts):
        raise SeoGenerationError("Лимит исчерпан — заполните вручную.")

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", fail)
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Лимит исчерпан — заполните вручную.").wait_for()
    assert page.locator("#id_seo_title").input_value() == ""
    assert page.get_by_role("button", name="Сгенерировать").is_enabled()


def test_save_fills_empty_fields_in_background_thread(admin_page, live_server, service, monkeypatch):
    def fake(page_kind, facts):
        return SeoDraft(title="Фрироуп в Т-Парке", description="Верёвочный маршрут в лесу.")

    monkeypatch.setattr(seo_generation, "generate_seo", fake)
    monkeypatch.setattr(seo_generation, "run_in_background", REAL_RUN_IN_BACKGROUND)
    monkeypatch.setattr(seo_generation, "_executor", None)
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/{service.pk}/change/")
    page.get_by_role("button", name="Сохранить и продолжить редактирование").click()
    page.get_by_text("Пустые SEO-поля заполнит нейросеть").wait_for()
    seo_generation._executor.shutdown(wait=True)
    service.refresh_from_db()
    assert service.seo_title == "Фрироуп в Т-Парке"
    assert service.seo_description == "Верёвочный маршрут в лесу."


def test_closing_page_does_not_lose_generated_text(admin_page, live_server, service, monkeypatch):
    started, release, saved = threading.Event(), threading.Event(), threading.Event()
    real_save = seo_generation.save_empty_seo

    def slow(page_kind, facts):
        started.set()
        release.wait(10)
        return SeoDraft(title="Фрироуп в Т-Парке", description="Верёвочный маршрут в лесу.")

    def saving(*args):
        result = real_save(*args)
        saved.set()
        return result

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", slow)
    monkeypatch.setattr(seo_generation, "save_empty_seo", saving)
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    page.close()
    release.set()
    assert saved.wait(10)
    service.refresh_from_db()
    assert service.seo_title == "Фрироуп в Т-Парке"
    assert service.seo_description == "Верёвочный маршрут в лесу."


def _warns_on_leave(page) -> bool:
    """Сработает ли предупреждение admin_unsaved.js о несохранённых изменениях."""
    return page.evaluate(
        """() => {
            const event = new Event("beforeunload", { cancelable: true });
            window.dispatchEvent(event);
            return event.defaultPrevented;
        }"""
    )


def test_no_warning_when_generated_text_is_already_saved(admin_page, live_server, service, generated):
    page = admin_page
    _open_seo_tab(page, live_server, service)
    assert not _warns_on_leave(page)
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Готово: текст уже на сайте").wait_for()
    assert not _warns_on_leave(page)


def test_warns_about_replaced_text_that_is_not_saved(admin_page, live_server, service, generated):
    Service.objects.filter(pk=service.pk).update(seo_title="Свой заголовок", seo_description="Своё описание")
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Готово: новый текст пока только в форме").wait_for()
    assert _warns_on_leave(page)


def test_warns_about_other_edits_after_generation(admin_page, live_server, service, generated):
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/{service.pk}/change/")
    page.locator("#id_name").fill("Фрироуп новый")
    page.get_by_role("link", name="SEO", exact=True).click()
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Готово: текст уже на сайте").wait_for()
    assert _warns_on_leave(page)


@pytest.fixture
def slow_generation(monkeypatch):
    """Нейросеть «думает», пока тест не вызовет `release.set()`; `started` — запрос дошёл до сервера."""
    started, release = threading.Event(), threading.Event()

    def slow(page_kind, facts):
        started.set()
        release.wait(10)
        return SeoDraft(title="Фрироуп в Т-Парке", description="Верёвочный маршрут в лесу.")

    monkeypatch.setattr("apps.core.admin_utils.generate_seo", slow)
    yield started, release
    release.set()


def _animation(locator) -> str:
    return locator.evaluate("(element) => getComputedStyle(element).animationName")


def test_shows_progress_while_generating(admin_page, live_server, service, slow_generation):
    started, release = slow_generation
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.get_by_text("Нейросеть напишет заголовок и описание по тому, что сейчас в форме").wait_for()
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    button = page.get_by_role("button", name="Пишем текст…")
    assert button.is_disabled()
    assert page.get_by_text("Можно не ждать: если закрыть страницу, текст сохранится сам").is_visible()
    assert _animation(page.locator("#id_seo_title")) != "none"
    assert _animation(page.locator("#id_seo_description")) != "none"
    release.set()
    page.get_by_text("Готово: текст уже на сайте").wait_for()
    assert page.get_by_role("button", name="Сгенерировать").is_enabled()
    assert _animation(page.locator("#id_seo_title")) == "none"


def test_new_record_asks_not_to_close_page(admin_page, live_server, slow_generation):
    started, release = slow_generation
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/add/")
    page.locator("#id_name").fill("Фрироуп")
    page.locator("#id_price").fill("1500")
    page.get_by_role("link", name="SEO", exact=True).click()
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    assert page.get_by_text("Не закрывайте страницу: запись ещё не сохранена").is_visible()
    release.set()
    page.get_by_text("Готово: текст пока только в форме").wait_for()


def test_filled_fields_ask_to_wait_for_answer(admin_page, live_server, service, slow_generation):
    started, release = slow_generation
    Service.objects.filter(pk=service.pk).update(seo_title="Свой", seo_description="Своё")
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    assert page.get_by_text("Дождитесь ответа: заполненные поля заменятся только после «Сохранить»").is_visible()
    release.set()


def test_animation_respects_reduced_motion(admin_page, live_server, service, slow_generation):
    started, release = slow_generation
    page = admin_page
    page.emulate_media(reduced_motion="reduce")
    _open_seo_tab(page, live_server, service)
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    assert _animation(page.locator("#id_seo_title")) == "none"
    release.set()


def test_explains_network_failure(admin_page, live_server, service, generated):
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.route("**/seo-generate/**", lambda route: route.abort())
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Не удалось связаться с сайтом").wait_for()
    assert page.get_by_role("button", name="Сгенерировать").is_enabled()


def test_fields_locked_while_generating(admin_page, live_server, service, slow_generation):
    started, release = slow_generation
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.get_by_role("button", name="Сгенерировать").click()
    assert started.wait(10)
    assert not page.locator("#id_seo_title").is_editable()
    assert not page.locator("#id_seo_description").is_editable()
    release.set()
    page.get_by_text("Готово: текст уже на сайте").wait_for()
    assert page.locator("#id_seo_title").is_editable()
    assert page.locator("#id_seo_description").is_editable()


def test_fields_unlocked_after_error(admin_page, live_server, service, generated):
    page = admin_page
    _open_seo_tab(page, live_server, service)
    page.route("**/seo-generate/**", lambda route: route.abort())
    page.get_by_role("button", name="Сгенерировать").click()
    page.get_by_text("Не удалось связаться с сайтом").wait_for()
    assert page.locator("#id_seo_title").is_editable()
