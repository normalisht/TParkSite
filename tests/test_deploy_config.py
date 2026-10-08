"""Проверки конфигурации развёртывания, которые иначе всплыли бы только на сервере."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _compose_services() -> list[str]:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    services_block = text.split("services:", 1)[1].split("\nvolumes:", 1)[0]
    return re.findall(r"^  ([\w-]+):\s*$", services_block, flags=re.MULTILINE)


def test_compose_service_names_are_unique_in_shared_proxy_network():
    # Имя сервиса — DNS-алиас во всех сетях сервиса, включая общую сеть прокси:
    # общие имена вроде web/media пересеклись бы с другими проектами.
    assert _compose_services() == ["tpark-web", "tpark-media"]


def test_env_example_is_production_safe_by_default():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert values["DEBUG"] == "0"


def test_scripts_use_renamed_service():
    for path in [ROOT / "scripts" / "backup.sh", ROOT / "README.md", ROOT / "CLAUDE.md"]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"compose (exec|run|cp)( -T| --rm)* web\b", text), path
        assert not re.search(r"(?<![\w-])web:/data", text), path
