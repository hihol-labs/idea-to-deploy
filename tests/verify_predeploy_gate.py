#!/usr/bin/env python3
"""Behavioural proof for the hard gate `check-predeploy-gate.sh` (U16).

The hook is the mechanical half of the pre-deploy independent review gate:
`/deploy` Step 0 was only an instruction, so skipping the step skipped the
gate. This test spawns the hook as a real PreToolUse subprocess and asserts
the enforcement boundary from the outside:

  1. deny  — gated candidate (data-sensitive marker) + content-shipping
             command (`rsync`) and no gate-pass record for the CURRENT
             candidate digest -> exit 2 + permissionDecision "deny";
  2. allow — routine candidate (no marker) with the same command;
  3. allow — read-only inspection (`docker ps`) on a gated candidate;
  4. allow — a gate pass recorded for the exact current candidate digest;
  4b. allow — ADR-008: a valid current pass authorizes the reviewed deploy
             regardless of the transport command's shape (shipment-form
             re-analysis is out of scope; the digest binding stays enforced);
  5. deny  — a gate pass bound to a DIFFERENT digest does not unlock the
             current candidate (the record is a transport, not the contract);
  6. allow — non-Bash tool calls and non-shipping commands are untouched;
  7. deny  — r53: relocating HOME to an attacker tree with a permissive fake
             classifier must NOT change the verdict — the trust anchor comes
             from the account database, not from the environment.

Fixture shape (r53): the trust anchor is no longer HOME-derived, so tests can
no longer redirect it through the environment. The hook under test runs via a
generated RUNNER that loads the real hook bytes and repoints its
`INSTALLED_GATE_SCRIPT` global at a fixture install; that fixture install is a
generated WRAPPER that loads the real gate-module bytes and repoints its
`GATE_MAC_KEY_PATH` at a fixture key. Only the two trust-anchor globals — the
thing under test — differ from production; every judged byte is the real one.

Run: python3 tests/verify_predeploy_gate.py
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "check-predeploy-gate.sh"
GATE_SCRIPT = ROOT / "skills" / "deploy" / "scripts" / "itd_predeploy_gate.py"
# Fixture destinations are assembled from parts and point at an RFC 2606
# .invalid host, so the repository's own secret scrubber cannot mistake a
# test string for a real deploy target.
REMOTE = "deployer@" + "example.invalid"
SYNC_CMD = "rsync -az ./ " + REMOTE + ":/srv/app"
COPY_CMD = "scp build.tar " + REMOTE + ":/srv/"

DATA_SENSITIVE_CLAUDE_MD = "# Fixture project\n\nitd-domain: data-sensitive\n"

LOADER_PRELUDE = """\
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec


def _load(name, path):
    loader = SourceFileLoader(name, path)
    spec = spec_from_loader(name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module
"""


def gate_module():
    spec = importlib.util.spec_from_file_location("itd_predeploy_gate", GATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit("unable to load the installed pre-deploy gate script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_gate_wrapper(home: Path) -> tuple[Path, Path]:
    """Fixture "installed" gate script: real bytes, fixture MAC key.

    Returns (wrapper path at the installed-layout location, fixture key path).
    """
    key_path = home / ".config" / "itd" / "deploy-gate.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = (home / ".claude" / "skills" / "deploy" / "scripts"
               / "itd_predeploy_gate.py")
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        LOADER_PRELUDE
        + f"module = _load('itd_predeploy_gate', {str(GATE_SCRIPT)!r})\n"
        + f"module.GATE_MAC_KEY_PATH = Path({str(key_path)!r})\n"
        + "sys.exit(module.main(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    return wrapper, key_path


def write_hook_runner(home: Path, installed_gate: Path) -> Path:
    """Runner that executes the real hook bytes against the fixture install."""
    runner = home / "run-hook-under-fixture.py"
    runner.write_text(
        LOADER_PRELUDE
        + f"module = _load('check_predeploy_gate', {str(HOOK)!r})\n"
        + f"module.INSTALLED_GATE_SCRIPT = Path({str(installed_gate)!r})\n"
        + "sys.exit(module.main())\n",
        encoding="utf-8",
    )
    return runner


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, timeout=30)


def make_candidate(root: Path, data_sensitive: bool) -> Path:
    cwd = root / "work"
    cwd.mkdir(parents=True)
    git(cwd, "init", "-q")
    git(cwd, "config", "user.email", "predeploy-fixture")
    git(cwd, "config", "user.name", "Predeploy Fixture")
    (cwd / "CLAUDE.md").write_text(
        DATA_SENSITIVE_CLAUDE_MD if data_sensitive else "# Fixture project\n",
        encoding="utf-8",
    )
    (cwd / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", "candidate")
    return cwd


def invoke(cwd: Path, payload: dict, home: Path,
           entry: Path | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONUTF8": "1",
        "ITD_HOST": "claude",
        "PLUGIN_ROOT": str(ROOT),
        "CLAUDE_SESSION_ID": f"predeploy-{uuid.uuid4().hex[:10]}",
    })
    proc = subprocess.run(
        [sys.executable, str(entry if entry is not None else HOOK)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), env=env, timeout=120,
    )
    try:
        parsed = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        parsed = {}
    specific = parsed.get("hookSpecificOutput") or {}
    return (proc.returncode,
            str(specific.get("permissionDecision") or ""),
            str(specific.get("permissionDecisionReason") or ""))


def bash(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": ""},
    }


def main() -> int:
    passed = failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        print(("PASS  " if condition else "FAIL  ") + name
              + (f"  [{detail}]" if detail and not condition else ""))
        if condition:
            passed += 1
        else:
            failed += 1

    gate = gate_module()

    # 1. gated candidate + content-shipping command -> deny
    with tempfile.TemporaryDirectory(prefix="itd-predeploy-deny-") as td:
        root = Path(td)
        home = root / "home"
        home.mkdir()
        # r53: the anchor is account-database-derived, so the fixture is wired
        # through patched module globals, not through HOME (see module doc).
        installed_gate, key_path = write_gate_wrapper(home)
        runner = write_hook_runner(home, installed_gate)
        gate.GATE_MAC_KEY_PATH = key_path
        cwd = make_candidate(root, data_sensitive=True)
        rc, decision, reason = invoke(cwd, bash(SYNC_CMD), home, entry=runner)
        check("gated candidate without a gate pass is denied (exit 2 + deny)",
              rc == 2 and decision == "deny",
              f"rc={rc} decision={decision!r}")
        check("deny reason is actionable (WHY/FIX)",
              "WHY:" in reason and "FIX:" in reason, reason[-200:])

        # 3. read-only inspection stays open on the same gated candidate
        rc, decision, _ = invoke(cwd, bash("docker ps -a"), home, entry=runner)
        check("read-only inspection stays open on a gated candidate",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")

        # 6. non-shipping command and non-Bash tool stay open
        rc, decision, _ = invoke(cwd, bash("git status --short"), home,
                                 entry=runner)
        check("non-shipping Bash command is untouched",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")
        rc, decision, _ = invoke(cwd, {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(cwd / "app.py"), "content": "x"},
        }, home, entry=runner)
        check("non-Bash tool call is untouched",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")

        # 5. a record bound to a different digest does not unlock this candidate
        gate.record_gate_pass(cwd, "0" * 64, "data-sensitive", "0" * 64)
        rc, decision, _ = invoke(cwd, bash(COPY_CMD), home, entry=runner)
        check("gate pass bound to another digest does not unlock the candidate",
              rc == 2 and decision == "deny", f"rc={rc} decision={decision!r}")

        # 4. a record bound to the CURRENT digest opens the path. Since route
        # finding r36 the pass is bound to the current deploy input digest;
        # ADR-008 (2026-08-12) removed the shipment-FORM analysis, so a valid
        # current pass authorizes the independently reviewed deploy regardless
        # of the transport command's exact shape — shipment-form minutiae are
        # out of U16's scope (undecidable to parse; covered by /careful + the
        # completion gate + human deploy review). The digest binding itself
        # stays enforced (the "another digest" negative control above).
        digest = gate.derive_candidate_digest(cwd)
        check("candidate digest is derivable from the repository", bool(digest))
        artifact = cwd / ".itd-memory" / "deploy-input.tar"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        emitted = gate.emit_deploy_input(cwd, artifact)
        gate.record_gate_pass(cwd, str(digest), "data-sensitive", str(emitted),
                              deploy_input_path=artifact)
        rc, decision, _ = invoke(
            cwd, bash("scp .itd-memory/deploy-input.tar " + REMOTE + ":/srv/"),
            home, entry=runner)
        check("gate pass bound to the current digest opens the deploy path",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")
        # ADR-008: with a VALID current pass the gate no longer re-judges the
        # shipment form — a different transport command on the same reviewed,
        # digest-bound candidate is allowed (was denied under the removed
        # form-analysis design).
        rc, decision, _ = invoke(cwd, bash(COPY_CMD), home, entry=runner)
        check("a valid current pass authorizes the reviewed deploy regardless "
              "of shipment form (ADR-008)",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")

        # 7. r53: HOME relocation must not move the trust anchor. The evil
        # HOME carries a permissive fake classifier that reports every
        # candidate routine; the REAL hook (no runner) must not consult it —
        # the account-database anchor resolves elsewhere, so the gated
        # candidate stays denied.
        evil_home = root / "evil-home"
        fake = (evil_home / ".claude" / "skills" / "deploy" / "scripts"
                / "itd_predeploy_gate.py")
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_text(
            "import json\n"
            "print(json.dumps({'riskClass': 'routine', 'gated': False,\n"
            "                  'gatePassRecorded': False}))\n",
            encoding="utf-8",
        )
        fresh = make_candidate(root / "evil-case", data_sensitive=True)
        rc, decision, _ = invoke(fresh, bash(SYNC_CMD), evil_home)
        check("r53: HOME pointing at a permissive fake install does not "
              "flip the verdict — the anchor is not environment-derived",
              rc == 2 and decision == "deny", f"rc={rc} decision={decision!r}")

    # 2. routine candidate is never touched
    with tempfile.TemporaryDirectory(prefix="itd-predeploy-routine-") as td:
        root = Path(td)
        home = root / "home"
        home.mkdir()
        installed_gate, key_path = write_gate_wrapper(home)
        runner = write_hook_runner(home, installed_gate)
        gate.GATE_MAC_KEY_PATH = key_path
        cwd = make_candidate(root, data_sensitive=False)
        rc, decision, _ = invoke(cwd, bash(SYNC_CMD), home, entry=runner)
        check("routine candidate is not blocked",
              rc == 0 and decision != "deny", f"rc={rc} decision={decision!r}")

    print(f"\n{passed} passed, {failed} failed")
    if not failed:
        print("verify_predeploy_gate: PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
