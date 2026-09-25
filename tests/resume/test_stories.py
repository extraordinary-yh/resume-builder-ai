import pytest

from resumebuilder.data import Bullet
from resumebuilder.stories import load_stories, parse_front_matter, validate_stories

STORY = """---
id: acme-growth
company: Acme
role: Engineer
period: 2025-01 .. 2025-06
headline: Grew signups
competencies: [growth, ownership]
tech: [React]
metrics: ["10K signups"]
evidence:
  - {kind: ticket, ref: DEMO-1}
bullets: [a1]
questions: [ownership]
---
## Situation / Task

We had no demos.

## Action

I built them.

## Result

10K signups.
"""


def test_parse_front_matter_splits_meta_and_body():
    meta, body = parse_front_matter(STORY)
    assert meta["id"] == "acme-growth" and meta["bullets"] == ["a1"]
    assert body.startswith("## Situation")


def test_parse_front_matter_requires_fences():
    with pytest.raises(ValueError, match="front matter"):
        parse_front_matter("no fences here")


def test_load_and_validate(tmp_path):
    (tmp_path / "acme-growth.md").write_text(STORY)
    (tmp_path / "_general.md").write_text("# general answers\n")
    stories = load_stories(tmp_path)
    assert list(stories) == ["acme-growth"] and stories["acme-growth"].company == "Acme"
    bullets = {"a1": Bullet(id="a1", role="acme", text="x", story="acme-growth")}
    assert validate_stories(stories, bullets) == []


def test_validate_reports_cross_reference_problems(tmp_path):
    (tmp_path / "acme-growth.md").write_text(STORY.replace("bullets: [a1]", "bullets: [a1, ghost]").replace("## Action", "## Doing"))
    stories = load_stories(tmp_path)
    bullets = {"a1": Bullet(id="a1", role="acme", text="x", story="other"), "b2": Bullet(id="b2", role="acme", text="y", story="missing")}
    problems = validate_stories(stories, bullets)
    text = "\n".join(problems)
    assert "ghost" in text and "other" in text and "missing" in text and "## Action" in text


def test_load_reports_missing_required_keys(tmp_path):
    (tmp_path / "bad.md").write_text("---\nid: bad\n---\nbody\n")
    with pytest.raises(ValueError, match="company"):
        load_stories(tmp_path)
