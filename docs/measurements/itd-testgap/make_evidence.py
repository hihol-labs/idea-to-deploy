#!/usr/bin/env python3
"""Copy the host-only pilot evidence (run transcripts, proxy logs, the canary marker) into the git-ignored machine
input `.itd-memory/host-inputs/ITD-PILOT-TESTGAP-evidence/`. Run records, blind files and tools are tracked here."""
import shutil
from pathlib import Path

WORK = Path("/home/hihol/projects/idea-to-deploy/.itd-memory/host-inputs/ITD-PILOT-TESTGAP")
HOST = WORK.parent / "ITD-PILOT-TESTGAP-evidence"

if HOST.exists():
    shutil.rmtree(HOST)
(HOST / "sides").mkdir(parents=True)
for side in sorted((WORK / "work" / "runs").glob("*.side")):
    if side.name.startswith("probe"):
        continue
    dst = HOST / "sides" / side.name
    shutil.copytree(side / "projects", dst / "projects")
    shutil.copy2(side / "proxy.log", dst / "proxy.log")
shutil.copy2(WORK / "canary-secret.txt", HOST / "canary-secret.txt")
print(sum(1 for _ in HOST.rglob("*") if _.is_file()), "files in", HOST)
