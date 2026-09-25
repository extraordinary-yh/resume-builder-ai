import re

from resumebuilder.data import resolve
from resumebuilder.export import diff_resolved, export_markdown, strip_bold
from tests.resume.test_data import BULLETS, MASTER


def test_export_markdown_has_scanner_sections_and_no_contact_details():
    md = export_markdown(resolve(MASTER, BULLETS))
    assert md.startswith("# Alex Morgan — structured resume (generated from profile/resume.yaml; do not edit)")
    for h in ("## Summary", "## Experience", "## Projects", "## Education", "## Skills"):
        assert h in md, h
    assert "- Fictional example; verify your own eligibility." in md and "### Acme — Engineer (2025 - now, NYC)" in md
    assert "- Drove 10K signups." in md and "**" not in md
    assert "### Proj — a demo (2024)" in md and "- B.S., Example University, 2024" in md and "- Languages: Python, TypeScript" in md
    assert "Example Mobile" in md
    assert "alex@example.com" not in md and not re.search(r"\d{3}-\d{3}-\d{4}", md)


def test_strip_bold():
    assert strip_bold("a **b** c") == "a b c"
    assert strip_bold("on *Temporal* with [x](https://y) and **10K**") == "on Temporal with x and 10K"


def test_diff_resolved_lists_added_removed_reworded_reordered():
    master = resolve(MASTER, BULLETS)
    tailored = resolve(MASTER, BULLETS, {"include": ["a3"], "exclude": ["a2"], "order": {"acme": ["a3", "a1"]}, "variants": {"a1": "short"}})
    lines = diff_resolved(master, tailored)
    assert "+ acme: a3" in lines and "- acme: a2" in lines and "~ acme: a1 (reworded)" in lines
    assert diff_resolved(master, master) == []
    reordered = resolve(MASTER, BULLETS, {"order": {"acme": ["a2", "a1"]}})
    assert diff_resolved(master, reordered) == ["reorder acme: a2, a1"]


def test_diff_reports_a_retitled_role():
    from resumebuilder.data import resolve
    from resumebuilder.export import diff_resolved
    from tests.resume.test_data import BULLETS, MASTER
    lines = diff_resolved(resolve(MASTER, BULLETS), resolve(MASTER, BULLETS, {"titles": {"acme": "AI Software Engineer"}}))
    assert lines == ["title acme: Engineer → AI Software Engineer"]
