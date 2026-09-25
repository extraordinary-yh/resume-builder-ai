from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FONTS_DIR = REPO / "assets" / "fonts" / "merriweather"


@pytest.fixture(scope="session")
def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            b.close()
        return True
    except Exception:
        return False


@pytest.fixture
def browser(chromium_available):
    if not chromium_available:
        pytest.skip("Playwright Chromium is not installed (uv run playwright install chromium)")
