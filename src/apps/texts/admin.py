from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_utils import SiteModelAdmin
from apps.texts.models import SiteText


@admin.register(SiteText)
class SiteTextAdmin(SimpleHistoryAdmin, SiteModelAdmin):
    fields = ["text"]
