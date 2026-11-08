#!/usr/bin/env python3
"""Manual check of the K0 variant-B blockers (protocol section 6, M2): does each claimed mutant survive the test?

With a path argument it runs on that copy of the tree and exits 1 when a mutant survives or the unmutated test is red.
"""
import subprocess
import sys
from pathlib import Path

CASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/hihol/projects/idea-to-deploy/.itd-memory/host-inputs/ITD-PILOT-TESTGAP/work/manual/K0")  # copy of the K0 template
F = CASE / "hooks/codex-dispatch.py"
MUTANTS = {
    "uid-owner-check-dropped": ("return info.st_uid == getuid() and not info.st_mode & 0o022",
                                "return not info.st_mode & 0o022"),
    "ttl-shortened-to-60s": ("APPROVAL_TTL_SECONDS = 30 * 60", "APPROVAL_TTL_SECONDS = 60"),
    "ttl-lower-bound-dropped": ("return 0 <= age <= APPROVAL_TTL_SECONDS", "return age <= APPROVAL_TTL_SECONDS"),
    "input-hash-command-only": ("            binding[key] = payload[key]\n",
                                "            binding[key] = ({\"command\": payload[key].get(\"command\")} if key == \"tool_input\" "
                                "and isinstance(payload[key], dict) else payload[key])\n"),
}
orig = F.read_text(encoding="utf-8")
p0 = subprocess.run(["python3", "tests/verify_codex_ask_gates.py"], cwd=CASE, capture_output=True, text=True, timeout=300)
print(f"unmutated: exit {p0.returncode}, {(p0.stdout.strip().splitlines() or [''])[-1]}")
red = p0.returncode != 0
for name, (a, b) in MUTANTS.items():
    assert orig.count(a) == 1, name
    F.write_text(orig.replace(a, b), encoding="utf-8")
    try:
        p = subprocess.run(["python3", "tests/verify_codex_ask_gates.py"], cwd=CASE, capture_output=True, text=True,
                           timeout=300)
        last = (p.stdout.strip().splitlines() or [""])[-1]
        print(f"{name}: exit {p.returncode}, {last} -> {'SURVIVED' if p.returncode == 0 else 'killed'}")
        red = red or p.returncode == 0
    finally:
        F.write_text(orig, encoding="utf-8")
print("restored:", subprocess.run(["git", "status", "--short"], cwd=CASE, capture_output=True, text=True).stdout or "clean")
sys.exit(1 if len(sys.argv) > 1 and red else 0)
