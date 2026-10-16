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
    assert list(settings.STATIC_ROOT.rglob("*.css.br")), "WhiteNoise не создал .br — нет пакета brotli"
    # Только копии с хешем (WHITENOISE_KEEP_ONLY_HASHED_FILES), source map не сжимаются.
    assert not (settings.STATIC_ROOT / "img/logo.png").exists()
    assert list((settings.STATIC_ROOT / "img").glob("logo.*.png"))
    assert list(settings.STATIC_ROOT.rglob("*.map"))
    assert not list(settings.STATIC_ROOT.rglob("*.map.gz")) and not list(settings.STATIC_ROOT.rglob("*.map.br"))
