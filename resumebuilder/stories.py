"""Story bank: Markdown files with YAML front matter under profile/stories/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .data import Bullet

REQUIRED = ("id", "company", "period", "headline", "competencies", "bullets")
REQUIRED_HEADINGS = ("## Situation", "## Action")


@dataclass
class Story:
    id: str
    company: str
    period: str
    headline: str
    competencies: list[str]
    bullets: list[str]
    role: str = ""
    tech: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValueError("story must start with a '---' front matter fence")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("story front matter has no closing '---' fence")
    meta = yaml.safe_load(text[4:end]) or {}
    return meta, text[end + 5:].lstrip("\n")


def load_stories(directory: Path) -> dict[str, Story]:
    out: dict[str, Story] = {}
    for path in sorted(Path(directory).glob("*.md")):
        if path.name.startswith("_"):
            continue
        meta, body = parse_front_matter(path.read_text())
        missing = [k for k in REQUIRED if k not in meta]
        if missing:
            raise ValueError(f"{path.name}: front matter missing {missing}")
        known = {k: meta[k] for k in Story.__dataclass_fields__ if k in meta and k not in ("body", "path")}
        story = Story(**known, body=body, path=path)
        story.bullets = list(story.bullets or [])
        if story.id in out:
            raise ValueError(f"duplicate story id {story.id!r} in {path.name}")
        out[story.id] = story
    return out


def validate_stories(stories: dict[str, Story], bullets: dict[str, Bullet]) -> list[str]:
    problems: list[str] = []
    for s in stories.values():
        for h in REQUIRED_HEADINGS:
            if not any(line.startswith(h) for line in s.body.splitlines()):
                problems.append(f"{s.id}: body has no '{h}' heading")
        for bid in s.bullets:
            if bid not in bullets:
                problems.append(f"{s.id}: lists unknown bullet {bid!r}")
            elif bullets[bid].story != s.id:
                problems.append(f"{s.id}: bullet {bid!r} points at story {bullets[bid].story!r}")
    for b in bullets.values():
        if b.story and b.story not in stories:
            problems.append(f"bullet {b.id!r}: story {b.story!r} does not exist")
    return problems
