"""Resume source data: the bullet bank, the master resume, overlays, and the resolved resume."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ResumeDataError(ValueError):
    """The bank, the master, or an overlay is inconsistent."""


@dataclass
class Bullet:
    id: str
    role: str
    text: str
    story: str = ""
    short: str = ""
    long: str = ""
    metric: str = ""
    tags: list[str] = field(default_factory=list)
    approved: bool = False            # True only for wording the user signed off on; drafts need --drafts to render
    source: str = ""                  # where the approved wording came from (a docx name, "the user 2026-09-02 chat", ...)
    derived_from: str = ""            # for paraphrased drafts: the approved bullet id they keep the meaning and metrics of
    approved_variants: list[str] = field(default_factory=list)   # variant names ("short", "long") the user also approved

    def variant(self, name: str) -> str:
        if not name or name == "text":
            return self.text
        value = getattr(self, name, "") if name in ("short", "long") else ""
        if not value:
            raise ResumeDataError(f"bullet {self.id!r} has no {name!r} variant")
        return value


@dataclass
class LayoutParams:
    """Every knob the template reads. Defaults mirror the user's Word file (2026-09 SWE version)."""
    page_width_in: float = 9.25
    page_height_in: float = 12.28
    margin_in: float = 0.5
    font_pt: float = 9.0
    line_height: float = 1.571        # Word: 1.25 x single; Merriweather single = 1.257 em
    name_pt: float = 16.5
    contact_pt: float = 8.0
    heading_pt: float = 11.5          # as in the Word file
    role_pt: float = 10.0             # as in the Word file
    company_pt: float = 9.5           # company name (bold) slightly larger than the 9 pt body (the user, 2026-09-02)
    section_before_pt: float = 9.7    # tuned so any line → heading baseline gap = 26.7 pt (Word's value)
    section_after_pt: float = 4.5     # tuned so heading → next title baseline gap = 22 pt (10 pt role) / 21.4 pt (9 pt line)
    role_gap_pt: float = 7.65         # tuned so last bullet → next role title = 22 pt, same as after a heading
    edu_gap_pt: float = 7.4           # same visible gap before the second degree line (9 pt)
    title_pad_pt: float = 0.0         # extra above a 10 pt role title (Chromium snaps baselines to 0.75 pt anyway)
    role_line_height: float = 1.5     # role title line box; 1.5 x 10 pt puts the company line 14.5 pt below (Word)
    contact_gap_pt: float = 8.0       # visible white band name → contact ≈ 12 pt, equal to contact → first heading
    first_section_before_pt: float = 5.8   # the first heading sits closer to the contact line than later headings do to text
    name_top_pt: float = -2.4         # first baseline at 52.3 pt from the page top (Word)
    bullet_gap_pt: float = 0.0
    bullet_indent_pt: float = 5.5
    bullet_size_pt: float = 5.0
    orphan_min_fill_pct: float = 50.0  # a wrapped bullet's last line must fill at least this much
    tech_weight: float = 530.0         # tech terms use the variable font at this weight (metrics are 700 on a 300 body)

    @classmethod
    def from_layout(cls, layout: dict[str, Any]) -> "LayoutParams":
        page = layout.get("page", {}) or {}
        kw: dict[str, float] = {}
        if "width_in" in page:
            kw["page_width_in"] = float(page["width_in"])
        if "height_in" in page:
            kw["page_height_in"] = float(page["height_in"])
        for k in cls.__dataclass_fields__:
            if k in ("page_width_in", "page_height_in"):
                continue
            if k in layout and layout[k] is not None:
                kw[k] = float(layout[k])
        return cls(**kw)

    @property
    def line_pt(self) -> float:
        return round(self.font_pt * self.line_height, 3)

    @property
    def content_width_in(self) -> float:
        return round(self.page_width_in - 2 * self.margin_in, 3)

    def replace(self, **kw: Any) -> "LayoutParams":
        unknown = set(kw) - set(asdict(self))
        if unknown:
            raise ResumeDataError(f"unknown layout keys: {sorted(unknown)}")
        d = asdict(self)
        d.update({k: float(v) for k, v in kw.items()})
        return LayoutParams(**d)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class ResolvedBullet:
    id: str
    text: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ResolvedSection:
    id: str
    heading: str
    subheading: str
    dates: str
    location: str
    bullets: list[ResolvedBullet]
    url: str = ""


@dataclass
class Resolved:
    basics: dict[str, Any]
    summary: str
    roles: list[ResolvedSection]
    projects: list[ResolvedSection]
    education: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    earlier: list[str]
    agent_notes: list[str]
    layout: LayoutParams
    show_summary: bool = False

    def all_bullets(self) -> list[ResolvedBullet]:
        return [b for s in self.roles + self.projects for b in s.bullets]

    def sha(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:8]


REQUIRED_MASTER = ("basics", "roles", "projects", "education", "skills", "layout")
_BULLET_FIELDS = tuple(Bullet.__dataclass_fields__)


def load_bullets(path: Path) -> dict[str, Bullet]:
    doc = yaml.safe_load(Path(path).read_text()) or []
    out: dict[str, Bullet] = {}
    for entry in doc:
        kwargs = {k: entry[k] for k in _BULLET_FIELDS if k in entry}
        for required in ("id", "role", "text"):
            if required not in kwargs:
                raise ResumeDataError(f"bullet entry missing {required!r}: {entry!r}")
        kwargs["tags"] = list(kwargs.get("tags") or [])
        kwargs["approved_variants"] = list(kwargs.get("approved_variants") or [])
        kwargs["approved"] = bool(kwargs.get("approved", False))
        b = Bullet(**kwargs)
        if b.id in out:
            raise ResumeDataError(f"duplicate bullet id {b.id!r}")
        out[b.id] = b
    return out


def load_master(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    missing = [k for k in REQUIRED_MASTER if k not in doc]
    if missing:
        raise ResumeDataError(f"{path} missing sections: {missing}")
    return doc


def load_overlay(path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text()) or {}


def load_version(root: Path, name: str) -> dict[str, Any]:
    """A named resume version (profile/versions/<name>.yaml) is an overlay on the master."""
    path = Path(root) / "profile" / "versions" / f"{name}.yaml"
    if not path.exists():
        raise ResumeDataError(f"no resume version {name!r} (expected {path})")
    doc = load_overlay(path)
    doc.setdefault("name", name)
    return doc


def merge_overlays(base: dict[str, Any] | None, top: dict[str, Any] | None) -> dict[str, Any]:
    """Apply `top` (a job overlay) over `base` (a version): lists union, maps merge, scalars from top."""
    base, top = dict(base or {}), dict(top or {})
    out: dict[str, Any] = {**base}
    for key in ("include", "exclude", "target_tags"):
        out[key] = list(dict.fromkeys(list(base.get(key) or []) + list(top.get(key) or [])))
    out["exclude"] = [i for i in out["exclude"] if i not in (top.get("include") or [])]
    out["include"] = [i for i in out["include"] if i not in (top.get("exclude") or [])]
    for key in ("order", "variants", "titles", "layout", "basics"):
        out[key] = {**(base.get(key) or {}), **(top.get(key) or {})}
    for key in ("summary", "show_summary", "job_id", "notes", "name", "based_on", "skills", "allow_extend", "file_tag"):
        if key in top:
            out[key] = top[key]
    return out


def app_dir(root: Path, job_id: str) -> Path:
    return Path(root) / "data" / "applications" / job_id.replace(":", "-")


def resolved_basics(master: dict[str, Any], overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """The master's contact block with the overlay's `basics` keys on top. A version sets the name the resume
    carries (startup → Alex Rivera, swe → Alex Morgan) so the name alone says which resume went where."""
    return {**dict(master.get("basics") or {}), **dict((overlay or {}).get("basics") or {})}


def resume_name(master: dict[str, Any], overlay: dict[str, Any] | None = None) -> str:
    return str(resolved_basics(master, overlay).get("name") or "resume")


def resume_file_name(master: dict[str, Any], overlay: dict[str, Any] | None, label: str) -> str:
    """`<Name>_Resume_<LABEL>.pdf`, e.g. Alex_Rivera_Resume_STARTUP.pdf, Alex_Morgan_Resume_SWE.pdf."""
    stem = "_".join(resume_name(master, overlay).split())
    return f"{stem}_Resume_{str(label).upper()}.pdf"


def _section(entry: dict[str, Any], kind: str, ids: list[str], bullets: dict[str, Bullet], variants: dict[str, str],
             titles: dict[str, str] | None = None) -> ResolvedSection:
    resolved = [ResolvedBullet(i, bullets[i].variant(variants.get(i, "")), list(bullets[i].tags)) for i in ids]
    if kind == "role":
        title = (titles or {}).get(entry["id"], entry.get("title", ""))
        return ResolvedSection(entry["id"], entry["company"], title, entry.get("dates", ""),
                               entry.get("location", ""), resolved)
    return ResolvedSection(entry["id"], entry["name"], entry.get("tagline", ""), entry.get("dates", ""),
                           entry.get("location", ""), resolved, entry.get("url", ""))


def resolve(master: dict[str, Any], bullets: dict[str, Bullet], overlay: dict[str, Any] | None = None,
            allow_drafts: bool = False) -> Resolved:
    overlay = overlay or {}
    include, exclude = list(overlay.get("include") or []), set(overlay.get("exclude") or [])
    order, variants = dict(overlay.get("order") or {}), dict(overlay.get("variants") or {})
    unknown = [i for i in list(include) + sorted(exclude) + list(variants) + [i for ids in order.values() for i in ids]
               if i not in bullets]
    for entry in master["roles"] + master["projects"]:
        unknown += [i for i in entry.get("bullets", []) if i not in bullets]
    bad_variants = [f"{i}:{v}" for i, v in variants.items()
                    if i in bullets and v not in ("", "text") and not (v in ("short", "long") and getattr(bullets[i], v, ""))]
    if unknown or bad_variants:
        problems = []
        if unknown:
            problems.append(f"unknown bullet ids: {sorted(set(unknown))}")
        if bad_variants:
            problems.append(f"missing variants: {bad_variants}")
        raise ResumeDataError("; ".join(problems))

    def ids_for(entry: dict[str, Any]) -> list[str]:
        ids = [i for i in entry.get("bullets", []) if i not in exclude]
        ids += [i for i in include if bullets[i].role == entry["id"] and i not in ids]
        if entry["id"] in order:
            wanted = [i for i in order[entry["id"]] if i in ids]
            ids = wanted + [i for i in ids if i not in wanted]
        lead = entry.get("lead", "")
        if lead:
            # A pinned lead bullet says what the product was; a recruiter scans that line to learn what the
            # role was about, so no version or overlay may drop it or reorder it out of first place.
            if lead not in entry.get("bullets", []):
                raise ResumeDataError(f"role {entry['id']!r} pins lead bullet {lead!r}, which is not one of its bullets")
            if lead in exclude:
                raise ResumeDataError(f"bullet {lead!r} is the pinned lead of {entry['id']!r} and cannot be excluded")
            ids = [lead] + [i for i in ids if i != lead]
        return ids

    titles = dict(overlay.get("titles") or {})
    unknown_roles = [r for r in titles if r not in {e["id"] for e in master["roles"]}]
    if unknown_roles:
        raise ResumeDataError(f"overlay titles for unknown roles: {unknown_roles}")
    roles = [_section(e, "role", ids_for(e), bullets, variants, titles) for e in master["roles"]]
    projects = [_section(e, "project", ids_for(e), bullets, variants) for e in master["projects"]]
    if not allow_drafts:
        drafts = [b.id for s in roles + projects for b in s.bullets
                  if not bullets[b.id].approved
                  or (variants.get(b.id, "") not in ("", "text") and variants[b.id] not in bullets[b.id].approved_variants)]
        if drafts:
            raise ResumeDataError(f"unapproved bullets selected: {drafts} (the user approves by setting approved: true; "
                                  "pass --drafts to render anyway)")
    layout = LayoutParams.from_layout(master["layout"] or {}).replace(**(overlay.get("layout") or {}))
    show_summary = overlay.get("show_summary", (master["layout"] or {}).get("show_summary", False))
    return Resolved(
        basics=resolved_basics(master, overlay), summary=str(overlay.get("summary", master.get("summary", "")) or ""),
        roles=roles, projects=projects, education=list(master["education"]),
        skills=list(overlay.get("skills") or master["skills"]),
        earlier=list(master.get("earlier") or []), agent_notes=list(master.get("agent_notes") or []), layout=layout,
        show_summary=bool(show_summary),
    )
