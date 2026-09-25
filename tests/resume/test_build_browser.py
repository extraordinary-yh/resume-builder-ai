import json

import pytest

from resumebuilder.data import Bullet, resolve
from resumebuilder.render import Renderer, build
from tests.resume.conftest import FONTS_DIR
from tests.resume.test_data import BULLETS, MASTER

pytestmark = pytest.mark.browser

LONG = ("Built a crash-logging web application used by roughly one thousand engineers across three sites, "
        "cutting the time to identify a known crash from several weeks to about one hour through a searchable index.")


def test_build_writes_pdf_html_layout_and_measures(browser, tmp_path):
    bullets = {**BULLETS, "a9": Bullet(id="a9", role="acme", text=LONG, tags=["backend"], approved=True)}
    r = resolve(MASTER, bullets, {"include": ["a9"]})
    res = build(r, tmp_path, FONTS_DIR)
    assert res.pdf_path.exists() and res.html_path.exists() and res.layout_path.exists()
    assert res.report.pages == 1 and res.report.fits and 0 < res.report.fill_pct < 60
    assert all(f.startswith("Merriweather") for f in res.report.fonts), res.report.fonts
    by_id = {b.id: b for b in res.report.bullets}
    assert by_id["a2"].lines == 1 and by_id["a2"].over_by_words == 0
    assert by_id["a9"].lines >= 2 and by_id["a9"].over_by_words >= 1 and by_id["a9"].words > 20
    saved = json.loads(res.layout_path.read_text())
    assert saved["pages"] == 1 and saved["bullets"][0]["id"] == "a1"


def test_renderer_reuses_one_browser_for_many_measurements(browser, tmp_path):
    with Renderer(FONTS_DIR) as ren:
        a = ren.measure(resolve(MASTER, BULLETS), tmp_path / "a")
        b = ren.measure(resolve(MASTER, BULLETS, {"layout": {"font_pt": 10}}), tmp_path / "b")
    assert b.content_height_in > a.content_height_in and a.pages == b.pages == 1
