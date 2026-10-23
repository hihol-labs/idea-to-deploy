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


def snapshot(home: Path) -> dict[str, bytes]:
    return {path.relative_to(home).as_posix(): path.read_bytes() if path.is_file() else b"<dir>"
            for path in sorted(home.rglob("*"))}


def run(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(SCRIPT), "--codex-home", str(home)], capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def main() -> int:
    trusted = {"trusted_hash": "sha256:" + "a" * 64}
    with tempfile.TemporaryDirectory(prefix="itd-codex-trust-") as raw:
        tmp = Path(raw)

        home = home_with(tmp, "all", {key: trusted for key in KEYS})
        before = snapshot(home)
        result = run(home)
        check("every entry trusted: exit 0 and OK", result.returncode == 0 and "OK:" in result.stdout,
              result.stdout + result.stderr)
        check("the report writes nothing under the Codex home", snapshot(home) == before)

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
        check("no config.toml: unreadable input, exit 2", result.returncode == 2 and "config.toml" in result.stderr,
              result.stdout + result.stderr)

        old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 d.py --script x.sh"}]}]}}
        result = run(home_with(tmp, "versions", {key: trusted for key in KEYS}, {"1.9.0": old, "1.10.0": LAYOUT}))
        check("the newest installed version is compared (1.10.0 over 1.9.0)",
              result.returncode == 0 and "1.10.0" in result.stdout, result.stdout + result.stderr)

        result = run(home_with(tmp, "prerelease", {key: trusted for key in KEYS},
                               {"1.10.0-beta.2": old, "1.10.0": LAYOUT, "1.10.0-rc.1": old, "latest": old}))
        check("a release outranks its prereleases and a non-version directory is ignored",
              result.returncode == 0 and "/1.10.0/hooks" in result.stdout.replace("\\", "/"),
              result.stdout + result.stderr)
        result = run(home_with(tmp, "prerelease-only", {key: trusted for key in KEYS},
                               {"1.10.0-beta.2": LAYOUT, "1.10.0-beta.10": LAYOUT, "1.10.0-alpha": old}))
        check("prereleases compare by numeric identifiers (beta.10 over beta.2)",
              result.returncode == 0 and "1.10.0-beta.10" in result.stdout, result.stdout + result.stderr)
        result = run(home_with(tmp, "invalid-semver", {key: trusted for key in KEYS},
                               {"1.9.0": LAYOUT, "1.10.0-alpha..1": old, "1.10.0-01": old, "01.10.0": old,
                                "1.10": old}))
        check("directories that are not valid semantic versions are ignored",
              result.returncode == 0 and "/1.9.0/hooks" in result.stdout.replace("\\", "/"),
              result.stdout + result.stderr)

        for label, text in (("hooks.state is a string", '[hooks]\nstate = "x"\n'),
                            ("a hooks.state value is not a table", '[hooks.state]\n"k" = 1\n'),
                            ("hooks is a number", "hooks = 5\n"),
                            ("trusted_hash is a number", '[hooks.state."k"]\ntrusted_hash = 1\n'),
                            ("trusted_hash is empty", '[hooks.state."k"]\ntrusted_hash = ""\n'),
                            ("enabled is a string", '[hooks.state."k"]\nenabled = "false"\n')):
            shaped = home_with(tmp, "shape-" + str(len(label)), None)
            (shaped / "config.toml").write_text(text, encoding="utf-8")
            result = run(shaped)
            check(f"an unexpected TOML shape is unreadable input, exit 2 ({label})",
                  result.returncode == 2 and "Traceback" not in result.stderr, result.stdout + result.stderr)

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
