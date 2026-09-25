"""Build a fictional resume inside build/demo, without changing your profile."""
from pathlib import Path
import os
import shutil
from resumebuilder.cli import main
root=Path(__file__).resolve().parents[1]
workspace=root/"build/demo"
shutil.copytree(root/"examples/profile",workspace/"profile",dirs_exist_ok=True)
shutil.copytree(root/"assets",workspace/"assets",dirs_exist_ok=True)
os.environ["RESUMEBUILDER_ROOT"]=str(workspace)
if main(["validate"]): raise SystemExit(1)
raise SystemExit(main(["fit","--version","swe"]))
