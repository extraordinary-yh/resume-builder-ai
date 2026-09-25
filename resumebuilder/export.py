"""Markdown export for the scanner and a human-readable overlay diff."""
from __future__ import annotations

import re

from .data import Resolved, ResolvedSection

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_TECH = re.compile(r"(?<![*\w])\*(?!\*)([^*\n]+?)\*(?![*\w])")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADER = "# {name} — structured resume (generated from profile/resume.yaml; do not edit)"


def strip_bold(text: str) -> str:
    """Remove **bold** and [text](url) markup, leaving plain text."""
    return _TECH.sub(r"\1", _BOLD.sub(r"\1", _LINK.sub(r"\1", text)))


def _section_md(s: ResolvedSection) -> list[str]:
    when = ", ".join(x for x in (s.dates, s.location) if x)
    head = f"### {s.heading} — {s.subheading} ({when})" if s.subheading else f"### {s.heading} ({when})"
    return [head] + [f"- {strip_bold(b.text)}" for b in s.bullets] + [""]


def export_markdown(r: Resolved) -> str:
    out = [HEADER.format(name=r.basics.get("name", "")), ""]
    out += [f"- {n}" for n in r.agent_notes] + [""]
    out += ["## Summary", "", r.summary or "(none)", "", "## Experience", ""]
    for s in r.roles:
        out += _section_md(s)
    if r.earlier:
        out += ["### Earlier"] + [f"- {e}" for e in r.earlier] + [""]
    out += ["## Projects", ""]
    for s in r.projects:
        out += _section_md(s)
    out += ["## Education", ""]
    out += [f"- {e['degree']}, {e['school']}" + (f" — {e['detail']}" if e.get("detail") else "") for e in r.education] + [""]
    out += ["## Skills", ""] + [f"- {g['label']}: {strip_bold(', '.join(g['items']))}" for g in r.skills] + [""]
    return "\n".join(out)


def diff_resolved(master: Resolved, tailored: Resolved) -> list[str]:
    lines: list[str] = []
    before = {s.id: s for s in master.roles + master.projects}
    for s in tailored.roles + tailored.projects:
        m = before.get(s.id)
        old = {b.id: b.text for b in (m.bullets if m else [])}
        new = {b.id: b.text for b in s.bullets}
        lines += [f"+ {s.id}: {i}" for i in new if i not in old]
        lines += [f"- {s.id}: {i}" for i in old if i not in new]
        lines += [f"~ {s.id}: {i} (reworded)" for i in new if i in old and old[i] != new[i]]
        kept_old = [i for i in old if i in new]
        kept_new = [i for i in new if i in old]
        if kept_old != kept_new:
            lines.append(f"reorder {s.id}: {', '.join(new)}")
        if m and m.subheading != s.subheading:      # an overlay's `titles:` retitles the role
            lines.append(f"title {s.id}: {m.subheading} → {s.subheading}")
    if master.summary != tailored.summary:
        lines.append("~ summary")
    return lines
