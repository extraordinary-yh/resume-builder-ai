"""Company-grouped resume storage, with immutable saved versions and shared pointers."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

from .data import ResumeDataError, app_dir


def company_folder(root: Path, job_id: str, previous: dict) -> str:
    if previous.get("company_folder"):
        company = previous["company_folder"]
    else:
        source = job_id.split(":", 1)[0] if ":" in job_id else job_id.split("-", 1)[0]
        config = root / "config/companies.yaml"
        companies = (yaml.safe_load(config.read_text()) or {}).get("companies", []) if config.exists() else []
        entry = next((c for c in companies if c["key"] == source), {})
        if entry.get("aggregator") or (not entry and source in {"hackernews", "ashby", "greenhouse", "lever", "linkedin"}):
            # Standalone builder has no scanner dependency: require the real employer explicitly.
            raise ResumeDataError("Aggregator job needs its employer in resume-location.json: company_folder")
        else:
            # Multiple boards for one employer share its first configured key.
            company = next((c["key"] for c in companies if c.get("name") == entry.get("name")), source)
    slug = re.sub(r"[^a-z0-9]+", "-", str(company).lower()).strip("-")
    if not slug:
        raise ResumeDataError("Missing employer for resume folder")
    return slug


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _relocate_pointers(root: Path, old: str, new: str) -> None:
    """An archived PDF may be shared by several applications, including submitted ones."""
    for pointer in (root / "data/applications").glob("*/resume-location.json"):
        doc = json.loads(pointer.read_text())
        changed = False
        if doc.get("path") == old:
            doc["path"] = new
            changed = True
        for sha, path in (doc.get("versions") or {}).items():
            if path == old:
                doc["versions"][sha] = new
                changed = True
        if changed:
            pointer.write_text(json.dumps(doc, indent=2) + "\n")


def store_in_hub(root: Path, pdf: Path, job_id: str, filename: str, resume_sha: str) -> Path:
    pointer = app_dir(root, job_id) / "resume-location.json"
    previous = json.loads(pointer.read_text()) if pointer.exists() else {}
    company = company_folder(root, job_id, previous)
    opening = "general" if job_id == company else job_id.replace(":", "-")
    target = root / "Applied Job Resumes" / company / opening / filename
    previous_pdf = root / previous.get("path", "")
    if previous.get("resume_sha") == resume_sha and previous_pdf.is_file():
        # Keep intentionally shared PDFs shared when rebuilding unchanged content.
        pdf.unlink()
        return previous_pdf
    target.parent.mkdir(parents=True, exist_ok=True)
    old = None
    if target.exists() and target.read_bytes() != pdf.read_bytes():
        old_sha = previous.get("resume_sha") or hashlib.sha256(target.read_bytes()).hexdigest()[:8]
        old = target.parent / "versions" / old_sha / filename
        if old.exists() and old.read_bytes() != target.read_bytes():
            raise ResumeDataError(f"conflicting saved resume version at {old}")
        old.parent.mkdir(parents=True, exist_ok=True)
        target.replace(old)
        _relocate_pointers(root, _rel(root, target), _rel(root, old))
        previous.setdefault("versions", {})[old_sha] = _rel(root, old)
    versions = dict(previous.get("versions") or {})
    # Every alias for an archived version must retain the archived bytes.
    if old is not None:
        versions = {sha: (_rel(root, old) if path == _rel(root, target) else path) for sha, path in versions.items()}
    pdf.replace(target)
    versions[resume_sha] = _rel(root, target)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({**previous, "company_folder": company, "path": _rel(root, target),
                                   "resume_sha": resume_sha, "versions": versions}, indent=2) + "\n")
    return target
