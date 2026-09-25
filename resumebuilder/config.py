from pathlib import Path
import os

def repo_root():
    if os.environ.get("RESUMEBUILDER_ROOT"):
        return Path(os.environ["RESUMEBUILDER_ROOT"]).resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "resumebuilder").is_dir():
            return candidate
    raise FileNotFoundError("Run from the Resume Builder AI checkout or set RESUMEBUILDER_ROOT")
