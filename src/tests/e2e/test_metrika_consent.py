import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

from apps.core.models import CookieConsentEvent, InfoPage, SiteSettings

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

METRIKA_STUB = "window.metrikaCalls = []; window.ym = (...args) => window.metrikaCalls.push(args);"


@pytest.fixture
def metrika_site():
    site = SiteSettings.load()
    site.yandex_metrika_id = "12345"
    site.privacy_page = InfoPage.objects.create(title="Политика конфиденциальности")
    site.save()
    return site


def test_metrika_requires_consent_and_stops_after_refusal(live_server, browser, metrika_site):
    with browser.new_context(viewport={"width": 320, "height": 700}, is_mobile=True, has_touch=True) as context:
        requests = []

        def metrika(route):
            requests.append(route.request.url)
            route.fulfill(content_type="text/javascript", body=METRIKA_STUB)

        context.route("https://mc.yandex.ru/**", metrika)
        context.add_init_script("localStorage.setItem('cookie-ok', '1')")
        page = context.new_page()
        page.goto(live_server.url)
        notice = page.get_by_role("region", name="Настройки cookie")
        expect(notice).to_be_visible()
        assert not requests
        page.get_by_role("button", name="Отклонить").click()
        page.reload()
        expect(notice).to_be_hidden()
        assert not requests

        page.get_by_role("button", name="Настройки cookie").click()
        page.get_by_role("button", name="Принять").click()
        page.wait_for_function("window.metrikaCalls?.some((call) => call[1] === 'init')")
        assert requests == ["https://mc.yandex.ru/metrika/tag.js"]
        page.reload()
        page.wait_for_function("window.metrikaCalls?.some((call) => call[1] === 'init')")
        expect(notice).to_be_hidden()
        page.evaluate(
            """() => {
                document.cookie = '_ym_uid=old; Path=/';
                document.cookie = 'site-preference=keep; Path=/';
                localStorage.setItem('_ym_retryReqs', 'old');
            }"""
        )
        page.get_by_role("button", name="Настройки cookie").click()
        page.get_by_role("button", name="Отклонить").click()
        assert page.evaluate("window.metrikaCalls.map((call) => call[1])") == ["init", "destruct"]
        assert page.evaluate("localStorage.getItem('_ym_retryReqs')") is None
        cookies = {cookie["name"] for cookie in context.cookies()}
        assert "_ym_uid" not in cookies
        assert "site-preference" in cookies
        page.reload()
        expect(notice).to_be_hidden()
        assert len(requests) == 2


def test_new_metrika_consent_version_asks_only_previously_agreed_visitors(live_server, browser, metrika_site):
    with browser.new_context() as opted_in, browser.new_context() as opted_out:
        for context, decision in [(opted_in, "Принять"), (opted_out, "Отклонить")]:
            context.route("https://mc.yandex.ru/**", lambda route: route.abort())
            page = context.new_page()
            page.goto(live_server.url)
            page.get_by_role("button", name=decision).click()
            expect(page.get_by_role("region", name="Настройки cookie")).to_be_hidden()
        metrika_site.metrika_consent_version = 2
        metrika_site.save(update_fields=["metrika_consent_version"])

        allowed_page = opted_in.pages[0]
        allowed_page.reload()
        expect(allowed_page.get_by_role("region", name="Настройки cookie")).to_be_visible()
        assert allowed_page.locator('script[src*="mc.yandex.ru"]').count() == 0
        refused_page = opted_out.pages[0]
        refused_page.reload()
        expect(refused_page.get_by_role("region", name="Настройки cookie")).to_be_hidden()
        assert refused_page.locator('script[src*="mc.yandex.ru"]').count() == 0


def test_metrika_does_not_start_when_consent_is_revoked_during_tag_load(live_server, browser, metrika_site):
    with browser.new_context() as context:
        pending = []
        context.route("https://mc.yandex.ru/**", lambda route: pending.append(route))
        page = context.new_page()
        page.goto(live_server.url)
        with page.expect_request("https://mc.yandex.ru/metrika/tag.js"):
            page.get_by_role("button", name="Принять").click()
        page.get_by_role("button", name="Настройки cookie").click()
        page.get_by_role("button", name="Отклонить").click()
        page.locator('script[src*="mc.yandex.ru"]').evaluate(
            """(tag) => tag.addEventListener("load", () => { window.metrikaTagLoaded = true; })"""
        )
        pending[0].fulfill(content_type="text/javascript", body=METRIKA_STUB)
        page.wait_for_function("window.metrikaTagLoaded")
        assert page.evaluate("window.metrikaCalls") == []


def test_failed_consent_recording_keeps_counter_off(live_server, browser, metrika_site):
    with browser.new_context() as context:
        context.route("https://mc.yandex.ru/**", lambda route: route.abort())
        context.route(
            "**/cookie-consent/",
            lambda route: route.fulfill(status=503) if route.request.method == "POST" else route.continue_(),
        )
        page = context.new_page()
        page.goto(live_server.url)
        page.get_by_role("button", name="Принять").click()
        expect(page.get_by_role("alert")).to_contain_text("Не удалось сохранить согласие")
        assert page.locator('script[src*="mc.yandex.ru"]').count() == 0
        assert not CookieConsentEvent.objects.exists()


@pytest.mark.parametrize("disable_analytics", [False, True])
def test_offline_revocation_retries_on_next_visit(live_server, browser, metrika_site, disable_analytics):
    with browser.new_context() as context:
        context.route(
            "https://mc.yandex.ru/**", lambda route: route.fulfill(content_type="text/javascript", body=METRIKA_STUB)
        )
        page = context.new_page()
        page.goto(live_server.url)
        page.get_by_role("button", name="Принять").click()
        page.wait_for_function("window.metrikaCalls?.some((call) => call[1] === 'init')")

        def offline(route):
            if route.request.method == "POST":
                route.fulfill(status=503)
            else:
                route.continue_()

        context.route("**/cookie-consent/", offline)
        page.get_by_role("button", name="Настройки cookie").click()
        with page.expect_response(lambda response: response.status == 503 and "/cookie-consent/" in response.url):
            page.get_by_role("button", name="Отклонить").click()
        assert page.evaluate("window.metrikaCalls.map((call) => call[1])") == ["init", "destruct"]
        assert CookieConsentEvent.objects.count() == 1

        context.unroute("**/cookie-consent/", offline)
        if disable_analytics:
            metrika_site.yandex_metrika_id = ""
            metrika_site.save(update_fields=["yandex_metrika_id"])
        with page.expect_response(lambda response: response.request.method == "POST" and response.status == 200):
            page.reload()
        assert page.locator('script[src*="mc.yandex.ru"]').count() == 0
        assert CookieConsentEvent.objects.filter(action="revoke").count() == 1


def test_can_withdraw_after_server_saved_consent_but_response_was_lost(live_server, browser, metrika_site):
    with browser.new_context() as context:
        context.route("https://mc.yandex.ru/**", lambda route: route.abort())

        def lose_response(route):
            if route.request.method == "POST":
                assert route.fetch().status == 200
                route.abort()
            else:
                route.continue_()

        context.route("**/cookie-consent/", lose_response)
        page = context.new_page()
        page.goto(live_server.url)
        page.get_by_role("button", name="Принять").click()
        expect(page.get_by_role("alert")).to_contain_text("Не удалось сохранить согласие")
        context.clear_cookies(name="metrika-consent")
        context.unroute("**/cookie-consent/", lose_response)

        page.reload()
        with page.expect_response(lambda response: response.request.method == "POST" and response.status == 200):
            page.get_by_role("button", name="Отклонить").click()
        assert page.locator('script[src*="mc.yandex.ru"]').count() == 0
        assert list(CookieConsentEvent.objects.order_by("pk").values_list("action", flat=True)) == ["allow", "revoke"]


def test_can_withdraw_saved_consent_after_analytics_disabled(live_server, browser, metrika_site):
    with browser.new_context() as visitor, browser.new_context() as newcomer:
        visitor.route("https://mc.yandex.ru/**", lambda route: route.abort())
        page = visitor.new_page()
        page.goto(live_server.url)
        notice = page.get_by_role("region", name="Настройки cookie")
        notice.get_by_role("button", name="Принять", exact=True).click()
        expect(notice).to_be_hidden()
        page.evaluate("localStorage.clear()")
        metrika_site.yandex_metrika_id = ""
        metrika_site.save(update_fields=["yandex_metrika_id"])

        first_visit = newcomer.new_page()
        with first_visit.expect_response(lambda response: response.url.endswith("/cookie-consent/?check=withdrawal")):
            first_visit.goto(live_server.url)
        expect(first_visit.get_by_role("link", name="Политика конфиденциальности")).to_be_visible()
        expect(first_visit.get_by_role("button", name="Настройки cookie")).to_be_hidden()
        expect(first_visit.get_by_role("region", name="Настройки cookie")).to_be_hidden()

        page.reload()
        settings_button = page.get_by_role("button", name="Настройки cookie")
        expect(settings_button).to_be_visible()
        expect(notice).to_be_hidden()
        settings_button.click()
        expect(notice.get_by_role("button", name="Принять", exact=True)).to_have_count(0)
        notice.get_by_role("button", name="Отозвать согласие").click()
        expect(settings_button).to_be_hidden()
        expect(notice).to_be_hidden()
        assert page.locator('script[src*="mc.yandex.ru"]').count() == 0
        assert CookieConsentEvent.objects.filter(action="revoke").count() == 1
