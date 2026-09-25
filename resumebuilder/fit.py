"""The one-page fitter. Policy: never compress spacing below the configured minimum; a wrapped bullet's
last line must fill at least half the width (no orphans); fix orphans by widening the line, and
overflow by adding page height; when the page is at its limits, name the bullets to paraphrase."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Callable

from .data import LayoutParams, Resolved
from .measure import BulletMeasure, LayoutReport

EPS = 1e-9


@dataclass
class Bounds:
    start: LayoutParams
    max_width_in: float
    width_step_in: float
    max_height_in: float
    height_step_in: float
    trim_height: bool = False        # after fitting, cut the page height down to the content (spacing untouched)
    min_height_in: float = 11.0      # never trim below this
    trim_pad_in: float = 0.05        # slack left under the last line
    allow_extend: bool = False       # grow the page height for overflow only when explicitly allowed (the user's rule)

    @classmethod
    def from_layout(cls, layout: dict[str, Any]) -> "Bounds":
        page = layout.get("page", {}) or {}
        start = LayoutParams.from_layout(layout)
        return cls(
            start=start,
            max_width_in=float(page.get("max_width_in", start.page_width_in)),
            width_step_in=float(page.get("width_step_in", 0.25)),
            max_height_in=float(page.get("max_height_in", start.page_height_in)),
            height_step_in=float(page.get("height_step_in", 0.25)),
            trim_height=bool(page.get("trim_height", False)),
            min_height_in=float(page.get("min_height_in", 11.0)),
            trim_pad_in=float(page.get("trim_pad_in", 0.05)),
            allow_extend=bool(page.get("allow_extend", False)),
        )


def widths(b: Bounds) -> list[float]:
    out, w = [b.start.page_width_in], b.start.page_width_in
    while w + b.width_step_in <= b.max_width_in + EPS:
        w = round(w + b.width_step_in, 3)
        out.append(w)
    return out


def heights(b: Bounds) -> list[float]:
    out, h = [b.start.page_height_in], b.start.page_height_in
    while h + b.height_step_in <= b.max_height_in + EPS:
        h = round(h + b.height_step_in, 3)
        out.append(h)
    return out


def rank_cuts(report: LayoutReport, target_tags: set[str], tags_by_id: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Bullets to paraphrase, cheapest and least relevant first: orphans (shortest last line first), then other
    wrapped bullets by how few words push them over."""
    orphan_ids = {b.id for b in report.orphans}

    def key(b: BulletMeasure) -> tuple:
        relevance = len(set(tags_by_id.get(b.id, [])) & set(target_tags))
        if b.id in orphan_ids:
            return (0, b.last_line_fill_pct, relevance)
        return (1, b.over_by_words, relevance)

    wrapped = sorted((b for b in report.bullets if b.lines > 1), key=key)
    return [{"id": b.id, "section": b.section, "lines": b.lines, "over_by_words": b.over_by_words,
             "last_line_fill_pct": b.last_line_fill_pct, "orphan": b.id in orphan_ids} for b in wrapped]


def lines_over(report: LayoutReport) -> int:
    """How many body lines the content exceeds the page by (0 when it fits)."""
    if not report.overflows:
        return 0
    line_in = report.params.font_pt * report.params.line_height / 72.0
    return max(1, math.ceil(report.overflow_in / line_in - EPS))


def cut_candidates(report: LayoutReport, resolved: Resolved, bank: dict[str, Any] | None,
                   target_tags: set[str]) -> list[dict[str, Any]]:
    """Lines that could go, cheapest loss first: a wrapped bullet with an approved short variant (keeps the bullet,
    saves a line), then bullets off the target tags, then bullets without a metric. Skills lines are listed last."""
    bank = bank or {}
    out = []
    for b in report.bullets:
        meta = bank.get(b.id)
        tags = set(getattr(meta, "tags", []) or [])
        relevance = len(tags & set(target_tags))
        has_metric = bool(getattr(meta, "metric", "") or "")
        short_ok = bool(meta and getattr(meta, "short", "") and "short" in (getattr(meta, "approved_variants", []) or []))
        if b.section == "skills":
            out.append({"id": b.id, "section": b.section, "lines": b.lines, "saves": b.lines, "action": "merge or drop the skills line",
                        "relevance": relevance, "metric": has_metric, "rank": (3, 0, 0)})
            continue
        if b.lines > 1 and short_ok:
            out.append({"id": b.id, "section": b.section, "lines": b.lines, "saves": b.lines - 1, "action": "use the approved short variant",
                        "relevance": relevance, "metric": has_metric, "rank": (0, relevance, 0)})
        out.append({"id": b.id, "section": b.section, "lines": b.lines, "saves": b.lines, "action": "drop the bullet",
                    "relevance": relevance, "metric": has_metric, "rank": (1 if not has_metric else 2, relevance, -b.lines)})
    out.sort(key=lambda c: c["rank"])
    for c in out:
        c.pop("rank")
    return out


@dataclass
class FitResult:
    fitted: bool
    rung: int                 # 1 as is, 2 wider page, 3 taller page (or overflow with extension refused), 4 paraphrase needed
    description: str
    params: LayoutParams
    report: LayoutReport
    cuts: list[dict[str, Any]]
    lines_over: int = 0
    extend_to_in: float | None = None     # the height that would fit, when extension is refused


def run_fit(resolved: Resolved, bounds: Bounds, measure: Callable[[Resolved], LayoutReport],
            target_tags: set[str] | frozenset[str] | tuple[str, ...] = (), bank: dict[str, Any] | None = None,
            allow_extend: bool | None = None) -> FitResult:
    allow_extend = bounds.allow_extend if allow_extend is None else allow_extend
    params = bounds.start
    report = measure(replace(resolved, layout=params))
    rung, desc = 1, "as is"
    if report.orphans:                                    # widen the line until no bullet leaves a word behind
        for w in widths(bounds)[1:]:
            params = params.replace(page_width_in=w)
            report = measure(replace(resolved, layout=params))
            rung, desc = 2, f"page width {w}in"
            if not report.orphans:
                break
    if not report.orphans and report.overflows and not allow_extend:
        over = lines_over(report)
        need = report.content_height_in + 2 * params.margin_in + bounds.trim_pad_in
        extend_to = math.ceil(need * 20 - EPS) / 20
        cuts = cut_candidates(report, resolved, bank, set(target_tags))
        return FitResult(False, 3, f"overflows by {over} line{'s' if over != 1 else ''} at {params.page_height_in}in; "
                                   f"cut a line or allow extending to {extend_to}in", params, report, cuts, over,
                         extend_to if extend_to <= bounds.max_height_in + EPS else None)
    if not report.orphans and report.overflows:           # extension allowed: add height until it is one page
        for h in heights(bounds)[1:]:
            params = params.replace(page_height_in=h)
            report = measure(replace(resolved, layout=params))
            rung, desc = 3, f"page height {h}in" + (f" (width {params.page_width_in}in)" if rung == 2 else "")
            if not report.overflows:
                break
    if report.fits:
        if bounds.trim_height:
            needed = report.content_height_in + 2 * params.margin_in + bounds.trim_pad_in
            trimmed = max(bounds.min_height_in, math.ceil(needed * 20 - EPS) / 20)     # up to the next 0.05 in
            if trimmed < params.page_height_in - EPS:
                candidate = params.replace(page_height_in=trimmed)
                trimmed_report = measure(replace(resolved, layout=candidate))
                if trimmed_report.fits:
                    params, report = candidate, trimmed_report
                    desc += f", height trimmed to {trimmed}in"
        return FitResult(True, rung, desc, params, report, [])
    tags_by_id = {b.id: b.tags for b in resolved.all_bullets()}
    what = "orphans remain" if report.orphans else "still overflows"
    return FitResult(False, 4, f"{what} at width {params.page_width_in}in, height {params.page_height_in}in",
                     params, report, rank_cuts(report, set(target_tags), tags_by_id), lines_over(report))
