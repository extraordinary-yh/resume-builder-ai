# Build your own resume

Run `uv sync`, `uv run python scripts/init_workspace.py`, and `uv run playwright install chromium`.

Replace `profile/resume.yaml` with your contact details, roles, education, projects and layout. Replace `profile/bullets.yaml` with your actual bullets. Each bullet has a stable ID, role ID, text, tags, source, optional story ID, and `approved` flag. Fictional examples are marked approved only to demonstrate rendering; they are not your claims.

Put evidence stories in `profile/stories/`. Front matter names the story, company, period, headline, competencies and bullet IDs; the body contains Situation / Task, Action, and Result. `resumebuilder validate` checks those links.

Named overlays live in `profile/versions/`. A job overlay in `data/applications/<company-id>/overlay.yaml` can select a `based_on` version, bullet order, variants, and target tags. `diff` makes changes visible. New wording stays unapproved until you approve it. Use `--drafts` only to inspect a draft.

`resumebuilder fit --version swe` produces a PDF under `build/resume/swe/`. A job build stores its PDF under `Applied Job Resumes/<company-id>/` with a metadata pointer in `data/applications/`. This folder name describes intended use; creating a PDF never records an application as submitted.

The renderer runs from the repository because it uses local fonts and workspace files. Generated HTML embeds fonts. Keep outputs and profiles private.
