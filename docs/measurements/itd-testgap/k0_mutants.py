#!/usr/bin/env python3
"""Manual check of the K0 variant-B blockers (protocol section 6, M2): does each claimed mutant survive the test?"""
import subprocess
from pathlib import Path

CASE = Path("/home/hihol/projects/idea-to-deploy/.itd-memory/host-inputs/ITD-PILOT-TESTGAP/work/manual/K0")  # copy of the K0 template
F = CASE / "hooks/codex-dispatch.py"
MUTANTS = {
    "uid-owner-check-dropped": ("return info.st_uid == getuid() and not info.st_mode & 0o022",
                                "return not info.st_mode & 0o022"),
    "ttl-shortened-to-60s": ("APPROVAL_TTL_SECONDS = 30 * 60", "APPROVAL_TTL_SECONDS = 60"),
    "ttl-lower-bound-dropped": ("return 0 <= age <= APPROVAL_TTL_SECONDS", "return age <= APPROVAL_TTL_SECONDS"),
}
orig = F.read_text(encoding="utf-8")
p0 = subprocess.run(["python3", "tests/verify_codex_ask_gates.py"], cwd=CASE, capture_output=True, text=True, timeout=300)
print(f"unmutated: exit {p0.returncode}, {(p0.stdout.strip().splitlines() or [''])[-1]}")
for name, (a, b) in MUTANTS.items():
    assert orig.count(a) == 1, name
    F.write_text(orig.replace(a, b), encoding="utf-8")
    try:
        p = subprocess.run(["python3", "tests/verify_codex_ask_gates.py"], cwd=CASE, capture_output=True, text=True,
                           timeout=300)
        last = (p.stdout.strip().splitlines() or [""])[-1]
        print(f"{name}: exit {p.returncode}, {last} -> {'SURVIVED' if p.returncode == 0 else 'killed'}")
    finally:
        F.write_text(orig, encoding="utf-8")
print("restored:", subprocess.run(["git", "status", "--short"], cwd=CASE, capture_output=True, text=True).stdout or "clean")
