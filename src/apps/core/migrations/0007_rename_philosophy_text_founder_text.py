from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0006_seo_content")]

    operations = [migrations.RenameField("sitesettings", "philosophy_text", "founder_text")]
