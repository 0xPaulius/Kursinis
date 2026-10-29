"""Statinio frontend'o taisyklės: be inline handler'ių ir skriptų, importai rodo į esamus failus."""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
HTML_FILES = [STATIC / "index.html", STATIC / "login.html"]
VENDORED = {"tailwind.min.js", "chart.min.js"}

INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
SCRIPT_TAG = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
IMPORT_FROM = re.compile(r"""^\s*import\s[^'"]*['"](\.{1,2}/[^'"]+)['"]""", re.MULTILINE)


def _own_modules() -> list[Path]:
    return [p for p in (STATIC / "js").rglob("*.js") if p.name not in VENDORED]


def test_html_has_no_inline_handlers():
    for page in HTML_FILES:
        assert not INLINE_HANDLER.search(page.read_text(encoding="utf-8")), page.name


def test_html_has_no_inline_scripts():
    for page in HTML_FILES:
        for attrs, body in SCRIPT_TAG.findall(page.read_text(encoding="utf-8")):
            assert "src=" in attrs and not body.strip(), f"{page.name}: inline <script>"


def test_module_imports_resolve():
    for module in _own_modules():
        for target in IMPORT_FROM.findall(module.read_text(encoding="utf-8")):
            assert (module.parent / target).resolve().is_file(), f"{module.name} -> {target}"


I18N_JS = STATIC / "js" / "i18n.js"
DATA_I18N = re.compile(r'data-i18n(?:-title|-placeholder)?="([^"]+)"')


def test_static_labels_exist_in_both_languages():
    lt, en = I18N_JS.read_text(encoding="utf-8").split("\n  en: {", 1)
    for key in set(DATA_I18N.findall((STATIC / "index.html").read_text(encoding="utf-8"))):
        key_re = re.compile(rf"^\s+{re.escape(key)}:", re.MULTILINE)
        assert key_re.search(lt) and key_re.search(en), key
