# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
# uv run video/preview.py draws src/actas/web/static/vista-previa.png, the image shown when a link to the site is
# shared. Needs Google Chrome.

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
STAGE = Path(__file__).resolve().parent / "preview.html"
OUT = ROOT / "src/actas/web/static/vista-previa.png"
TOWN = json.loads((ROOT / "analisis/municipio.json").read_text(encoding="utf-8"))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        page.goto(STAGE.as_uri())
        page.evaluate("b => setBrand(b[0], b[1])", [TOWN["web"]["nombre"], TOWN["municipio"]])
        page.screenshot(path=OUT)
        browser.close()
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
