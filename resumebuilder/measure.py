"""Layout facts read back from the rendered page and the PDF."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .data import LayoutParams

PX_PER_IN = 96.0

MEASURE_JS = r"""
() => {
  const page = document.querySelector('.page');
  const trimLastWord = (el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = []; let n; while ((n = walker.nextNode())) nodes.push(n);
    for (let i = nodes.length - 1; i >= 0; i--) {
      const t = nodes[i].nodeValue.replace(/\s+$/, '');
      if (!t) { nodes[i].nodeValue = ''; continue; }
      const cut = t.lastIndexOf(' ');
      nodes[i].nodeValue = cut < 0 ? '' : t.slice(0, cut);
      return true;
    }
    return false;
  };
  const bullets = [];
  for (const li of document.querySelectorAll('li[data-id], .skills p[data-id]')) {
    const cs = getComputedStyle(li);
    const lh = parseFloat(cs.lineHeight);
    const lines = Math.max(1, Math.round(li.getBoundingClientRect().height / lh));
    const words = li.textContent.trim().split(/\s+/).filter(Boolean).length;
    let lastFill = 100;
    const range = document.createRange(); range.selectNodeContents(li);
    const rects = [...range.getClientRects()].filter(r => r.width > 0);
    if (rects.length) {
      const lastTop = Math.max(...rects.map(r => r.top));
      const lastLine = rects.filter(r => Math.abs(r.top - lastTop) < lh / 2);
      const right = Math.max(...lastLine.map(r => r.right));
      const box = li.getBoundingClientRect();
      const padL = parseFloat(cs.paddingLeft) || 0, padR = parseFloat(cs.paddingRight) || 0;
      const left = box.left + padL, width = box.width - padL - padR;
      lastFill = Math.max(0, Math.min(100, Math.round(100 * (right - left) / width)));
    }
    let overBy = 0;
    if (lines > 1) {
      const ul = li.parentElement;                      // <ul> for bullets, .skills for skill lines
      const holder = ul.cloneNode(false);
      holder.style.cssText = 'position:absolute;visibility:hidden;left:0;top:0;box-sizing:border-box;width:' + ul.getBoundingClientRect().width + 'px;margin:0;padding-left:' + getComputedStyle(ul).paddingLeft;
      const clone = li.cloneNode(true);
      holder.appendChild(clone); page.appendChild(holder);
      while (clone.getBoundingClientRect().height > lh * 1.05 && overBy < 200 && trimLastWord(clone)) overBy++;
      holder.remove();
    }
    bullets.push({ id: li.dataset.id, section: li.dataset.section || '', lines, words, over_by_words: overBy, last_line_fill_pct: lastFill });
  }
  const heads = [...document.querySelectorAll('h2')];
  const pageBottom = page.getBoundingClientRect().bottom;
  const sections = heads.map((h, i) => {
    const top = h.getBoundingClientRect().top;
    const next = heads[i + 1] ? heads[i + 1].getBoundingClientRect().top : pageBottom;
    return { name: h.textContent.trim(), height_px: next - top };
  });
  return { content_height_px: page.getBoundingClientRect().height, bullets, sections };
}
"""


@dataclass
class BulletMeasure:
    id: str
    section: str
    lines: int
    words: int
    over_by_words: int
    last_line_fill_pct: int


@dataclass
class LayoutReport:
    params: LayoutParams
    content_height_in: float
    available_height_in: float
    overflow_in: float
    fill_pct: int
    pages: int
    fonts: list[str] = field(default_factory=list)
    bullets: list[BulletMeasure] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    orphan_min_fill_pct: float = 50.0

    @property
    def orphans(self) -> list[BulletMeasure]:
        """Wrapped bullets whose last line is too short: one or two words hanging on a line of their own."""
        return [b for b in self.bullets if b.lines > 1 and b.last_line_fill_pct < self.orphan_min_fill_pct]

    @property
    def overflows(self) -> bool:
        return self.pages > 1 or self.overflow_in > 0

    @property
    def fits(self) -> bool:
        return not self.overflows and not self.orphans

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fits"] = self.fits
        d["orphans"] = [b.id for b in self.orphans]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LayoutReport":
        return cls(params=LayoutParams(**d["params"]), content_height_in=d["content_height_in"],
                   available_height_in=d["available_height_in"], overflow_in=d["overflow_in"], fill_pct=d["fill_pct"],
                   pages=d["pages"], fonts=list(d.get("fonts", [])),
                   bullets=[BulletMeasure(**b) for b in d.get("bullets", [])], sections=list(d.get("sections", [])),
                   orphan_min_fill_pct=float(d.get("orphan_min_fill_pct", 50)))


def line_height_in(params: LayoutParams) -> float:
    return params.font_pt * params.line_height / 72.0


def layout_report(raw: dict[str, Any], params: LayoutParams, pages: int, fonts: list[str]) -> LayoutReport:
    available = params.page_height_in - 2 * params.margin_in
    content = float(raw["content_height_px"]) / PX_PER_IN
    return LayoutReport(
        params=params, content_height_in=round(content, 3), available_height_in=round(available, 3),
        overflow_in=round(content - available, 3), fill_pct=round(100 * content / available), pages=pages, fonts=list(fonts),
        bullets=[BulletMeasure(**b) for b in raw.get("bullets", [])],
        sections=[{"name": s["name"], "height_in": round(float(s["height_px"]) / PX_PER_IN, 2)} for s in raw.get("sections", [])],
        orphan_min_fill_pct=float(params.orphan_min_fill_pct),
    )


def pdf_pages_and_fonts(path: Path) -> tuple[int, set[str]]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    fonts: set[str] = set()
    for page in reader.pages:
        res = page.get("/Resources") or {}
        for f in (res.get("/Font") or {}).values():
            name = str(f.get_object().get("/BaseFont", "")).lstrip("/")
            fonts.add(name.split("+", 1)[-1])
    return len(reader.pages), fonts
