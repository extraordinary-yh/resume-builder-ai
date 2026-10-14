import shutil

import pytest
import yaml

from resumebuilder.cli import main
from tests.resume.conftest import FONTS_DIR
from tests.resume.test_data import BULLETS, MASTER


def make_repo(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "profile" / "stories").mkdir(parents=True, exist_ok=True)
    (tmp_path / "profile" / "resume.yaml").write_text(yaml.safe_dump(MASTER, sort_keys=False))
    (tmp_path / "profile" / "bullets.yaml").write_text(yaml.safe_dump(
        [{"id": b.id, "role": b.role, "text": b.text, "short": b.short, "tags": b.tags, "story": b.story,
          "approved": b.approved, "approved_variants": b.approved_variants} for b in BULLETS.values()], sort_keys=False))
    (tmp_path / "profile" / "versions").mkdir(exist_ok=True)
    (tmp_path / "profile" / "versions" / "swe.yaml").write_text("name: swe\ntitles: {acme: Software Engineer}\nexclude: [a2]\n")
    (tmp_path / "profile" / "versions" / "startup.yaml").write_text("name: startup\nbasics: {name: Alex Rivera}\nexclude: [a2]\n")
    (tmp_path / "profile" / "stories" / "acme-growth.md").write_text(
        "---\nid: acme-growth\ncompany: Acme\nperiod: 2025\nheadline: h\ncompetencies: [growth]\nbullets: [a1]\n---\n"
        "## Situation\n\ns\n\n## Action\n\na\n")
    if not (tmp_path / "assets" / "fonts" / "merriweather").exists():
        shutil.copytree(FONTS_DIR, tmp_path / "assets" / "fonts" / "merriweather")
    monkeypatch.setenv("RESUMEBUILDER_ROOT", str(tmp_path))
    return tmp_path


def test_validate_and_export_md(tmp_path, monkeypatch, capsys):
    root = make_repo(tmp_path, monkeypatch)
    assert main(["validate"]) == 0
    assert "ok" in capsys.readouterr().out
    (root / "profile" / "bullets.yaml").write_text("- {id: a1, role: acme, text: x, story: nowhere}\n")
    assert main(["validate"]) == 1
    assert "nowhere" in capsys.readouterr().out
    root = make_repo(tmp_path, monkeypatch)
    assert main(["export-md"]) == 0
    assert "## Experience" in (root / "profile" / "resume.md").read_text()


def test_diff_uses_the_job_application_dir(tmp_path, monkeypatch, capsys):
    root = make_repo(tmp_path, monkeypatch)
    app = root / "data" / "applications" / "acme-7"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text("job_id: acme:7\nexclude: [a2]\n")
    assert main(["diff", "--job", "acme:7"]) == 0
    assert "- acme: a2" in capsys.readouterr().out
    assert main(["diff", "--job", "acme:8"]) == 1


@pytest.mark.browser
def test_build_check_and_fit_write(browser, tmp_path, monkeypatch, capsys):
    root = make_repo(tmp_path, monkeypatch)
    assert main(["build"]) == 0
    out = capsys.readouterr().out
    assert (root / "build" / "resume" / "resume.pdf").exists() and "1 page" in out
    assert main(["check"]) == 0
    assert "a1" in capsys.readouterr().out
    app = root / "data" / "applications" / "acme-7"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text("job_id: acme:7\nexclude: [a2]\n")
    assert main(["fit", "--job", "acme:7", "--write"]) == 0
    assert "rung 1" in capsys.readouterr().out
    saved = yaml.safe_load((app / "overlay.yaml").read_text())
    assert saved["layout"]["page_width_in"] == 9.25 and saved["layout"]["line_height"] == 1.571 and saved["exclude"] == ["a2"]
    assert not (app / "resume.pdf").exists() and (app / "layout.json").exists()
    assert (root / "Applied Job Resumes" / "acme" / "acme-7" / "Alex_Morgan_Resume.pdf").exists()


def test_version_and_based_on_and_drafts(tmp_path, monkeypatch, capsys):
    root = make_repo(tmp_path, monkeypatch)
    app = root / "data" / "applications" / "acme-9"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text("job_id: acme:9\nbased_on: swe\ninclude: [d1]\n")
    assert main(["diff", "--job", "acme:9"]) == 1                  # d1 is a draft
    assert "unapproved" in capsys.readouterr().out
    assert main(["diff", "--job", "acme:9", "--drafts"]) == 0
    out = capsys.readouterr().out
    assert "vs version swe" in out and "+ acme: d1" in out and "- acme: a2" not in out    # a2 already excluded by the version
    assert main(["diff", "--version", "nope"]) == 1
    assert "no resume version" in capsys.readouterr().out


@pytest.mark.browser
def test_build_with_version_writes_named_copy(browser, tmp_path, monkeypatch, capsys):
    root = make_repo(tmp_path, monkeypatch)
    assert main(["build", "--version", "swe"]) == 0
    out = capsys.readouterr().out
    assert (root / "build" / "resume" / "swe" / "Alex_Morgan_Resume.pdf").exists() and "copied to" in out
    assert main(["build", "--version", "startup"]) == 0
    assert (root / "build" / "resume" / "startup" / "Alex_Rivera_Resume.pdf").exists()
    assert "<h1>Alex Rivera</h1>" in (root / "build" / "resume" / "startup" / "resume.html").read_text()
    app = root / "data" / "applications" / "acme-5"
    app.mkdir(parents=True)
    (app / "overlay.yaml").write_text("job_id: acme:5\nbased_on: startup\nfile_tag: ACME\n")
    assert main(["build", "--job", "acme:5"]) == 0
    assert (root / "Applied Job Resumes" / "acme" / "acme-5" / "Alex_Rivera_Resume.pdf").exists()
    assert not list(app.glob("*.pdf"))


def test_named_copy_uses_the_versions_name(tmp_path):
    from resumebuilder.cli import _named_copy
    from tests.resume.test_data import MASTER
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF")
    assert _named_copy(pdf, MASTER, None, "swe").name == "Alex_Morgan_Resume.pdf"
    assert _named_copy(pdf, MASTER, {"basics": {"name": "Alex Rivera"}}, "startup").name == "Alex_Rivera_Resume.pdf"
    assert _named_copy(pdf, MASTER, {"basics": {"name": "Alex Rivera"}}, "startup", "ACME").name == "Alex_Rivera_Resume.pdf"
    assert _named_copy(pdf, MASTER, None, None) is None


def test_hub_rebuild_keeps_one_copy_and_updates_changed_resume(tmp_path):
    import json
    from resumebuilder.cli import _store_in_hub
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"original")
    target = _store_in_hub(tmp_path, pdf, "acme:1", "Alex_Resume.pdf", "v1")
    pdf.write_bytes(b"different PDF timestamp, same resume")
    assert _store_in_hub(tmp_path, pdf, "acme:1", "Alex_Resume.pdf", "v1") == target
    assert target.read_bytes() == b"original" and not pdf.exists()
    pdf.write_bytes(b"revised resume")
    _store_in_hub(tmp_path, pdf, "acme:1", "Alex_Resume.pdf", "v2")
    assert target.read_bytes() == b"revised resume"
    assert len(list((tmp_path / "Applied Job Resumes").rglob("*.pdf"))) == 2
    assert (target.parent / "versions/v1/Alex_Resume.pdf").read_bytes() == b"original"
    pointer = json.loads((tmp_path / "data/applications/acme-1/resume-location.json").read_text())
    assert pointer["resume_sha"] == "v2" and (tmp_path / pointer["path"]) == target


def test_shared_resume_rebuild_preserves_other_applications(tmp_path):
    import json
    from resumebuilder.cli import _store_in_hub
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"original")
    target = _store_in_hub(tmp_path, pdf, "acme:1", "Alex_Morgan_Resume.pdf", "v1")
    pointer = tmp_path / "data/applications/acme-1/resume-location.json"
    shared = tmp_path / "data/applications/acme-2/resume-location.json"
    shared.parent.mkdir(parents=True)
    shared.write_text(pointer.read_text())
    pdf.write_bytes(b"same content, different render metadata")
    assert _store_in_hub(tmp_path, pdf, "acme:2", target.name, "v1") == target
    pdf.write_bytes(b"revision")
    _store_in_hub(tmp_path, pdf, "acme:1", target.name, "v2")
    other = json.loads(shared.read_text())
    assert other["resume_sha"] == "v1"
    assert (tmp_path / other["path"]).read_bytes() == b"original"
    assert (tmp_path / other["versions"]["v1"]).read_bytes() == b"original"
    assert target.read_bytes() == b"revision"
    # Revising the second role creates its own PDF, leaving the first untouched.
    pdf.write_bytes(b"second role revision")
    second = _store_in_hub(tmp_path, pdf, "acme:2", target.name, "v3")
    assert second.parent.name == "acme-2"
    assert target.read_bytes() == b"revision"


def test_company_grouping_uses_employer_for_aggregators(tmp_path):
    from resumebuilder.storage import company_folder
    from resumebuilder.data import ResumeDataError
    assert company_folder(tmp_path, "hackernews:123", {"company_folder": "Cora AI"}) == "cora-ai"
    with pytest.raises(ResumeDataError, match="employer"):
        company_folder(tmp_path, "hackernews:123", {})
    (tmp_path / "config").mkdir()
    (tmp_path / "config/companies.yaml").write_text(
        "companies:\n- {key: amazon_nyc, name: Amazon}\n- {key: amazon_bay, name: Amazon}\n")
    assert company_folder(tmp_path, "amazon_nyc:1", {}) == company_folder(tmp_path, "amazon_bay:2", {})
