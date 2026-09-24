#!/usr/bin/env python3
"""G-003 HOOKS-TIER-EXIT-1 oracle: advisory hooks go quiet on a low-risk unit.

`hooks/TIER_EXEMPT.json` names the advisory hooks allowed to exit early when the active
unit's riskTier is `low`. This oracle checks, on real subprocess runs of each listed hook:

- the list parses, its exempt tier is exactly `low`, and it names exactly the approved
  advisory hooks; no hard gate (`docs/HARNESS_TRUST_POLICY.json` hardGates) and no hook
  from the forbidden list below appears in it;
- low: every step of the hook's provocation fixture exits 0 with empty stdout, and no
  file under the isolated HOME/TMPDIR/project changes (no state, no ledger) - both when
  the tier comes from STATE.currentUnit and from the GOAL unit named by currentUnitId;
- a CLOSED low unit (currentUnit.status=verified, left in STATE by the harness) silences
  nothing: output is byte-identical to the pre-fix hook;
- a low unit silences nothing when it is not the payload's project: no payload `cwd`, or a
  payload `cwd` outside any ITD project while CLAUDE_PROJECT_DIR and the process cwd point
  at the low project (how the repository's own suites drive hooks); nor when STATE and GOAL
  name different units (or STATE's active unit has no id), nor when the goal is not
  active - all byte-identical to pre-fix;
- "byte-identical" covers exit code, stdout and stderr of every step plus the set of files
  the hook creates/changes/removes;
- medium / high / no tier: the candidate hook's (exit, stdout) per step is byte-identical
  to the pre-fix hook bytes (`tests/fixtures/hook_tier_exit/<hook>.prefix.txt`, pinned by
  sha256 and, when the base commit is reachable, re-derived from git) run on the same
  fixture in the same isolated paths - and the provocation is non-trivial (the pre-fix
  hook prints or writes something on it).

`--mutations` copies `hooks/` into a temp dir, applies independent mutations and requires
each to turn the suite red. `--hooks-dir DIR` runs the suite against another hooks copy.

Run: sh skills/_shared/itd_py.sh tests/verify_hook_tier_exit.py [--mutations]
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "hook_tier_exit"
BASE_COMMIT = "8d192dd"
APPROVED = {"context-aware.sh", "context-budget.sh", "stuck-detection.sh", "handoff-readiness.sh"}
PREFIX_SHA256 = {
    "context-aware.sh": "f143ed3b11f6628310ef333913b100c7f2e10b7646dac62a5479a3894ccb2334",
    "context-budget.sh": "36ecd7b3af74a3e0c91983e75f1354c68109c8a0476f24a33d28cf44bca57b9d",
    "handoff-readiness.sh": "b4cb6aaf7632cc76e60ebe78364f412986027fe5d6d75c79b49b9200766dea63",
    "stuck-detection.sh": "84526f255c6a4e8b4f70ccc046005199852243b983544be276b1e991038e5135",
}
# Gates, enforcement hooks, evidence producers and session-context hooks: never exempt.
FORBIDDEN = {
    "state-guard.sh", "pii-egress-guard.sh", "completion-gate.sh", "check-review-before-commit.sh",
    "completion-signals.sh", "completion-stop.sh", "check-skills.sh", "check-tool-skill.sh",
    "wip-gate.sh", "careful.sh", "freeze.sh", "model-policy.sh", "risk-score.sh",
    "crash-recovery.sh", "execution-trace.sh", "cross-review-precommit.sh",
    "pre-flight-check.sh", "session-open-diagnostic.sh",
}
SID = "tier-exit-oracle"

FAILS: list[str] = []
PASSES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSES
    if cond:
        PASSES += 1
    else:
        FAILS.append(name + (f": {detail}" if detail else ""))
        print(f"  FAIL {name}" + (f" - {detail}" if detail else ""))


def payloads(hook: str, proj: Path) -> list[dict]:
    base = {"session_id": SID, "cwd": str(proj)}
    if hook == "context-aware.sh":
        return [dict(base, prompt="continue")]
    if hook == "context-budget.sh":
        return [dict(base, tool_name="Bash", tool_input={"command": "grep -r TODO /"})]
    if hook == "stuck-detection.sh":
        step = dict(base, tool_name="Bash", tool_input={"command": "pytest -x"},
                    tool_response={"exit_code": 1})
        return [step, step, step, step]
    if hook == "handoff-readiness.sh":
        return [dict(base, stop_hook_active=False)]
    raise KeyError(hook)


def build_env(root: Path, hook: str, tier: str | None, variant: str = "state") -> tuple[Path, dict]:
    """(Re)create an isolated world under a FIXED root path so two runs see equal paths."""
    if root.exists():
        shutil.rmtree(root)
    home, tmp, proj = root / "home", root / "tmp", root / "proj"
    for d in (home, tmp, proj / ".itd-memory", root / "elsewhere"):
        d.mkdir(parents=True)
    unit: dict = {"id": "U-1", "status": "verified" if variant == "verified" else "in_progress"}
    if tier:
        unit["riskTier"] = tier
    state: dict = {"version": 1, "currentUnit": unit}
    if variant == "mismatch":
        # STATE's active unit has no tier; GOAL points at another, low unit
        state = {"version": 1, "currentUnit": {"id": "U-1", "status": "in_progress"}}
        goal = {"version": 1, "status": "active", "currentUnitId": "U-2",
                "units": [dict(unit, id="U-2", criterion="c", verificationCommand="true")]}
        (proj / ".itd-memory" / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
    if variant == "noid":
        # STATE's active unit carries neither id nor tier: GOAL cannot be tied to it
        state = {"version": 1, "currentUnit": {"status": "in_progress"}}
        goal = {"version": 1, "status": "active", "currentUnitId": "U-1",
                "units": [dict(unit, criterion="c", verificationCommand="true")]}
        (proj / ".itd-memory" / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
    if variant == "abandoned":
        state = {"version": 1}
        goal = {"version": 1, "status": "abandoned", "currentUnitId": "U-1",
                "units": [dict(unit, criterion="c", verificationCommand="true")]}
        (proj / ".itd-memory" / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
    if variant == "goal":
        # tier only in the goal ledger: STATE carries no current unit
        state = {"version": 1}
        goal = {"version": 1, "status": "active", "currentUnitId": "U-1",
                "units": [dict(unit, criterion="c", verificationCommand="true")]}
        (proj / ".itd-memory" / "GOAL.json").write_text(json.dumps(goal), encoding="utf-8")
    (proj / ".itd-memory" / "STATE.json").write_text(json.dumps(state), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(proj)], check=True, capture_output=True)
    (proj / "work.txt").write_text("uncommitted\n", encoding="utf-8")
    if hook == "context-aware.sh":
        # one call below the threshold, warned long ago, session started 10.5 minutes ago
        (tmp / f"claude-context-{SID}.json").write_text(json.dumps(
            {"count": 39, "last_warning": 0, "session_start": time.time() - 630}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ITD_", "CLAUDE_"))}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "TMPDIR": str(tmp), "TMP": str(tmp),
                "TEMP": str(tmp), "CLAUDE_SESSION_ID": SID, "CLAUDE_PROJECT_DIR": str(proj),
                "PYTHONDONTWRITEBYTECODE": "1"})
    return proj, env


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def run(script: Path, hook: str, root: Path, tier: str | None,
        variant: str = "state") -> tuple[list, dict, dict]:
    proj, env = build_env(root, hook, tier, variant)
    before = snapshot(root)
    steps = []
    for payload in payloads(hook, proj):
        if variant == "nocwd":
            payload = {k: v for k, v in payload.items() if k != "cwd"}
        elif variant == "foreign":
            payload = dict(payload, cwd=str(root / "elsewhere"))
        r = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                           capture_output=True, text=True, cwd=proj, env=env, timeout=60)
        steps.append((r.returncode, r.stdout, r.stderr))
    return steps, before, snapshot(root)


def behaviour(script: Path, hook: str, root: Path, tier: str | None, variant: str = "state") -> tuple:
    """(rc, stdout, stderr) per step + the NAMES of files created/changed/removed.

    Contents are not compared: the context-aware fixture seeds a wall-clock timestamp, so
    two runs write different bytes into the same state file."""
    steps, before, after = run(script, hook, root, tier, variant)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    return steps, changed


def prefix_script(hook: str) -> Path:
    return FIXTURES / (hook[:-3] + ".prefix.txt")


def check_prefix_pins() -> None:
    for hook, digest in PREFIX_SHA256.items():
        path = prefix_script(hook)
        data = path.read_bytes() if path.exists() else b""
        check(f"pin:{hook}", hashlib.sha256(data).hexdigest() == digest, "pre-fix fixture drifted")
        live = subprocess.run(["git", "show", f"{BASE_COMMIT}:hooks/{hook}"], cwd=REPO,
                              capture_output=True, timeout=30)
        if live.returncode == 0:
            check(f"pin-git:{hook}", live.stdout == data, f"fixture != {BASE_COMMIT}:hooks/{hook}")


def check_list(hooks_dir: Path) -> set[str]:
    path = hooks_dir / "TIER_EXEMPT.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        check("list:parse", False, f"{path}: {exc}")
        return set()
    check("list:tier", data.get("exemptTier") == "low", f"exemptTier={data.get('exemptTier')!r}")
    entries = data.get("hooks") if isinstance(data.get("hooks"), list) else []
    names = {str(e.get("script")) for e in entries if isinstance(e, dict)}
    check("list:reasons", all(isinstance(e, dict) and str(e.get("reason") or "").strip()
                              for e in entries), "every entry needs a reason")
    policy = json.loads((REPO / "docs" / "HARNESS_TRUST_POLICY.json").read_text(encoding="utf-8"))
    hard = {g["script"] for g in policy.get("hardGates", []) if isinstance(g, dict)}
    check("list:hardgates-present", len(hard) >= 12, f"only {len(hard)} hardGates read")
    check("list:no-hardgate", not (names & hard), f"hard gates listed: {sorted(names & hard)}")
    check("list:no-forbidden", not (names & FORBIDDEN), f"forbidden listed: {sorted(names & FORBIDDEN)}")
    check("list:exact", names == APPROVED, f"got {sorted(names)}")
    return names


def suite(hooks_dir: Path) -> list[str]:
    global PASSES
    FAILS.clear()
    PASSES = 0
    check_prefix_pins()
    listed = check_list(hooks_dir)
    work = Path(tempfile.mkdtemp(prefix="itd-tier-exit-"))
    try:
        root = work / "w"
        for hook in sorted(APPROVED):
            cand = hooks_dir / hook
            pre_steps, pre_before, pre_after = run(prefix_script(hook), hook, root, None)
            nontrivial = any(out for _, out, _ in pre_steps) or pre_before != pre_after
            check(f"provocation:{hook}", nontrivial, "pre-fix hook neither printed nor wrote")
            for tier in ("medium", "high", None):
                want = behaviour(prefix_script(hook), hook, root, tier)
                got = behaviour(cand, hook, root, tier)
                check(f"identical:{hook}:{tier or 'none'}", got == want,
                      f"candidate {got!r} != pre-fix {want!r}"[:300])
            steps, before, after = run(cand, hook, root, "low")
            check(f"low-silent:{hook}", all(rc == 0 and out == "" for rc, out, _ in steps),
                  f"steps {steps!r}"[:300])
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            check(f"low-no-write:{hook}", not changed, f"changed {changed}")
            steps, before, after = run(cand, hook, root, "low", "goal")
            check(f"goal-fallback-silent:{hook}",
                  all(rc == 0 and out == "" for rc, out, _ in steps) and before == after,
                  f"steps {steps!r}"[:300])
            want = behaviour(prefix_script(hook), hook, root, "low", "verified")
            got = behaviour(cand, hook, root, "low", "verified")
            check(f"closed-unit-not-exempt:{hook}", got == want,
                  f"candidate {got!r} != pre-fix {want!r}"[:300])
            want = behaviour(prefix_script(hook), hook, root, None, "goal")
            got = behaviour(cand, hook, root, None, "goal")
            check(f"identical:{hook}:goal-none", got == want,
                  f"candidate {got!r} != pre-fix {want!r}"[:300])
            for variant in ("nocwd", "foreign", "mismatch", "abandoned", "noid"):
                want = behaviour(prefix_script(hook), hook, root, "low", variant)
                got = behaviour(cand, hook, root, "low", variant)
                check(f"not-exempt-{variant}:{hook}", got == want,
                      f"candidate {got!r} != pre-fix {want!r}"[:300])
            check(f"listed:{hook}", hook in listed)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return list(FAILS)


MUTATIONS = [
    ("hard gate added to the list", "TIER_EXEMPT.json",
     '"hooks": [', '"hooks": [\n    {"script": "state-guard.sh", "reason": "mutant"},'),
    ("medium treated as low", "tier_exempt.py", 'tier == "low"', 'tier in ("low", "medium")'),
    ("missing tier falls back to low", "tier_exempt.py", "return None  # no tier",
     'return "low"  # no tier'),
    ("closed unit still exempt", "tier_exempt.py", 'unit.get("status") not in ACTIVE', "False"),
    ("fall-through to CLAUDE_PROJECT_DIR", "tier_exempt.py", 'raw = payload.get("cwd")',
     'raw = payload.get("cwd") or __import__("os").environ.get("CLAUDE_PROJECT_DIR")'),
    ("STATE unit without id tied to any GOAL unit", "tier_exempt.py",
     "if not state_id:", "if False:"),
    ("GOAL/STATE unit mismatch ignored", "tier_exempt.py", "current != state_id", "False"),
    ("early exit removed from stuck-detection", "stuck-detection.sh",
     'exempt("stuck-detection.sh", payload)', "False"),
]


def mutations() -> int:
    baseline = suite(REPO / "hooks")
    if baseline:
        print("skip mutations: baseline suite is red: " + ", ".join(baseline))
        return 1
    lethal = 0
    for name, target, old, new in MUTATIONS:
        tmp = Path(tempfile.mkdtemp(prefix="itd-tier-mut-"))
        try:
            hooks = tmp / "hooks"
            shutil.copytree(REPO / "hooks", hooks, ignore=shutil.ignore_patterns("__pycache__"))
            text = (hooks / target).read_text(encoding="utf-8")
            if old not in text:
                print(f"  MUTATION {name}: anchor not found in {target}")
                continue
            (hooks / target).write_text(text.replace(old, new, 1), encoding="utf-8")
            fails = suite(hooks)
            print(f"  MUTATION {name}: {'lethal' if fails else 'SURVIVED'} ({len(fails)} fails)")
            lethal += bool(fails)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"mutations lethal: {lethal}/{len(MUTATIONS)}")
    return 0 if lethal >= 3 and lethal == len(MUTATIONS) else 1


def main() -> int:
    args = sys.argv[1:]
    if "--mutations" in args:
        return mutations()
    hooks_dir = Path(args[args.index("--hooks-dir") + 1]) if "--hooks-dir" in args else REPO / "hooks"
    fails = suite(hooks_dir)
    if fails:
        print(f"FAILED: {len(fails)} failed, {PASSES} passed")
        return 1
    print(f"PASSED: 0 failed, {PASSES} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
