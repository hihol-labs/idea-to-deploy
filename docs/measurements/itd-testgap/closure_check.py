#!/usr/bin/env python3
"""Machine leg of ITD-PILOT-TESTGAP-AC1: the REL-1.110.6 closure by the ADR-016 convention. Run from the repo root."""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MERGE = "3a770e2ff028455da60aaca60bebefa129825989"
RECEIPT = Path(".itd-memory/host-inputs/REL-1.110.6-post/REL-1.110.6-canonical-a5-adjudication.json")  # copy
DELTA = Path(".itd-memory/host-inputs/REL-1.110.6-post/closure-delta.diff")
RECEIPT_FILE_SHA256 = "6ce18b36b39218ba1b6b31fc6003045b06fb7fc5eb9f9e8e94eb14d71ca08f83"  # bytes of the a5 receipt
err = []


def git(*a):
    return subprocess.check_output(["git", *a], text=True).strip()


if hashlib.sha256(RECEIPT.read_bytes()).hexdigest() != RECEIPT_FILE_SHA256:
    err.append("the receipt copy is not the a5 receipt file")
receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
tree = git("rev-parse", f"{MERGE}^{{tree}}")
if receipt["candidate"]["reviewedTree"] != tree:
    err.append(f"tree {tree} != reviewedTree {receipt['candidate']['reviewedTree']}")
if receipt.get("outcome") != "PASSED":
    err.append("receipt outcome is not PASSED")
decisions = Path(".itd/DECISIONS.md").read_text(encoding="utf-8")
closure = decisions[decisions.index("## 2026-11-07 - закрытие REL-1.110.6 по конвенции ADR-016"):]
for s in (MERGE, tree, receipt["receiptSha256"], hashlib.sha256(DELTA.read_bytes()).hexdigest(), "«Подписываю»"):
    if s not in closure:
        err.append(f"closure section lacks {s[:20]}")
delta_paths = sorted({line[6:] for line in DELTA.read_text(encoding="utf-8").splitlines()
                      if line.startswith("+++ b/")})
if delta_paths != [".itd-memory/STATE.json", ".itd-memory/events.jsonl", ".itd/ACCEPTANCE_CONTRACT.json",
                   ".itd/DECISIONS.md"]:
    err.append(f"delta paths {delta_paths}")
events = [json.loads(x) for x in Path(".itd-memory/events.jsonl").read_text(encoding="utf-8").splitlines() if x]
ver = [e for e in events if e.get("name") == "REL-1.110.6" and e.get("decision") == "verified"]
act = [e for e in events if e.get("name") == "ITD-PILOT-TESTGAP" and e.get("decision") == "activated"]
for e in ver + act:  # written by itd_unit_log.py: harness unit events of the STATE ledger
    if (e.get("actor"), e.get("type"), e.get("ledger")) != ("harness", "unit", "STATE"):
        err.append(f"event {e.get('id')} is not an itd_unit_log.py STATE unit event")
state_rc = subprocess.run([sys.executable, "scripts/validate_state.py", ".itd-memory/STATE.json", ".itd-memory/GOAL.json"],
                          capture_output=True, text=True).returncode
if state_rc != 0:
    err.append("scripts/validate_state.py does not exit 0")
if len(ver) != 1 or len(act) != 1:
    err.append("expected one verified REL-1.110.6 and one activated ITD-PILOT-TESTGAP event")
else:
    t = [datetime.fromisoformat(e["at"].replace("Z", "+00:00")) for e in (ver[0], act[0])]
    if (t[1] - t[0]).total_seconds() < 2 or ver[0]["id"] == act[0]["id"]:
        err.append("activate is not a separate call at least 2 s after verified")
    if receipt["receiptSha256"] not in ver[0].get("evidence", "") or tree not in ver[0].get("evidence", ""):
        err.append("verified evidence lacks the tree or the receipt hash")
contract = json.loads(Path(".itd/ACCEPTANCE_CONTRACT.json").read_text(encoding="utf-8"))
closed = [f for f in contract["closedFollowups"] if f["unitId"] == "REL-1.110.6"]
if len(closed) != 1 or closed[0].get("status") != "closed" or not closed[0].get("closedAt") or \
        not closed[0].get("closureEvidence"):
    err.append("REL-1.110.6 is not in closedFollowups with closedAt and closureEvidence")
if contract["activeFollowup"]["unitId"] != "ITD-PILOT-TESTGAP":
    err.append("activeFollowup is not ITD-PILOT-TESTGAP")
state = json.loads(Path(".itd-memory/STATE.json").read_text(encoding="utf-8"))
if state["currentUnit"]["id"] != "ITD-PILOT-TESTGAP" or state["currentUnit"].get("riskTier") != "medium":
    err.append("STATE currentUnit is not ITD-PILOT-TESTGAP (medium)")
src = Path(".itd-memory/host-inputs/REL-1.110.6-post/decisions-after-candidate.md").read_text(encoding="utf-8")
sections = re.split(r"(?m)^(?=## )", src)[1:]
if len(sections) != 2:
    err.append(f"expected two post-candidate sections, found {len(sections)}")
for sec in sections:
    if sec.strip() not in decisions:
        err.append(f"post-candidate section not carried verbatim: {sec.splitlines()[0]}")
for e in err:
    print("FAIL", e)
print("closure check:", "PASSED" if not err else f"FAILED ({len(err)})")
sys.exit(1 if err else 0)
