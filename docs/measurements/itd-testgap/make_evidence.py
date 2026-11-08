#!/usr/bin/env python3
"""Copy the host-only pilot evidence (run transcripts, proxy logs, the canary marker) into the git-ignored machine
input `.itd-memory/host-inputs/ITD-PILOT-TESTGAP-evidence/`. Run records, blind files and tools are tracked here."""
import json
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
shutil.copy2(WORK / "batch.log", HOST / "batch.log")
(HOST / "s13").mkdir()
S13_TRANSCRIPTS = Path("/home/hihol/.claude/projects")
for rec in sorted((Path(__file__).resolve().parent / "s13").glob("run-*.json")):
    sess = json.loads(rec.read_text(encoding="utf-8")).get("session")
    for t in S13_TRANSCRIPTS.glob(f"*/{sess}.jsonl"):
        shutil.copy2(t, HOST / "s13" / t.name)
print(sum(1 for _ in HOST.rglob("*") if _.is_file()), "files in", HOST)
