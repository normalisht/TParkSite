from django.utils.functional import SimpleLazyObject

from apps.texts.models import SiteText


def site_texts(request):
    """Все тексты сайта одним запросом — только если страница выводит хотя бы один (`{% text %}`)."""
    return {"site_texts": SimpleLazyObject(lambda: dict(SiteText.objects.values_list("key", "text")))}
