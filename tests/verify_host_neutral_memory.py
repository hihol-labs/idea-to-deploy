#!/usr/bin/env python3
"""Behavioural proof that `.itd-memory/` is the cross-host continuity source."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks"
passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    print(f"{'PASS' if condition else 'FAIL'}  {name}"
          + (f" [{detail}]" if detail and not condition else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def load_hook(filename: str, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(HOOKS / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def legacy_dir(home: Path, cwd: Path) -> Path:
    munged = re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))
    return home / ".claude" / "projects" / munged / "memory"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="itd-host-neutral-memory-"))
    home = tmp / "empty-host-home"
    home.mkdir()
    old_home = os.environ.get("HOME")
    old_profile = os.environ.get("USERPROFILE")
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    try:
        preflight = load_hook("pre-flight-check.sh", "itd_h2_preflight")
        session_open = load_hook("session-open-diagnostic.sh", "itd_h2_session_open")
        handoff = load_hook("handoff-readiness.sh", "itd_h2_handoff")
        state_guard = load_hook("state-guard.sh", "itd_h2_state_guard")

        project = tmp / "project"
        local = project / ".itd-memory"
        subdir = project / "src" / "nested"
        local.mkdir(parents=True)
        subdir.mkdir(parents=True)
        (local / "session_2026-07-15.md").write_text(
            "LOCAL-CHECKPOINT\nNext: local-next\n", encoding="utf-8")
        (local / "MEMORY.md").write_text(
            "- [next session](session_2026-07-15.md) — LOCAL-INDEX\n",
            encoding="utf-8")
        (local / ".active-session.lock").write_text(json.dumps({
            "timestamp": time.time(), "session": "local-owner", "pid": 1,
            "branch": "h2", "project": str(project), "note": "local"}),
            encoding="utf-8")

        mirror = legacy_dir(home, project)
        mirror.mkdir(parents=True)
        (mirror / "session_2026-07-14.md").write_text(
            "STALE-MIRROR", encoding="utf-8")
        (mirror / "MEMORY.md").write_text("STALE-MIRROR-INDEX", encoding="utf-8")

        check("pre-flight resolves ancestor `.itd-memory/` first",
              preflight.find_project_memory_dir(subdir) == local)
        check("session-open resolves ancestor `.itd-memory/` first",
              session_open.find_project_memory_dir(subdir) == local)
        check("handoff-readiness resolves ancestor `.itd-memory/` first",
              handoff.find_project_memory_dir(subdir) == local)
        check("state-guard resolves ancestor `.itd-memory/` first",
              state_guard.find_project_memory_dir(subdir) == local)
        check("state-guard local lookup survives deep=False",
              state_guard.find_project_memory_dir(subdir, deep=False) == local)

        diagnostic = session_open.build_diagnostic(project) or ""
        check("session diagnostic reads the local checkpoint",
              "LOCAL-CHECKPOINT" in diagnostic)
        check("stale host mirror cannot override local checkpoint",
              "STALE-MIRROR" not in diagnostic)
        check("pre-flight index is local, not host-private",
              "LOCAL-INDEX" in preflight.memory_index_context(local)
              and "STALE-MIRROR" not in preflight.memory_index_context(local))
        age = handoff.latest_session_age_min(
            handoff.find_project_memory_dir(project))
        check("handoff freshness is derived from local checkpoint",
              age is not None and age < 2)

        legacy_project = tmp / "legacy-only"
        legacy_project.mkdir()
        legacy = legacy_dir(home, legacy_project)
        legacy.mkdir(parents=True)
        check("Claude-private memory remains a read-only compatibility fallback",
              preflight.find_project_memory_dir(legacy_project) == legacy)

        empty_project = tmp / "no-memory"
        empty_project.mkdir()
        check("absence of both stores is reported as no continuity",
              preflight.find_project_memory_dir(empty_project) is None
              and session_open.find_project_memory_dir(empty_project) is None
              and handoff.find_project_memory_dir(empty_project) is None
              and state_guard.find_project_memory_dir(empty_project) is None)

        missing_state = tmp / "missing-state"
        missing_local = missing_state / ".itd-memory"
        missing_local.mkdir(parents=True)
        (missing_local / "MEMORY.md").write_text("index only", encoding="utf-8")
        private_state = legacy_dir(home, missing_state)
        private_state.mkdir(parents=True)
        (private_state / "GOAL.json").write_text(
            '{"goal":"PRIVATE-FALSE-PASS"}', encoding="utf-8")
        check("missing local state cannot be masked by private host state",
              preflight.itd_state_context(missing_state) == "")

        # Upgrade edge: existing .itd-memory may contain only STATE/GOAL while
        # historical narrative checkpoints still live in Claude-private memory.
        upgrade = tmp / "partial-local-upgrade"
        upgrade_local = upgrade / ".itd-memory"
        upgrade_local.mkdir(parents=True)
        (upgrade_local / "STATE.json").write_text(
            '{"nextAction":"LOCAL-STATE-WINS"}', encoding="utf-8")
        upgrade_legacy = legacy_dir(home, upgrade)
        upgrade_legacy.mkdir(parents=True)
        (upgrade_legacy / "session_2026-07-13.md").write_text(
            "LEGACY-NARRATIVE-HISTORY", encoding="utf-8")
        (upgrade_legacy / "MEMORY.md").write_text(
            "- [next session](session_2026-07-13.md) — legacy plan",
            encoding="utf-8")
        upgrade_subdir = upgrade / "src" / "nested"
        upgrade_subdir.mkdir(parents=True)
        upgrade_diagnostic = session_open.build_diagnostic(upgrade_subdir) or ""
        check("partial-local upgrade layers missing narrative from legacy",
              "LEGACY-NARRATIVE-HISTORY" in upgrade_diagnostic
              and "legacy host-memory fallback" in upgrade_diagnostic)
        check("partial-local upgrade keeps control state strictly local",
              preflight.find_local_project_memory_dir(upgrade) == upgrade_local
              and state_guard.find_project_memory_dir(upgrade) == upgrade_local)

        # A private-only fresh memo must not make a dirty project handoff-ready.
        readiness = tmp / "private-only-readiness"
        readiness_local = readiness / ".itd-memory"
        readiness_local.mkdir(parents=True)
        (readiness_local / "STATE.json").write_text("{}", encoding="utf-8")
        readiness_legacy = legacy_dir(home, readiness)
        readiness_legacy.mkdir(parents=True)
        (readiness_legacy / "session_2026-07-15.md").write_text(
            "fresh but private", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=readiness, check=True,
                       capture_output=True, text=True)
        (readiness / "dirty.txt").write_text("dirty", encoding="utf-8")
        env = dict(os.environ)
        env.update({"HOME": str(home), "USERPROFILE": str(home),
                    "ITD_HANDOFF_RATE_MIN": "0"})
        readiness_run = subprocess.run(
            [sys.executable, str(HOOKS / "handoff-readiness.sh")],
            input=json.dumps({"session_id": "h2-private-readiness",
                              "cwd": str(readiness), "stop_hook_active": False}),
            capture_output=True, text=True, cwd=readiness, env=env, timeout=30)
        check("fresh private mirror cannot suppress missing-local readiness hint",
              readiness_run.returncode == 0
              and "HANDOFF-READINESS" in readiness_run.stdout)

        adapter = json.loads((ROOT / "docs" / "host-adapters.json").read_text(
            encoding="utf-8"))
        check("adapter registry declares one canonical continuity path",
              adapter.get("methodologyCore", {}).get("canonicalContinuity")
              == ".itd-memory/")
        save_skill = (ROOT / "skills" / "session-save" / "SKILL.md").read_text(
            encoding="utf-8")
        adopt_skill = (ROOT / "skills" / "adopt" / "SKILL.md").read_text(
            encoding="utf-8")
        check("session-save writes the project-local canonical directory",
              'MEM_DIR="$(git rev-parse --show-toplevel)/.itd-memory"' in save_skill
              and "private path" in save_skill)
        check("adopt initializes local continuity without private suppression",
              'mkdir -p "$PROJECT_ROOT/.itd-memory"' in adopt_skill
              and "never choose it over local files" in adopt_skill)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        if old_profile is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = old_profile

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
