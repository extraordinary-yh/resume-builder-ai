"""Render the resolved resume to HTML, then to PDF through Chromium."""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .data import Resolved
from .measure import MEASURE_JS, LayoutReport, layout_report, pdf_pages_and_fonts

TEMPLATES = Path(__file__).resolve().parent / "templates"
FONT_FILES = {"300": "Merriweather-Light.ttf", "400": "Merriweather-Regular.ttf", "700": "Merriweather-Bold.ttf"}
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TECH = re.compile(r"(?<![*\w])\*(?!\*)([^*\n]+?)\*(?![*\w])")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


VARIABLE_FONT = "Merriweather-Variable.ttf"      # wght 300..900; used only for medium-weight tech terms


def font_faces(fonts_dir: Path) -> str:
    rules = []
    for weight, name in FONT_FILES.items():
        path = Path(fonts_dir) / name
        if not path.exists():
            raise FileNotFoundError(f"font file missing: {path} (vendor it under assets/fonts/merriweather/)")
        data = base64.b64encode(path.read_bytes()).decode()
        rules.append(f'@font-face {{ font-family: "Merriweather"; font-style: normal; font-weight: {weight}; '
                     f'src: url("data:font/ttf;base64,{data}") format("truetype"); }}')
    vf = Path(fonts_dir) / VARIABLE_FONT
    if vf.exists():
        data = base64.b64encode(vf.read_bytes()).decode()
        rules.append(f'@font-face {{ font-family: "Merriweather VF"; font-style: normal; font-weight: 300 900; '
                     f'src: url("data:font/ttf;base64,{data}") format("truetype"); }}')
    return "\n".join(rules)


def bold_html(text: str) -> Markup:
    """`**x**` → <b>x</b> and `[text](url)` → <a href="url">text</a>, on escaped text."""
    out = str(escape(text))
    out = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    out = _BOLD.sub(r"<b>\1</b>", out)
    return Markup(_TECH.sub(r'<span class="tech">\1</span>', out))      # *term* → Regular-weight tech term


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "j2"]))
    env.filters["bold"] = bold_html
    return env


def _icon_uri(icons_dir: Path | None, name: str) -> str:
    if not icons_dir or not name:
        return ""
    path = Path(icons_dir) / name
    if not path.exists():
        return ""                                   # no icon file → plain text, per the user's rule
    mime = "image/svg+xml" if path.suffix == ".svg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def contact_items(basics: dict, icons_dir: Path | None) -> list[dict]:
    items = []
    for key in ("location", "email", "phone"):
        if basics.get(key):
            items.append({"label": basics[key], "url": "", "prefix": "", "icon": _icon_uri(icons_dir, basics.get(f"{key}_icon", ""))})
    for link in basics.get("links", []) or []:
        items.append({"label": link.get("label", link.get("url", "")), "url": link.get("url", ""),
                      "prefix": link.get("prefix", ""), "icon": _icon_uri(icons_dir, link.get("icon", ""))})
    return items


def render_html(resolved: Resolved, fonts_dir: Path, icons_dir: Path | None = None) -> str:
    p = resolved.layout
    return _env().get_template("resume.html.j2").render(
        r=resolved, p=p, content_w=p.content_width_in, font_css=Markup(font_faces(fonts_dir)),
        contact=contact_items(resolved.basics, icons_dir))


@dataclass
class BuildResult:
    html_path: Path
    pdf_path: Path
    layout_path: Path
    report: LayoutReport


class Renderer:
    """Keeps one Chromium open so the fit ladder can measure many candidates quickly."""

    def __init__(self, fonts_dir: Path, icons_dir: Path | None = None) -> None:
        self.fonts_dir = Path(fonts_dir)
        self.icons_dir = Path(icons_dir) if icons_dir else None
        self._pw = None
        self._browser = None

    def __enter__(self) -> "Renderer":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError("playwright is not installed: run `uv sync` then `uv run playwright install chromium`") from e
        self._pw = sync_playwright().start()
        try:
            # JOBRADAR_CHROMIUM points at an already-installed Chromium (e.g. a cloud session that
            # ships one but cannot download Playwright's own build).
            executable = os.environ.get("JOBRADAR_CHROMIUM") or None
            self._browser = self._pw.chromium.launch(executable_path=executable)
        except Exception as e:
            self._pw.stop()
            raise RuntimeError("Chromium is missing: run `uv run playwright install chromium`") from e
        return self

    def __exit__(self, *exc) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def _render(self, resolved: Resolved, out_dir: Path) -> tuple[Path, Path, dict]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "resume.html"
        html_path.write_text(render_html(resolved, self.fonts_dir, self.icons_dir))
        pdf_path = out_dir / "resume.pdf"
        page = self._browser.new_page()
        try:
            page.goto(html_path.resolve().as_uri())
            page.emulate_media(media="print")
            page.evaluate("() => document.fonts.ready.then(() => true)")
            raw = page.evaluate(MEASURE_JS)
            page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
        finally:
            page.close()
        return html_path, pdf_path, raw

    def measure(self, resolved: Resolved, out_dir: Path) -> LayoutReport:
        _, pdf_path, raw = self._render(resolved, out_dir)
        pages, fonts = pdf_pages_and_fonts(pdf_path)
        return layout_report(raw, resolved.layout, pages=pages, fonts=sorted(fonts))

    def build(self, resolved: Resolved, out_dir: Path) -> BuildResult:
        html_path, pdf_path, raw = self._render(resolved, out_dir)
        pages, fonts = pdf_pages_and_fonts(pdf_path)
        report = layout_report(raw, resolved.layout, pages=pages, fonts=sorted(fonts))
        layout_path = Path(out_dir) / "layout.json"
        layout_path.write_text(json.dumps(report.to_dict(), indent=2))
        return BuildResult(html_path, pdf_path, layout_path, report)


def build(resolved: Resolved, out_dir: Path, fonts_dir: Path, icons_dir: Path | None = None) -> BuildResult:
    with Renderer(fonts_dir, icons_dir) as ren:
        return ren.build(resolved, out_dir)
