from pathlib import Path

from actas.web import texts

WEB = Path(texts.__file__).resolve().parent


def test_home_title():
    assert texts.HOME_TITLE == "¿A dónde va el dinero de Yecla?"


def test_shared_texts_live_only_in_texts_module():
    shared = [texts.SITE_NAME, texts.HOME_TITLE, texts.EMAIL, texts.UNOFFICIAL, texts.INFO_TITLE]
    for f in WEB.rglob("*.py"):
        if f.name == "texts.py":
            continue
        src = f.read_text(encoding="utf-8")
        for s in shared:
            assert s not in src, f"{f.name} repeats «{s}»: use actas.web.texts"
