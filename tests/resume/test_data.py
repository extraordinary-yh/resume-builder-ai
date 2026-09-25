import pytest

from resumebuilder.data import Bullet, LayoutParams, ResumeDataError, app_dir, load_bullets, load_master, merge_overlays, resolve

BULLETS = {
    "a1": Bullet(id="a1", role="acme", text="Drove **10K** signups.", short="**10K** signups.", tags=["growth"], story="acme-growth", approved=True, approved_variants=["short"]),
    "a2": Bullet(id="a2", role="acme", text="Built the API.", tags=["backend"], approved=True),
    "a3": Bullet(id="a3", role="acme", text="Spare bullet.", tags=["ops"], approved=True),
    "p1": Bullet(id="p1", role="proj", text="Shipped the thing.", tags=["frontend"], approved=True),
    "d1": Bullet(id="d1", role="acme", text="Drove **10K** signups with growth loops.", tags=["growth"], derived_from="a1"),
}
MASTER = {
    "basics": {"name": "Alex Morgan", "location": "SF", "email": "alex@example.com", "phone": "111-222-3333", "links": []},
    "summary": "AI product engineer.",
    "agent_notes": ["Fictional example; verify your own eligibility."],
    "roles": [{"id": "acme", "company": "Acme", "title": "Engineer", "location": "NYC", "dates": "2025 - now", "bullets": ["a1", "a2"]}],
    "projects": [{"id": "proj", "name": "Proj", "tagline": "a demo", "dates": "2024", "url": "https://p", "bullets": ["p1"]}],
    "education": [{"degree": "B.S.", "school": "Example University, 2024"}],
    "skills": [{"label": "Languages", "items": ["Python", "TypeScript"]}],
    "earlier": ["Example Mobile — iOS intern (2020)"],
    "layout": {"page": {"width_in": 9.25, "height_in": 12.28, "max_width_in": 9.75, "width_step_in": 0.25,
                        "max_height_in": 13.0, "height_step_in": 0.25},
               "margin_in": 0.5, "font_pt": 9, "line_height": 1.571, "heading_pt": 10.5, "role_pt": 9.5},
}


def test_resolve_master_keeps_order_and_layout_defaults():
    r = resolve(MASTER, BULLETS)
    assert [b.id for b in r.roles[0].bullets] == ["a1", "a2"]
    assert r.roles[0].heading == "Acme" and r.roles[0].subheading == "Engineer" and r.roles[0].dates == "2025 - now"
    assert r.projects[0].heading == "Proj" and r.projects[0].subheading == "a demo" and r.projects[0].url == "https://p"
    assert r.layout == LayoutParams(page_width_in=9.25, page_height_in=12.28, margin_in=0.5, font_pt=9, line_height=1.571, heading_pt=10.5, role_pt=9.5)
    assert r.layout.content_width_in == 8.25 and r.layout.line_pt == 14.139
    assert r.agent_notes == ["Fictional example; verify your own eligibility."] and r.earlier == ["Example Mobile — iOS intern (2020)"]
    assert len(r.sha()) == 8 and r.sha() == resolve(MASTER, BULLETS).sha()


def test_resolve_overlay_include_exclude_order_variants_layout():
    overlay = {"job_id": "x:1", "include": ["a3"], "exclude": ["a2"], "order": {"acme": ["a3", "a1"]},
               "variants": {"a1": "short"}, "layout": {"line_height": 1.25, "page_height_in": 11.5}, "summary": "Custom."}
    r = resolve(MASTER, BULLETS, overlay)
    assert [b.id for b in r.roles[0].bullets] == ["a3", "a1"]
    assert r.roles[0].bullets[1].text == "**10K** signups."
    assert r.layout.line_height == 1.25 and r.layout.page_height_in == 11.5 and r.layout.margin_in == 0.5 and r.layout.page_width_in == 9.25
    assert r.summary == "Custom." and r.sha() != resolve(MASTER, BULLETS).sha()


def test_resolve_order_appends_unlisted_ids_in_master_order():
    r = resolve(MASTER, BULLETS, {"order": {"acme": ["a2"]}})
    assert [b.id for b in r.roles[0].bullets] == ["a2", "a1"]


def _pinned(lead="a1"):
    m = {**MASTER, "roles": [{**MASTER["roles"][0], "lead": lead}]}
    return m


def test_pinned_lead_bullet_stays_first_whatever_the_order_says():
    r = resolve(_pinned(), BULLETS, {"order": {"acme": ["a2", "a1"]}})
    assert [b.id for b in r.roles[0].bullets] == ["a1", "a2"]


def test_pinned_lead_bullet_leads_even_when_an_overlay_adds_bullets():
    r = resolve(_pinned(), BULLETS, {"include": ["a3"], "order": {"acme": ["a3"]}})
    assert [b.id for b in r.roles[0].bullets] == ["a1", "a3", "a2"]


def test_pinned_lead_bullet_cannot_be_excluded():
    with pytest.raises(ResumeDataError, match="pinned lead"):
        resolve(_pinned(), BULLETS, {"exclude": ["a1"]})


def test_pinned_lead_must_be_one_of_the_role_bullets():
    with pytest.raises(ResumeDataError, match="not one of its bullets"):
        resolve(_pinned("a3"), BULLETS)


def test_resolve_reports_every_unknown_id():
    with pytest.raises(ResumeDataError) as e:
        resolve(MASTER, BULLETS, {"include": ["nope"], "exclude": ["zip"], "variants": {"a2": "short"}})
    msg = str(e.value)
    assert "nope" in msg and "zip" in msg and "a2" in msg


def test_overlay_titles_rename_roles_and_reject_unknown():
    r = resolve(MASTER, BULLETS, {"titles": {"acme": "AI Product Engineer"}})
    assert r.roles[0].subheading == "AI Product Engineer"
    with pytest.raises(ResumeDataError, match="unknown roles"):
        resolve(MASTER, BULLETS, {"titles": {"nope": "x"}})


def test_include_goes_to_the_bullets_own_role():
    r = resolve(MASTER, BULLETS, {"include": ["a3"]})
    assert [b.id for b in r.roles[0].bullets] == ["a1", "a2", "a3"]


def test_load_bullets_and_master_from_yaml(tmp_path):
    (tmp_path / "bullets.yaml").write_text("- {id: a1, role: acme, text: 'x', tags: [t]}\n- {id: a1, role: acme, text: 'y'}\n")
    with pytest.raises(ResumeDataError, match="duplicate"):
        load_bullets(tmp_path / "bullets.yaml")
    (tmp_path / "bullets.yaml").write_text("- {id: a1, role: acme, text: 'x', tags: [t]}\n")
    assert load_bullets(tmp_path / "bullets.yaml")["a1"].tags == ["t"]
    (tmp_path / "resume.yaml").write_text("basics: {name: M}\nroles: []\n")
    with pytest.raises(ResumeDataError, match="education"):
        load_master(tmp_path / "resume.yaml")


def test_app_dir_replaces_colon(tmp_path):
    assert app_dir(tmp_path, "google:123") == tmp_path / "data" / "applications" / "google-123"


def test_drafts_are_refused_unless_allowed():
    with pytest.raises(ResumeDataError, match="unapproved bullets selected: \\['d1'\\]"):
        resolve(MASTER, BULLETS, {"include": ["d1"]})
    r = resolve(MASTER, BULLETS, {"include": ["d1"]}, allow_drafts=True)
    assert [b.id for b in r.roles[0].bullets] == ["a1", "a2", "d1"]
    assert resolve(MASTER, BULLETS, {"variants": {"a1": "short"}}).roles[0].bullets[0].text == "**10K** signups."   # approved variant
    unapproved = {**BULLETS, "a1": Bullet(id="a1", role="acme", text="x", short="y", approved=True)}
    with pytest.raises(ResumeDataError, match="unapproved"):
        resolve(MASTER, unapproved, {"variants": {"a1": "short"}})


def test_merge_overlays_version_then_job():
    version = {"name": "swe", "titles": {"acme": "Software Engineer"}, "order": {"acme": ["a2", "a1"]}, "exclude": ["a3"],
               "target_tags": ["backend"], "layout": {"page_height_in": 12}}
    job = {"job_id": "x:1", "include": ["a3"], "titles": {}, "order": {"proj": ["p1"]}, "variants": {"a1": "short"},
           "target_tags": ["growth"], "layout": {"line_height": 1.6}, "summary": "S"}
    m = merge_overlays(version, job)
    assert m["include"] == ["a3"] and m["exclude"] == []                     # the job's include wins over the version's exclude
    assert m["order"] == {"acme": ["a2", "a1"], "proj": ["p1"]} and m["titles"] == {"acme": "Software Engineer"}
    assert m["target_tags"] == ["backend", "growth"] and m["layout"] == {"page_height_in": 12, "line_height": 1.6}
    assert m["summary"] == "S" and m["job_id"] == "x:1" and m["name"] == "swe"
    assert merge_overlays(version, {"file_tag": "BCG_FDE", "allow_extend": True})["file_tag"] == "BCG_FDE"
    assert merge_overlays(None, job)["include"] == ["a3"] and merge_overlays(version, None)["exclude"] == ["a3"]


def test_version_basics_override_the_name_and_the_file_name():
    from resumebuilder.data import resolved_basics, resume_file_name, resume_name
    startup = {"name": "startup", "basics": {"name": "Alex Rivera"}}
    r = resolve(MASTER, BULLETS, startup)
    assert r.basics["name"] == "Alex Rivera" and r.basics["email"] == "alex@example.com"        # other contact keys stay
    assert resolve(MASTER, BULLETS).basics["name"] == "Alex Morgan" and MASTER["basics"]["name"] == "Alex Morgan"
    assert r.sha() != resolve(MASTER, BULLETS).sha()
    assert resume_name(MASTER, None) == "Alex Morgan" and resume_name(MASTER, startup) == "Alex Rivera"
    assert resume_file_name(MASTER, None, "swe") == "Alex_Morgan_Resume_SWE.pdf"
    assert resume_file_name(MASTER, startup, "startup") == "Alex_Rivera_Resume_STARTUP.pdf"
    assert resume_file_name(MASTER, startup, "ACME") == "Alex_Rivera_Resume_ACME.pdf"
    merged = merge_overlays(startup, {"job_id": "x:1", "based_on": "startup"})
    assert merged["basics"] == {"name": "Alex Rivera"}                                  # a job overlay keeps the version's name
    assert merge_overlays(startup, {"basics": {"name": "Other"}})["basics"] == {"name": "Other"}
    assert resolved_basics(MASTER, {"basics": {"phone": "999"}})["phone"] == "999"




def test_overlay_can_replace_the_skills_block():
    r = resolve(MASTER, BULLETS, {"skills": [{"label": "Testing", "items": ["Jest"]}]})
    assert r.skills == [{"label": "Testing", "items": ["Jest"]}]
    assert resolve(MASTER, BULLETS).skills[0]["label"] == "Languages"
