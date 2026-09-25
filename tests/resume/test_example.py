from pathlib import Path
from resumebuilder.data import load_master,load_bullets,resolve
from resumebuilder.stories import load_stories,validate_stories
ROOT=Path(__file__).resolve().parents[2]

def test_fictional_profile_and_evidence_resolve():
    p=ROOT/'examples/profile'
    bullets=load_bullets(p/'bullets.yaml')
    r=resolve(load_master(p/'resume.yaml'),bullets)
    assert r.basics['email']=='alex@example.com'
    assert len(list(r.all_bullets()))==3
    assert validate_stories(load_stories(p/'stories'),bullets)==[]
