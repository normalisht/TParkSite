from django.core.management import call_command


def test_collectstatic_with_production_storage(settings, tmp_path):
    """Продакшен-хранилище (манифест WhiteNoise) должно собирать статику, включая vendored-библиотеки."""
    settings.STATIC_ROOT = tmp_path / "static"
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    call_command("collectstatic", interactive=False, verbosity=0)
    assert (settings.STATIC_ROOT / "staticfiles.json").exists()
