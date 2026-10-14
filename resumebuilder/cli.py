"""`resumebuilder …` subcommands."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .config import repo_root
from .data import (ResumeDataError, app_dir, load_bullets, load_master, load_overlay, load_version, merge_overlays, resolve,
                   resume_file_name)
from .export import diff_resolved, export_markdown
from .fit import Bounds, run_fit
from .measure import LayoutReport
from .render import Renderer
from .stories import load_stories, validate_stories
from .storage import store_in_hub as _store_in_hub

EXIT_DATA, EXIT_FIT, EXIT_BROWSER = 1, 2, 3


class _Paths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.master = root / "profile" / "resume.yaml"
        self.bullets = root / "profile" / "bullets.yaml"
        self.stories = root / "profile" / "stories"
        self.fonts = root / "assets" / "fonts" / "merriweather"
        self.icons = root / "assets" / "icons"
        self.build = root / "build" / "resume"


def _overlay_path(paths: _Paths, args) -> Path | None:
    if getattr(args, "overlay", None):
        return Path(args.overlay)
    if getattr(args, "job", None):
        return app_dir(paths.root, args.job) / "overlay.yaml"
    return None


def _load(paths: _Paths, args):
    """Returns (master, bullets, base, job_overlay, combined, overlay_path, out_dir, version_name)."""
    master, bullets = load_master(paths.master), load_bullets(paths.bullets)
    op = _overlay_path(paths, args)
    job = None
    if op is not None:
        if not op.exists():
            raise ResumeDataError(f"no overlay at {op}")
        job = load_overlay(op)
    version = getattr(args, "version", None) or (job or {}).get("based_on")
    base = load_version(paths.root, version) if version else None
    combined = merge_overlays(base, job) if (base or job) else None
    if getattr(args, "out", None):
        out = Path(args.out)
    elif op is not None:
        out = op.parent
    else:
        out = paths.build / version if version else paths.build
    return master, bullets, base, job, combined, op, out, version


def _named_copy(pdf: Path, master: dict, overlay: dict | None, version: str | None, tag: str | None = None) -> Path | None:
    """Copy resume.pdf to the clean <Name>_Resume.pdf attachment name.
    The name is the one the resume carries (the version's `basics.name`, else the master's)."""
    label = tag or version
    if not label:
        return None
    target = pdf.with_name(resume_file_name(master, overlay, label))
    shutil.copy(pdf, target)
    return target


def _print_report(r: LayoutReport) -> None:
    p = r.params
    line = f"{r.pages} page{'s' if r.pages != 1 else ''} at {p.page_width_in} x {p.page_height_in} in, fill {r.fill_pct}%"
    line += f", overflow {r.overflow_in:.2f}in" if r.overflow_in > 0 else f", slack {-r.overflow_in:.2f}in"
    orphans = r.orphans
    line += f", {len(orphans)} orphan{'s' if len(orphans) != 1 else ''}" if orphans else ", no orphans"
    print(line)
    print(f"{'id':28} {'lines':>5} {'over':>5} {'fill':>5}  note")
    orphan_ids = {b.id for b in orphans}
    for b in r.bullets:
        note = "ORPHAN: last line under half width" if b.id in orphan_ids else ""
        print(f"{b.id:28} {b.lines:5d} {b.over_by_words:5d} {b.last_line_fill_pct:4d}%  {note}")
    bad = [f for f in r.fonts if not f.startswith("Merriweather")]
    if bad:
        print(f"WARNING: non-Merriweather fonts in the PDF: {bad}")


def _print_no_fit(fit) -> None:
    if fit.rung == 3:                                  # overflow, extension refused: the cut-or-extend decision
        print(f"NOT WRITTEN: {fit.description}.")
        print("Evaluate, cheapest loss first (the user's rule: cut a line unless every remaining line is too valuable to lose):")
        for c in fit.cuts[:8]:
            flags = []
            if not c["metric"]:
                flags.append("no metric")
            if c["relevance"] == 0:
                flags.append("off target tags")
            print(f"  {c['id']:24} {c['section']:14} {c['lines']} line(s)  {c['action']}  saves {c['saves']}  {', '.join(flags)}")
        if fit.extend_to_in:
            print(f"  or extend the page to {fit.extend_to_in}in: pass --extend (or set allow_extend: true in the overlay) and say why in its notes")
        else:
            print("  extension is not possible within page.max_height_in; a line must go")
        return
    print(f"NOT WRITTEN: {fit.description}. Paraphrase these bullets (add `short` variants), most urgent first:")
    for c in fit.cuts:
        why = f"orphan, last line {c['last_line_fill_pct']}% wide" if c.get("orphan") else f"over by {c.get('over_by_words', '?')} word(s)"
        print(f"  {c['id']} ({c['section']}): {c['lines']} lines, {why}")


def cmd_resume(args) -> int:
    paths = _Paths(repo_root())
    try:
        if args.resume_cmd == "validate":
            bullets = load_bullets(paths.bullets)
            load_master(paths.master)
            problems = validate_stories(load_stories(paths.stories), bullets) if paths.stories.exists() else []
            for p in problems:
                print(p)
            print("ok" if not problems else f"{len(problems)} problem(s)")
            return 0 if not problems else EXIT_DATA
        master, bullets, base, job, overlay, op, out, version = _load(paths, args)
        drafts = bool(getattr(args, "drafts", False))
        resolved = resolve(master, bullets, overlay, allow_drafts=drafts)
        if args.resume_cmd == "export-md":
            target = paths.root / "profile" / "resume.md"
            target.write_text(export_markdown(resolved))
            print(f"wrote {target}")
            return 0
        if args.resume_cmd == "diff":
            reference = resolve(master, bullets, base, allow_drafts=True) if base else resolve(master, bullets, None, allow_drafts=True)
            label = f"version {version}" if version else "master"
            print(f"# {op.name if op else 'overlay'} vs {label}")
            for line in diff_resolved(reference, resolved) or ["(no differences)"]:
                print(line)
            return 0
        with Renderer(paths.fonts, paths.icons) as ren:
            if args.resume_cmd in ("build", "check", "fit"):
                # Every render goes through the fitter: a two-page PDF is never written (the user's rule).
                bounds = Bounds.from_layout(master["layout"])
                target_tags = set((overlay or {}).get("target_tags") or [])
                allow_extend = bool(getattr(args, "extend", False)) or bounds.allow_extend or bool((overlay or {}).get("allow_extend"))
                fit = run_fit(resolved, bounds, lambda r: ren.measure(r, out), target_tags, bank=bullets, allow_extend=allow_extend)
                if not fit.fitted:
                    for stale in ("resume.pdf", "resume.html", "layout.json"):
                        (Path(out) / stale).unlink(missing_ok=True)
                    for stale in Path(out).glob("*_Resume*.pdf") if Path(out).exists() else []:
                        stale.unlink()
                    _print_no_fit(fit)
                    return EXIT_FIT
                fitted = resolve(master, bullets, {**(overlay or {}), "layout": fit.params.to_dict()}, allow_drafts=drafts)
                final = ren.build(fitted, out)
                print(f"landed on rung {fit.rung}: {fit.description} — 1 page, fill {final.report.fill_pct}%, no orphans")
                job_id = getattr(args, "job", None) or (job or {}).get("job_id")
                if job_id and not getattr(args, "out", None):
                    label = (job or {}).get("file_tag") or version or job_id.replace(":", "-")
                    target = _store_in_hub(paths.root, final.pdf_path, job_id,
                                           resume_file_name(master, overlay, label), fitted.sha())
                    print(f"wrote {target} (sha {fitted.sha()})")
                else:
                    print(f"wrote {final.pdf_path} (sha {fitted.sha()})")
                    named = _named_copy(final.pdf_path, master, overlay, version, (job or {}).get("file_tag"))
                    if named:
                        print(f"copied to {named}")
                if args.resume_cmd == "check":
                    _print_report(final.report)
                if args.resume_cmd == "fit" and args.write and op is not None:
                    doc = dict(job or {})
                    doc["layout"] = fit.params.to_dict()
                    op.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
                    print(f"stored layout in {op}")
                elif args.resume_cmd == "fit" and args.write:
                    print("nothing to write for the master resume (defaults live in profile/resume.yaml)")
                return 0
    except ResumeDataError as e:
        print(f"resume data error: {e}")
        return EXIT_DATA
    except FileNotFoundError as e:
        print(str(e))
        return EXIT_DATA
    except ValueError as e:                     # story front matter problems
        print(str(e))
        return EXIT_DATA
    except RuntimeError as e:
        print(str(e))
        return EXIT_BROWSER
    return 0


def add_resume_parser(r) -> None:
    rs = r.add_subparsers(dest="resume_cmd", required=True)
    for name, help_ in (("validate", "check the bullet bank and stories"), ("build", "HTML + PDF + layout.json"),
                        ("check", "build and print lines per bullet"), ("fit", "walk the one-page ladder"),
                        ("diff", "overlay vs master"), ("export-md", "regenerate profile/resume.md")):
        p = rs.add_parser(name, help=help_)
        p.add_argument("--overlay", help="overlay YAML path")
        p.add_argument("--job", help="job id; uses data/applications/<job-dir>/overlay.yaml")
        p.add_argument("--version", help="named resume version from profile/versions/<name>.yaml (a job overlay's based_on)")
        p.add_argument("--drafts", action="store_true", help="allow bullets that the user has not approved yet")
        p.add_argument("--extend", action="store_true", help="allow the fitter to grow the page height for overflow (decide cut vs extend first)")
        p.add_argument("--out", help="output directory (default build/resume[/<version>] or the application dir)")
        if name == "fit":
            p.add_argument("--write", action="store_true", help="store the chosen layout in the overlay")
    r.set_defaults(func=cmd_resume)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="resumebuilder", description="Evidence-backed resumes with deterministic layout.")
    add_resume_parser(p)
    args = p.parse_args(argv)
    return int(args.func(args))
