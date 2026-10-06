#!/usr/bin/env python3
"""Behavioral oracle for the sync surface of scripts/sync-to-active.sh.

Two contracts, both found by closing GPG-004 follow-ups:
  * the plugin manifest `.claude-plugin/plugin.json` is verified to exist but
    was never synced, so the installed manifest was aligned by hand;
  * `__pycache__`/`*.pyc` bytecode entered the skills drift scan, so the only
    reported drift on a fully synced install was pure noise.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts/sync-to-active.sh"
VERIFY_SYNC = ROOT / "scripts/verify-sync-to-active.sh"


def run_sync(active: Path, *, apply: bool = False) -> str:
    """Run the real sync script against an isolated install.

    apply=False is the dry-run plan; apply=True exercises the actual copy
    paths.  Both are confined to the fixture by CLAUDE_HOME — nothing here
    may touch the developer's real ~/.claude.
    """
    environment = dict(os.environ)
    environment["CLAUDE_HOME"] = str(active)
    completed = subprocess.run(
        ["bash", str(SYNC)] + ([] if apply else ["--check"]),
        cwd=str(ROOT), env=environment, capture_output=True, timeout=600,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"sync failed ({completed.returncode}): "
            f"{completed.stderr.decode('utf-8', 'replace')[-400:]}"
        )
    return (completed.stdout + completed.stderr).decode("utf-8", "replace")


def main() -> int:
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(message)

    with tempfile.TemporaryDirectory(prefix="itd-sync-oracle-") as raw:
        fixture = Path(raw)

        # 1. Manifest: a fresh install must be told the manifest is missing,
        #    not silently left to hand alignment.
        empty_install = fixture / "empty"
        empty_install.mkdir()
        fresh = run_sync(empty_install)
        check(".claude-plugin/plugin.json" in fresh,
              "the dry-run plan never mentions the plugin manifest")
        check("would add" in fresh.split(".claude-plugin/plugin.json")[0][-80:]
              or "would sync" in fresh.split(".claude-plugin/plugin.json")[0][-80:],
              "the manifest is mentioned but not as a planned sync action")

        # 2. Manifest content drift on an otherwise synced install is reported.
        stale_install = fixture / "stale"
        (stale_install / ".claude-plugin").mkdir(parents=True)
        (stale_install / ".claude-plugin/plugin.json").write_text(
            json.dumps({"name": "stale-hand-aligned-copy"}), encoding="utf-8"
        )
        stale = run_sync(stale_install)
        check(".claude-plugin/plugin.json" in stale,
              "manifest drift on an installed copy is not reported")

        # 3. Bytecode is not drift: an install whose skills match the repo
        #    except for __pycache__ must read as clean, not "~1 updated".
        synced_install = fixture / "synced"
        (synced_install / "skills").mkdir(parents=True)
        shutil.copytree(ROOT / "skills/_shared",
                        synced_install / "skills/_shared")
        shutil.rmtree(synced_install / "skills/_shared/__pycache__",
                      ignore_errors=True)
        cache = synced_install / "skills/_shared/__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "itd_free_reviewer_producer.cpython-99.pyc").write_bytes(
            b"stale bytecode from another interpreter"
        )
        bytecode = run_sync(synced_install)
        check("would sync /_shared (drift detected)" not in bytecode,
              "__pycache__ bytecode still reads as skill drift")

        # 4. Apply mode really writes the manifest, not just plans it.
        applied_install = fixture / "applied"
        applied_install.mkdir()
        run_sync(applied_install, apply=True)
        installed = applied_install / ".claude-plugin/plugin.json"
        check(installed.is_file(),
              "apply mode never installed the plugin manifest")
        check(installed.read_bytes()
              == (ROOT / ".claude-plugin/plugin.json").read_bytes(),
              "the installed manifest does not match the repo manifest")
        # ...and a second apply is a clean no-op, not a perpetual rewrite.
        again = run_sync(applied_install, apply=True)
        check("manifest: .claude-plugin/plugin.json unchanged" in again,
              "a synced manifest is not reported as unchanged on re-run")

        # 4b. ADR-012 owner opt-out: a hook listed in itd-disabled-hooks.txt is
        #     not registered, the others still are, and a re-run does not
        #     bring it back or rewrite settings.json again.
        optout_install = fixture / "optout"
        optout_install.mkdir()

        def registered(install: Path) -> list[str]:
            data = json.loads((install / "settings.json").read_text(encoding="utf-8"))
            return [h.get("command", "") for groups in data.get("hooks", {}).values()
                    for g in groups for h in g.get("hooks", [])]

        # an install synced BEFORE the opt-out file existed has the hooks registered...
        run_sync(optout_install, apply=True)
        check(any("check-tool-skill.sh" in c for c in registered(optout_install)),
              "fixture precondition: a plain sync registers check-tool-skill.sh")
        # ...and the next sync after the file appears removes them (BOM, duplicate and typo included)
        (optout_install / "itd-disabled-hooks.txt").write_text(
            "﻿check-review-before-commit.sh  # BOM first, trailing comment\n# owner opt-out\n"
            "check-tool-skill.sh\ncheck-tool-skill.sh\ncheck-tool-skil\n",
            encoding="utf-8",
        )
        optout = run_sync(optout_install, apply=True)
        check("names no registered hook: check-tool-skil" in optout,
              "a misspelled name in the opt-out list is accepted silently")
        commands = registered(optout_install)
        check(not any("check-tool-skill.sh" in c for c in commands),
              "a hook listed in itd-disabled-hooks.txt is still registered")
        check(not any("check-review-before-commit.sh" in c for c in commands),
              "a listed hook with a trailing comment is still registered")
        check(any("check-predeploy-gate.sh" in c for c in commands),
              "the opt-out also dropped a hook that was not listed")
        settings_before = (optout_install / "settings.json").read_bytes()
        rerun = run_sync(optout_install, apply=True)
        check((optout_install / "settings.json").read_bytes() == settings_before,
              "a re-run with the same opt-out list rewrote settings.json")
        check(not any("check-tool-skill.sh" in c for c in registered(optout_install)),
              "a re-run brought a disabled hook back")
        check("hooks disabled by itd-disabled-hooks.txt: 2" in rerun,
              "the sync output does not count the distinct hooks the opt-out list disables")

    # 5. The manifest stays on the verify-sync surface, so a future edit that
    #    drops it from the sync script fails loudly instead of silently.
    verify_source = VERIFY_SYNC.read_text(encoding="utf-8")
    check(".claude-plugin/plugin.json" in verify_source,
          "verify-sync-to-active.sh does not police the plugin manifest")
    completed = subprocess.run(
        ["bash", str(VERIFY_SYNC)], cwd=str(ROOT),
        capture_output=True, timeout=120,
    )
    check(completed.returncode == 0,
          "verify-sync-to-active.sh reports drift: "
          + completed.stdout.decode("utf-8", "replace")[-300:])

    print(json.dumps({"status": "PASSED", "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
