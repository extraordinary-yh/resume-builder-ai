from resumebuilder.data import LayoutParams, resolve
from dataclasses import replace as dc_replace

from resumebuilder.fit import Bounds, cut_candidates, heights, lines_over, rank_cuts, run_fit, widths
from resumebuilder.measure import BulletMeasure, LayoutReport
from tests.resume.test_data import BULLETS, MASTER

BOUNDS = Bounds.from_layout(MASTER["layout"])   # 9.25 x 12.28, width up to 9.75, height up to 13.0


def fake_measure(height_for, fill_for=None):
    """height_for(params) -> content height in inches; fill_for(params) -> last-line fill of bullet a1 (2 lines)."""
    def measure(resolved):
        p = resolved.layout
        avail = p.page_height_in - 2 * p.margin_in
        h = height_for(p)
        fill = fill_for(p) if fill_for else 80
        return LayoutReport(params=p, content_height_in=h, available_height_in=avail, overflow_in=round(h - avail, 3),
                            fill_pct=round(100 * h / avail), pages=1 if h <= avail else 2, fonts=[],
                            bullets=[BulletMeasure("a1", "acme", 2, 17, 1, fill), BulletMeasure("a2", "acme", 2, 20, 3, 70),
                                     BulletMeasure("p1", "proj", 1, 5, 0, 60)],
                            orphan_min_fill_pct=p.orphan_min_fill_pct)
    return measure


def test_bounds_and_candidate_lists():
    assert BOUNDS.start == LayoutParams(page_width_in=9.25, page_height_in=12.28, heading_pt=10.5, role_pt=9.5, line_height=1.571)
    assert widths(BOUNDS) == [9.25, 9.5, 9.75] and heights(BOUNDS) == [12.28, 12.53, 12.78]
    tight = Bounds.from_layout({"page": {"width_in": 8.5, "height_in": 11}})
    assert widths(tight) == [8.5] and heights(tight) == [11.0]


def test_run_fit_trims_height_when_asked_but_never_below_the_floor():
    layout = {**MASTER["layout"], "page": {**MASTER["layout"]["page"], "trim_height": True, "min_height_in": 11.0}}
    b = Bounds.from_layout(layout)
    assert b.trim_height and b.min_height_in == 11.0 and b.trim_pad_in == 0.05
    res = run_fit(resolve(MASTER, BULLETS), b, fake_measure(lambda p: 10.6))      # 10.6 + 1.0 margins + 0.05 = 11.65
    assert res.fitted and res.rung == 1 and res.params.page_height_in == 11.65 and "trimmed" in res.description
    floor = run_fit(resolve(MASTER, BULLETS), b, fake_measure(lambda p: 5.0))
    assert floor.params.page_height_in == 11.0
    untouched = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 10.6))
    assert untouched.params.page_height_in == 12.28                              # trim is opt-in


def test_run_fit_as_is_when_nothing_is_wrong():
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 10.0))
    assert res.fitted and res.rung == 1 and res.params == BOUNDS.start and res.cuts == []


def test_run_fit_widens_for_orphans_then_stops():
    # a1's last line is 20% wide at 9.25in and joins the first line at 9.5in
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 10.0, lambda p: 20 if p.page_width_in < 9.5 else 90))
    assert res.fitted and res.rung == 2 and res.params.page_width_in == 9.5 and res.params.page_height_in == 12.28


def test_run_fit_refuses_to_extend_without_permission_and_lists_cuts():
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 11.6), target_tags={"growth"}, bank=BULLETS)
    assert not res.fitted and res.rung == 3 and res.lines_over == 2 and res.extend_to_in == 12.65      # 11.6 + 1.0 + 0.05
    assert "cut a line or allow extending to 12.65in" in res.description
    ids = [(c["id"], c["action"]) for c in res.cuts]
    assert ids[0] == ("a1", "use the approved short variant")                     # cheapest: keeps the bullet, saves a line
    assert ("a2", "drop the bullet") in ids and ("p1", "drop the bullet") in ids
    assert lines_over(res.report) == 2
    allowed = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 11.6), allow_extend=True)
    assert allowed.fitted and allowed.rung == 3
    via_bounds = run_fit(resolve(MASTER, BULLETS), dc_replace(BOUNDS, allow_extend=True), fake_measure(lambda p: 11.6))
    assert via_bounds.fitted


def test_run_fit_adds_height_for_overflow_never_shrinks_spacing():
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 11.6), allow_extend=True)     # fits once available >= 11.6 -> 12.78in page
    assert res.fitted and res.rung == 3 and res.params.page_height_in == 12.78 and res.params.page_width_in == 9.25
    assert res.params.line_height == BOUNDS.start.line_height and res.params.margin_in == BOUNDS.start.margin_in


def test_run_fit_gives_up_with_orphans_first_in_the_cut_list():
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 20.0, lambda p: 20), target_tags={"growth"}, allow_extend=True)
    assert not res.fitted and res.rung == 4 and "orphans remain" in res.description
    assert res.params.page_width_in == 9.75
    assert [c["id"] for c in res.cuts] == ["a1", "a2"] and res.cuts[0]["orphan"] and not res.cuts[1]["orphan"]


def test_run_fit_gives_up_on_overflow_with_wrapped_bullets_ranked():
    res = run_fit(resolve(MASTER, BULLETS), BOUNDS, fake_measure(lambda p: 20.0), allow_extend=True)
    assert not res.fitted and "still overflows" in res.description and res.params.page_height_in == 12.78
    assert [c["id"] for c in res.cuts] == ["a1", "a2"]           # over by 1 word before over by 3


def test_rank_cuts_orders_orphans_by_fill_then_relevance():
    report = LayoutReport(params=LayoutParams(), content_height_in=1, available_height_in=1, overflow_in=0, fill_pct=100, pages=1,
                          bullets=[BulletMeasure("x", "s", 2, 10, 2, 30), BulletMeasure("y", "s", 2, 10, 2, 10), BulletMeasure("z", "s", 2, 10, 1, 70)])
    cuts = rank_cuts(report, {"growth"}, {"x": ["growth"], "y": ["ops"], "z": []})
    assert [c["id"] for c in cuts] == ["y", "x", "z"]
