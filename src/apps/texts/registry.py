"""Реестр текстов сайта: какие тексты есть, где они на сайте и что выводится по умолчанию.

Источник правды о наборе текстов: модель `SiteText` хранит только текущие значения, а ключи, подписи
и тексты по умолчанию — здесь. Работает и с историческими моделями миграций (`sync_texts`).
"""

from django.db import models


class Page(models.TextChoices):
    HOME = "home", "Главная"
    SERVICE = "service", "Услуга"
    CATEGORY = "category", "Категория"
    EVENTS = "events", "Мероприятия"
    EVENT = "event", "Мероприятие"
    ABOUT = "about", "О нас"
    CONTACTS = "contacts", "Контакты"
    REVIEWS = "reviews", "Отзывы"
    GALLERY = "gallery", "Галерея"
    ERROR404 = "error404", "Страница 404"
    COMMON = "common", "Общее"
