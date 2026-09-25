from resumebuilder.data import LayoutParams
from resumebuilder.measure import MEASURE_JS, LayoutReport, layout_report, line_height_in

RAW = {"content_height_px": 96 * 10.5,
       "bullets": [{"id": "a1", "section": "acme", "lines": 2, "words": 17, "over_by_words": 3, "last_line_fill_pct": 18},
                   {"id": "a2", "section": "acme", "lines": 1, "words": 9, "over_by_words": 0, "last_line_fill_pct": 70}],
       "sections": [{"name": "Experience", "height_px": 96 * 6.2}]}


def test_layout_report_derives_overflow_fill_and_orphans():
    p = LayoutParams(page_width_in=8.5, page_height_in=11)      # 0.5in margins -> 10in available
    r = layout_report(RAW, p, pages=2, fonts=["Merriweather-Light"])
    assert r.available_height_in == 10.0 and r.content_height_in == 10.5
    assert round(r.overflow_in, 2) == 0.5 and r.fill_pct == 105 and r.pages == 2 and not r.fits and r.overflows
    assert r.bullets[0].over_by_words == 3 and r.sections[0]["height_in"] == 6.2
    assert [b.id for b in r.orphans] == ["a1"]                                   # 2 lines, last line 18% wide
    short = layout_report({**RAW, "content_height_px": 96 * 9.7}, p, pages=1, fonts=[])
    assert not short.overflows and not short.fits and short.to_dict()["orphans"] == ["a1"]   # orphan still blocks
    ok_raw = {**RAW, "content_height_px": 96 * 9.7, "bullets": [{**RAW["bullets"][0], "last_line_fill_pct": 55}, RAW["bullets"][1]]}
    ok = layout_report(ok_raw, p, pages=1, fonts=[])
    assert ok.fits and ok.fill_pct == 97 and ok.overflow_in < 0 and ok.orphans == []
    strict = layout_report(ok_raw, p.replace(orphan_min_fill_pct=60), pages=1, fonts=[])
    assert not strict.fits


def test_report_round_trips_through_dict():
    r = layout_report(RAW, LayoutParams(), pages=2, fonts=["X"])
    again = LayoutReport.from_dict(r.to_dict())
    assert again == r and again.params == LayoutParams() and again.orphan_min_fill_pct == 50


def test_line_height_in():
    assert round(line_height_in(LayoutParams(font_pt=9, line_height=1.571)), 4) == round(9 * 1.571 / 72, 4)


def test_measure_js_is_a_function_expression():
    assert MEASURE_JS.strip().startswith("() =>") and "content_height_px" in MEASURE_JS and "over_by_words" in MEASURE_JS
