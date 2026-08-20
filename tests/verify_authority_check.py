#!/usr/bin/env python3
"""Oracle for scripts/itd_authority_check.py (LPD002-A8).

Self-contained: builds a synthetic repo + snapshot in a temp dir, proves both
sides (clean parity -> exit 0 quiet; divergence/missing counterpart -> exit 1
with path+WHY+FIX; input errors -> exit 2; keys/keyring exempt) and pins the
live procedure doc. Run: python3 -I tests/verify_authority_check.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "itd_authority_check.py"
DOC = ROOT / "docs" / "VERIFICATION_LOOP.md"
PY = sys.executable

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else " — " + detail))
    if cond:
        passed += 1
    else:
        failed += 1


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-I", str(SCRIPT), *args], capture_output=True,
                          text=True, timeout=60)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    shared = root / "repo" / "skills" / "_shared"
    shared.mkdir(parents=True)
    snap = root / "auth"
    snap.mkdir()
    (shared / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (shared / "POLICY.json").write_text("{}\n", encoding="utf-8")
    (snap / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (snap / "POLICY.json").write_text("{}\n", encoding="utf-8")
    (snap / "producer-ed25519.key").write_text("SECRET", encoding="utf-8")
    (snap / "producer-keyring.json").write_text("{\"k\": 1}", encoding="utf-8")

    r = run("--snapshot", str(snap), "--repo", str(root / "repo"))
    check("clean parity exits 0 and stays quiet",
          r.returncode == 0 and r.stdout.strip() == "", r.stdout + r.stderr)

    (snap / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    r = run("--snapshot", str(snap), "--repo", str(root / "repo"))
    check("divergent module exits 1 with WHY and FIX",
          r.returncode == 1 and "DIVERGED mod.py" in r.stdout
          and "WHY:" in r.stdout and "FIX:" in r.stdout, r.stdout)
    check("divergence names the re-mint procedure",
          "re-mint the snapshot from the merged main" in r.stdout, r.stdout)

    (snap / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (snap / "orphan.py").write_text("x = 1\n", encoding="utf-8")
    r = run("--snapshot", str(snap), "--repo", str(root / "repo"))
    check("snapshot-only module is a divergence",
          r.returncode == 1 and "DIVERGED orphan.py" in r.stdout, r.stdout)
    (snap / "orphan.py").unlink()

    (snap / "producer-ed25519.key").write_text("OTHER", encoding="utf-8")
    (snap / "producer-keyring.json").write_text("{\"k\": 2}", encoding="utf-8")
    r = run("--snapshot", str(snap), "--repo", str(root / "repo"))
    check("signing key and keyring are exempt from parity",
          r.returncode == 0, r.stdout)

    r = run("--snapshot", str(root / "missing"), "--repo", str(root / "repo"))
    check("missing snapshot dir is an input error (exit 2)",
          r.returncode == 2 and "ERROR" in r.stdout, r.stdout)

    r = run("--snapshot", str(snap), "--repo", str(root))
    check("non-repository --repo is an input error (exit 2)",
          r.returncode == 2, r.stdout)

    (shared / "newgate.py").write_text("GATE = 2\n", encoding="utf-8")
    r = run("--snapshot", str(snap), "--repo", str(root / "repo"))
    check("repo-side module absent from the snapshot is flagged MISSING",
          r.returncode == 1 and "MISSING newgate.py" in r.stdout, r.stdout)
    (shared / "newgate.py").unlink()

    orphan_only = root / "orphans"
    orphan_only.mkdir()
    (orphan_only / "ghost.py").write_text("x = 1\n", encoding="utf-8")
    r = run("--snapshot", str(orphan_only), "--repo", str(root / "repo"))
    check("all-orphan snapshot is actionable exit 1, not an input error",
          r.returncode == 1 and "DIVERGED ghost.py" in r.stdout, r.stdout)

    empty = root / "empty"
    empty.mkdir()
    r = run("--snapshot", str(empty), "--repo", str(root / "repo"))
    check("empty snapshot vs populated gate is total divergence (exit 1), not a vacuous pass",
          r.returncode == 1 and "MISSING" in r.stdout, r.stdout)

r = subprocess.run([PY, "-I", str(SCRIPT)], capture_output=True, text=True,
                   timeout=60)
check("no arguments is a usage error, never an implicit scan",
      r.returncode == 2 and not r.stdout, r.stdout + r.stderr[:120])

doc = DOC.read_text(encoding="utf-8")
check("the minting/parity procedure is documented in VERIFICATION_LOOP.md",
      "itd_authority_check.py" in doc and "itd-review-authority" in doc)
for phrase in ("merged main", "byte-for-byte",
               "producer-ed25519.key", "producer-keyring.json",
               "When to re-mint"):
    check(f"doc keeps the procedure detail: {phrase!r}", phrase in doc,
          "regressed procedure text")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
