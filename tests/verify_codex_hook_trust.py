#!/usr/bin/env python3
"""Behaviour of scripts/itd_codex_hook_trust.py (plan session 5, BACKLOG P2 2026-10-22): the read-only report of the
Idea to Deploy hook entries Codex will not run - untrusted, switched off by position, or left behind by a layout
change - against the newest installed hooks.json. Temporary Codex homes only.
Usage: python3 tests/verify_codex_hook_trust.py
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "itd_codex_hook_trust.py"
PLUGIN = "idea-to-deploy@personal"
LAYOUT = {"hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 d.py --script pre-flight-check.sh"}]}],
    "PreToolUse": [
        {"matcher": ".*", "hooks": [{"type": "command", "command": "python3 d.py --script pii-egress-guard.sh"}]},
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 d.py --script careful.sh"},
                                      {"type": "command", "command": "python3 d.py --script completion-gate.sh"}]},
    ],
}}
KEYS = ["user_prompt_submit:0:0", "pre_tool_use:0:0", "pre_tool_use:1:0", "pre_tool_use:1:1"]

passed = failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    passed += ok
    failed += not ok
    print(("PASS " if ok else "FAIL ") + label + ("" if ok else f": {detail}"))


def home_with(tmp: Path, name: str, state: dict[str, dict] | None, layouts: dict[str, dict] | None = None) -> Path:
    home = tmp / name
    for version, layout in (layouts or {"1.10.0": LAYOUT}).items():
        hooks = home / "plugins" / "cache" / "personal" / "idea-to-deploy" / version / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "hooks.json").write_text(json.dumps(layout), encoding="utf-8")
    if state is not None:
        lines = ['model = "gpt"', "", "[hooks.state]", ""]
        for key, record in state.items():
            lines.append(f'[hooks.state."{PLUGIN}:hooks/hooks.json:{key}"]')
            lines += [f"{field} = {json.dumps(value)}" for field, value in record.items()]
            lines.append("")
        (home / "config.toml").write_text("\n".join(lines), encoding="utf-8")
    return home


def run(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(SCRIPT), "--codex-home", str(home)], capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def main() -> int:
    trusted = {"trusted_hash": "sha256:" + "a" * 64}
    with tempfile.TemporaryDirectory(prefix="itd-codex-trust-") as raw:
        tmp = Path(raw)

        home = home_with(tmp, "all", {key: trusted for key in KEYS})
        before = (home / "config.toml").read_bytes()
        result = run(home)
        check("every entry trusted: exit 0 and OK", result.returncode == 0 and "OK:" in result.stdout,
              result.stdout + result.stderr)
        check("the report never writes config.toml", (home / "config.toml").read_bytes() == before)

        state = {key: trusted for key in KEYS[:2]}
        state["pre_tool_use:1:1"] = {"enabled": False}
        state["pre_tool_use:2:0"] = trusted
        result = run(home_with(tmp, "gaps", state))
        out = result.stdout
        check("findings: exit 1", result.returncode == 1, out + result.stderr)
        check("an entry without trust is named with its script and matcher",
              "untrusted pre_tool_use:1:0 careful.sh (Bash)" in out, out)
        check("a positional switch-off is named", "disabled pre_tool_use:1:1 completion-gate.sh (Bash)" in out, out)
        check("a disabled entry without trust is also untrusted",
              "untrusted pre_tool_use:1:1 completion-gate.sh (Bash)" in out, out)
        check("a key no entry has any more is stale", "stale pre_tool_use:2:0" in out, out)
        check("a trusted entry is not reported", "pii-egress-guard" not in out, out)
        check("the fix names /hooks and the ITD list", "/hooks" in out and "itd-disabled-hooks.txt" in out, out)

        result = run(home_with(tmp, "noconfig", None))
        check("no config.toml: every entry is untrusted", result.returncode == 1
              and sum(line.startswith("untrusted ") for line in result.stdout.splitlines()) == len(KEYS),
              result.stdout)

        old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 d.py --script x.sh"}]}]}}
        result = run(home_with(tmp, "versions", {key: trusted for key in KEYS}, {"1.9.0": old, "1.10.0": LAYOUT}))
        check("the newest installed version is compared (1.10.0 over 1.9.0)",
              result.returncode == 0 and "1.10.0" in result.stdout, result.stdout + result.stderr)

        empty = tmp / "empty"
        empty.mkdir()
        result = run(empty)
        check("no installed plugin: exit 2", result.returncode == 2 and "cannot read" in result.stderr,
              result.stdout + result.stderr)
        broken = home_with(tmp, "broken", {})
        (broken / "config.toml").write_text("[hooks.state\n", encoding="utf-8")
        result = run(broken)
        check("malformed config.toml: exit 2", result.returncode == 2, result.stdout + result.stderr)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
