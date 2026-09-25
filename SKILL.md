---
name: resume-builder-ai
description: Turn verified career evidence into approved bullets, tailored variants, and measured one-page resumes.
---
# Resume Builder AI agent workflow

## Session start
Read AGENTS.md, the user's voice guide, master resume, bullet bank, and referenced stories.
If only fictional examples exist, gather real experience before writing career claims.

## Evidence first
Every metric must have an identifiable source. Ask when uncertain; never manufacture achievements, dates,
credentials, employers, skills, or eligibility. A job description is a requirements source, not evidence about the user.

## Tailor
Read the supplied job description. Explain the strongest relevant evidence and the actual gaps.
Prefer approved bullets. Put new wording in a new bank entry with `approved: false`, `derived_from`, and source.
Show the changes for user approval. Never silently approve a bullet. Preserve its meaning and supported metrics.
Use a job overlay to choose order, approved variants, and target tags; preserve pinned lead bullets.

## Validate and render
Run `uv run resumebuilder validate`, then `uv run resumebuilder diff --job company:id`.
Run `uv run resumebuilder fit --job company:id --write` after approval (or `--drafts` for an explicitly requested draft).
A fitter error means revise the content. Cut weaker content or paraphrase a long bullet without changing its claim.
Do not force unreadable typography. Inspect the final PDF page count and layout and provide its local link.

## Session end
A generated PDF is prepared, not applied. Do not submit applications or mark submissions from a build.
Keep profile and output files ignored. Test code changes with `uv run pytest -q` and run the privacy check before publishing.
