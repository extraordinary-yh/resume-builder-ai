import re

import pytest

from resumebuilder.data import resolve
from resumebuilder.render import bold_html, font_faces, render_html
from tests.resume.conftest import FONTS_DIR
from tests.resume.test_data import BULLETS, MASTER


def test_bold_html_escapes_then_bolds():
    assert str(bold_html("Drove **10K** <signups>")) == "Drove <b>10K</b> &lt;signups&gt;"


def test_font_faces_embeds_three_weights_plus_variable():
    css = font_faces(FONTS_DIR)
    assert css.count("@font-face") == 4 and "font-weight: 300;" in css and "data:font/ttf;base64," in css
    assert '"Merriweather VF"; font-style: normal; font-weight: 300 900;' in css      # variable font for tech terms


def test_font_faces_names_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="Merriweather-Light.ttf"):
        font_faces(tmp_path)


def test_render_html_structure_and_layout_knobs():
    r = resolve(MASTER, BULLETS, {"layout": {"page_height_in": 11.5, "margin_in": 0.45, "line_height": 1.25}})
    html = render_html(r, FONTS_DIR)
    assert "@page { size: 9.25in 11.5in; margin: 0.45in; }" in html
    assert "--font: 9.0pt" in html and "--lh: 1.25" in html and ".page { width: 8.35in; }" in html
    assert "--heading: 10.5pt" in html and "--role: 9.5pt" in html and "--line-pt: 11.25pt" in html
    assert '<li data-id="a1" data-section="acme">Drove <b>10K</b> signups.</li>' in html
    assert "Alex Morgan" in html and "alex@example.com" in html and "111-222-3333" in html
    assert "<h2>EXPERIENCE</h2>" in html and "<h2>Projects</h2>" in html and "<h2>EDUCATION</h2>" in html and "SKILLS &amp; ACTIVITIES" in html
    assert "AI product engineer." not in html                 # summary hidden by default
    assert "Python, TypeScript" in html and "Example University, 2024" in html
    assert not re.search(r'<(script|link)[^>]+(src|href)="https?://', html)
    assert 'src: url("data:font/ttf;base64,' in html                 # font CSS must not be HTML-escaped
    shown = render_html(resolve(MASTER, BULLETS, {"show_summary": True}), FONTS_DIR)
    assert "AI product engineer." in shown


def test_contact_line_icons_and_links(tmp_path):
    (tmp_path / "pin.png").write_bytes(b"\x89PNG fake")
    master = {**MASTER, "basics": {"name": "M", "location": "SF", "location_icon": "pin.png", "email": "alex@example.com",
                                   "email_icon": "missing.png", "phone": "", "links": [
                                       {"label": "alex-example", "url": "https://alex-example.medium.com/", "icon": "medium.png", "prefix": "@"}]}}
    html = render_html(resolve(master, BULLETS), FONTS_DIR, icons_dir=tmp_path)
    assert '<img class="ico" src="data:image/png;base64,' in html and html.count('<img class="ico"') == 1   # missing icons → text
    assert '@<a href="https://alex-example.medium.com/">alex-example</a>' in html and "alex@example.com" in html


def test_bold_filter_renders_links_and_tech_terms():
    assert str(bold_html("see [technical writing](https://m) and **10K**")) == 'see <a href="https://m">technical writing</a> and <b>10K</b>'
    assert str(bold_html("on *Temporal* and a *NestJS* API: **~25K** tracks")) == 'on <span class="tech">Temporal</span> and a <span class="tech">NestJS</span> API: <b>~25K</b> tracks'
    assert str(bold_html("*Node.js*/*React* app")) == '<span class="tech">Node.js</span>/<span class="tech">React</span> app'
    assert str(bold_html("35+ endpoints at **1,000+** users")) == '35+ endpoints at <b>1,000+</b> users'
