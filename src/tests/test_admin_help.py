import re

import pytest
from django.urls import reverse

from apps.core.admin_help import HELP_ANCHORS, HELP_SECTIONS

pytestmark = pytest.mark.django_db


def _help_html(client) -> str:
    response = client.get(reverse("admin_help"))
    assert response.status_code == 200
    return response.content.decode()


def test_help_requires_staff(client, django_user_model):
    url = reverse("admin_help")
    login = reverse("admin:login")
    assert client.get(url).url.startswith(login)
    django_user_model.objects.create_user("guest", password="p")
    client.login(username="guest", password="p")
    assert client.get(url).url.startswith(login)


def test_help_open_for_plain_staff(client, django_user_model):
    django_user_model.objects.create_user("staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    assert "Как устроен сайт" in _help_html(client)


def test_sidebar_links_to_help(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    assert f'href="{reverse("admin_help")}"' in html


def test_toc_points_to_existing_sections(admin_client):
    html = _help_html(admin_client)
    ids = set(re.findall(r'<section id="([\w-]+)"', html))
    assert ids == HELP_ANCHORS
    toc = re.findall(r'href="#([\w-]+)"', html)
    assert set(toc) - {"toc"} == HELP_ANCHORS
    assert [s.anchor for s in HELP_SECTIONS] == list(dict.fromkeys(a for a in toc if a != "toc"))


def test_help_admin_links_open(admin_client):
    html = _help_html(admin_client)
    links = sorted(set(re.findall(r'href="(/admin/[^"#]*)', html)) - {reverse("admin_help")})
    assert links
    for link in links:
        response = admin_client.get(link.replace("&amp;", "&"), follow=True)
        assert response.status_code == 200, link
