#!/usr/bin/env python3
"""Behaviour of scripts/itd_codex_hook_trust.py (plan session 5, BACKLOG P2 2026-10-22): the read-only report of the
Idea to Deploy hook entries Codex will not run - untrusted, switched off by position, or left behind by a layout
change - against the newest installed hooks.json, plus the trustStatus Codex itself reports through
`codex app-server` hooks/list (CODEX-HOOKS-0166-1: Codex 0.166 binds trust to the plugin contents, so a trusted_hash
alone is no proof). Temporary Codex homes and a fake Codex app-server only.
Usage: python3 tests/verify_codex_hook_trust.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

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
FAKE_SERVER = r"""
import json, os, sys
mode = os.environ.get("FAKE_CODEX_MODE", "trusted")
keys = json.loads(os.environ["FAKE_CODEX_KEYS"])
if sys.argv[1:] != ["app-server"]:
    sys.exit(64)
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("id") == 1:
        reply = {"id": 1, "result": {"userAgent": "fake"}}
    elif msg.get("id") == 2:
        if mode == "chatter":
            import time
            while True:  # notifications and foreign ids, never the answer
                print(json.dumps({"jsonrpc": "2.0", "method": "noise", "params": {}}), flush=True)
                print(json.dumps({"jsonrpc": "2.0", "id": 99, "result": {}}), flush=True)
                time.sleep(0.05)
        if mode == "error":
            reply = {"id": 2, "error": {"code": -32603, "message": "boom"}}
        else:
            status = {k: "trusted" for k in keys}
            if mode.startswith("modified:"):
                status[mode.split(":", 1)[1]] = "modified"
            hooks = [] if mode == "empty" else [
                {"key": "idea-to-deploy@personal:hooks/hooks.json:" + k, "trustStatus": v} for k, v in status.items()]
            if mode == "extra":  # an entry the local layout does not have, and a duplicate key with another status
                hooks.append({"key": "idea-to-deploy@personal:hooks/hooks.json:pre_tool_use:9:0",
                              "trustStatus": "modified"})
                hooks.append({"key": "idea-to-deploy@personal:hooks/hooks.json:pre_tool_use:0:0",
                              "trustStatus": "untrusted"})
            if msg["params"]["cwds"] != [os.environ["FAKE_CODEX_CWD"]]:
                reply = {"id": 2, "error": {"code": -32602, "message": "unexpected cwds " + repr(msg["params"]["cwds"])}}
                print(json.dumps({"jsonrpc": "2.0", **reply}), flush=True)
                continue
            reply = {"id": 2, "result": {"data": [{"cwd": msg["params"]["cwds"][0], "hooks": hooks}]}}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", **reply}), flush=True)
"""


def fake_codex(tmp: Path) -> str:
    server = tmp / "fake_codex_server.py"
    server.write_text(FAKE_SERVER, encoding="utf-8")
    if os.name == "nt":
        import ctypes  # cmd.exe reads a batch file in the OEM code page; a UTF-8 non-ASCII path would break
        launcher = tmp / "fake_codex.cmd"
        launcher.write_text(f'@"{sys.executable}" -B "{server}" %*\r\n',
                            encoding=f"cp{ctypes.windll.kernel32.GetOEMCP()}")
    else:
        launcher = tmp / "fake_codex"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" -B "{server}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return str(launcher)


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


CODEX = ""
PROJECT = Path()


def run(home: Path, mode: str = "trusted", codex: str | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, "-B", str(SCRIPT), "--codex-home", str(home), "--cwd", str(PROJECT)]
    if codex != "":
        argv += ["--codex", codex or CODEX]
    env = dict(os.environ, FAKE_CODEX_MODE=mode, FAKE_CODEX_KEYS=json.dumps(KEYS), FAKE_CODEX_CWD=str(PROJECT))
    if codex == "":
        env["PATH"] = str(Path(sys.executable).parent)
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                          env=env)


def main() -> int:
    trusted = {"trusted_hash": "sha256:" + "a" * 64}
    global CODEX, PROJECT
    with tempfile.TemporaryDirectory(prefix="itd-codex-trust-") as raw:
        tmp = Path(raw)
        CODEX = fake_codex(tmp)
        PROJECT = tmp / "project"
        PROJECT.mkdir()

        home = home_with(tmp, "all", {key: trusted for key in KEYS})
        before = snapshot(home)
        result = run(home)
        check("every entry trusted: exit 0 and OK", result.returncode == 0 and "OK:" in result.stdout,
              result.stdout + result.stderr)
        check("the report writes nothing under the Codex home", snapshot(home) == before)

        # CODEX-HOOKS-0166-1: every trusted_hash recorded, but the plugin contents changed - Codex skips the entry
        result = run(home, "modified:pre_tool_use:0:0")
        check("a trusted_hash with changed plugin contents is reported from Codex's trustStatus, exit 1",
              result.returncode == 1
              and "modified pre_tool_use:0:0 pii-egress-guard.sh (.*) (Codex trustStatus)" in result.stdout,
              result.stdout + result.stderr)
        check("the fix names the re-trust after a plugin update and the Windows daemon bypass",
              "Trust all and continue" in result.stdout and "codex --no-daemon" in result.stdout, result.stdout)
        result = run(home, "extra")
        check("an extra or duplicate Codex entry of the plugin that is not trusted is named, never folded into OK",
              result.returncode == 1 and "modified pre_tool_use:9:0" in result.stdout
              and "untrusted pre_tool_use:0:0" in result.stdout and "OK:" not in result.stdout,
              result.stdout + result.stderr)
        result = run(home, "empty")
        check("hooks/list is asked for the project directory (--cwd), not the Codex home",
              run(home, "trusted").returncode == 0)
        check("Codex listing none of the plugin's hooks is a finding, exit 1",
              result.returncode == 1 and "unlisted: Codex lists no hook" in result.stdout,
              result.stdout + result.stderr)
        result = run(home, codex="")
        check("without a Codex executable the content trust is unverified, never OK (exit 1)",
              result.returncode == 1 and "unverified content trust" in result.stdout and "OK:" not in result.stdout,
              result.stdout + result.stderr)
        result = run(home, "error")
        check("a Codex app-server error is unreadable input, exit 2",
              result.returncode == 2 and "cannot read the Codex hook trust" in result.stderr
              and "boom" in result.stderr,
              result.stdout + result.stderr)
        started = time.monotonic()
        run(home)
        overhead = time.monotonic() - started  # interpreter, launcher and fake server start-up on this host
        argv = [sys.executable, "-B", str(SCRIPT), "--codex-home", str(home), "--cwd", str(PROJECT), "--codex", CODEX,
                "--timeout", "3"]
        env = dict(os.environ, FAKE_CODEX_MODE="chatter", FAKE_CODEX_KEYS=json.dumps(KEYS),
                   FAKE_CODEX_CWD=str(PROJECT))
        try:
            started = time.monotonic()
            result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=60, env=env)
            elapsed = time.monotonic() - started
            ok = result.returncode == 2 and "no answer" in result.stderr and elapsed < 3 + overhead + 2
            detail = f"elapsed {elapsed:.1f}s, overhead {overhead:.1f}s; " + result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            ok, detail = False, "the trust check hung on a chattering app-server"
        check("an app-server that never answers (notifications, foreign ids) hits the overall deadline, exit 2",
              ok, detail)
        for bad in ("inf", "nan", "0", "-1", "x"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--codex-home", str(home), "--codex", CODEX,
                                     "--timeout", bad], capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=60,
                                    env=dict(os.environ, FAKE_CODEX_MODE="trusted", FAKE_CODEX_KEYS=json.dumps(KEYS),
                                             FAKE_CODEX_CWD=str(PROJECT)))
            check(f"--timeout {bad} is a usage error before Codex starts, exit 2 without a traceback",
                  result.returncode == 2 and "Traceback" not in result.stderr and "timeout" in result.stderr,
                  result.stdout + result.stderr)
        result = run(home, codex=str(tmp / "no-such-codex"))
        check("no finding, failure, timeout or usage path writes under the Codex home or the project",
              snapshot(home) == before and not any(PROJECT.iterdir()))
        check("a missing --codex executable is unreadable input, exit 2",
              result.returncode == 2 and "Traceback" not in result.stderr, result.stdout + result.stderr)

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
