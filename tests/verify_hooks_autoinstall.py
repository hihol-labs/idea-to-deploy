#!/usr/bin/env python3
"""G-004 HOOKS-AUTOINSTALL-1 oracle: /adopt and /project offer to install enforcement hooks.

`skills/_shared/itd_project_hooks.py` merges the project settings template
(`skills/adopt/references/project-settings-template.json`) into a target project's
`.claude/settings.json`, and only after explicit confirmation. On real subprocess runs in
isolated temp dirs this oracle checks:

- no arguments: exit 0, no output, nothing created;
- `plan` never writes (absent file stays absent; an existing file keeps bytes and mtime) and
  names what would be added;
- `apply` without `--yes` is refused (non-zero) and writes nothing - the "declined" path;
- `apply --yes` on an absent file creates it with every template hook as an exact
  (event, matcher, command) triple, the plugin hooks dir substituted, no `_comment_*` keys,
  and the template `permissions.ask` rules;
- a second `apply --yes` is byte- and mtime-identical (idempotent, no duplicates);
- an existing file keeps the user's own hooks, other keys and permissions; hooks already
  present are not duplicated; a script registered under several matchers of one event
  (state-guard.sh) is registered under each of them;
- every malformed settings shape in `BAD_SETTINGS` (bad JSON, non-object, event not a list,
  entry without a `hooks` list, hook without a non-empty string `command`, non-string matcher, bad
  `permissions`) and every malformed template in `BAD_TEMPLATES` (including an empty one) is
  refused by BOTH `plan` and `apply --yes` with the shared diagnostic contract (`refused`:
  non-zero, WHY and FIX, no traceback) and no byte written; so are a symlink-loop `--root` and
  `apply` without `--yes`;
- NaN/Infinity (literal or an overflowing number such as 1e999), an empty file and deeply
  nested JSON are refused the same way; so is a settings path that is a directory or a FIFO
  (no hang); an unreadable user-level settings dir only warns; a failure after the write says
  the file was already written; so are a `.claude`
  that is a regular file, read-only or unreadable, and an overlong `--root` (every unforeseen
  failure is a WHY/FIX refusal, never a traceback); deeply nested user-level settings only warn;
- a quoted user-level path containing a space is one path; a hooks dir whose name holds a quote
  and a backslash is substituted into the parsed template as data;
- `plan` on a file that still needs a merge names it and changes no byte or mtime; no arguments
  writes nothing in the project, the working directory or HOME;
- a hook whose script is registered in the user-level settings from an idea-to-deploy hooks
  dir (the `hooks` dir next to that settings file, also in the Windows python-wrapper form, or
  the plugin hooks dir) is not duplicated at project level, the other hooks and the permissions
  still are; a same-named script from an unrelated directory or another project's
  `.claude/hooks` does not count; the user-level file is never written;
- the plugin hooks dir is recognised in the user-level settings however it is spelled: with a
  `..` segment, as `$HOME/...`, or when `--hooks-dir` is a symlink;
- a symlinked settings file whose target is inside the project is updated through its target
  (the link survives) and `plan` names the real target; a settings file or `.claude` dir that
  resolves outside the project - existing or dangling - is refused by both `plan` and `apply`
  and nothing is created or changed outside it;
- a symlink loop at `settings.json` or at the `.claude` dir is refused (WHY/FIX, no traceback)
  and the link is kept;
- unreadable user-level settings are not silently ignored: `plan` warns;
- a `--root` that is not a directory is refused without creating anything;
- `skills/adopt/SKILL.md` and `skills/project/SKILL.md` END with an explicit confirmation
  step (their last `### Step` heading) that runs the helper's `plan`, asks, and whose every
  numbered item running `apply --yes` starts with an «да» condition while the single «нет» item
  forbids `apply` and leaves the file untouched. This is a STRUCTURAL check of the item text by
  regular expressions, not a check of its meaning: an item deliberately phrased to contradict
  itself (for example quoting the ban words while telling the agent to apply anyway) can pass;
  such wording is caught by review, not by this oracle;
- neither README carries the phrase "not auto-installed".

`--mutations` copies the helper, applies independent mutations and requires each to turn
the suite red. `--helper PATH` runs the suite against another helper copy.

Run: sh skills/_shared/itd_py.sh tests/verify_hooks_autoinstall.py [--mutations]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "skills" / "_shared" / "itd_project_hooks.py"
TEMPLATE = REPO / "skills" / "adopt" / "references" / "project-settings-template.json"
PLACEHOLDER = "{{PLUGIN_HOOKS_DIR}}"

PASSES = 0


def check(fails: list[str], ok: bool, label: str) -> None:
    global PASSES
    if ok:
        PASSES += 1
    else:
        fails.append(label)
        print(f"  FAIL {label}")


def refused(r: subprocess.CompletedProcess[str]) -> bool:
    """The diagnostic contract of every refusal: non-zero, WHY and FIX, no traceback."""
    return (r.returncode != 0 and "WHY:" in r.stderr and "FIX:" in r.stderr
            and "Traceback" not in r.stderr)


BAD_SETTINGS = (
    ("malformed JSON", "{not json\n"),
    ("non-object JSON", "[1, 2]\n"),
    ("hooks not an object", '{"hooks": []}\n'),
    ("event not a list", '{"hooks": {"Stop": {}}}\n'),
    ("event list of non-objects", '{"hooks": {"Stop": [1]}}\n'),
    ("entry without hooks", '{"hooks": {"PreToolUse": [{}]}}\n'),
    ("entry hooks null", '{"hooks": {"PreToolUse": [{"hooks": null}]}}\n'),
    ("entry hooks not a list", '{"hooks": {"Stop": [{"hooks": {}}]}}\n'),
    ("hook not an object", '{"hooks": {"Stop": [{"hooks": ["x"]}]}}\n'),
    ("hook without command", '{"hooks": {"Stop": [{"hooks": [{}]}]}}\n'),
    ("hook command not a string", '{"hooks": {"Stop": [{"hooks": [{"command": 1}]}]}}\n'),
    ("hook command empty", '{"hooks": {"Stop": [{"hooks": [{"command": " "}]}]}}\n'),
    ("matcher not a string", '{"hooks": {"Bash": [{"matcher": 5, "hooks": []}]}}\n'),
    ("permissions not an object", '{"permissions": []}\n'),
    ("permissions.ask not a list", '{"permissions": {"ask": "x"}}\n'),
    ("permissions.ask non-string", '{"permissions": {"ask": [1]}}\n'),
    ("NaN constant", '{"x": NaN}\n'),
    ("overflowing number", '{"a": 1e999, "permissions": {"ask": []}}\n'),
    ("negative overflowing number", '{"a": -1e999}\n'),
    ("Infinity constant", '{"x": Infinity}\n'),
    ("empty file", ""),
    ("deeply nested JSON", '{"x": ' + "[" * 100000 + "]" * 100000 + "}\n"),
)
BAD_TEMPLATES = (
    ("array template", "[1]\n"),
    ("empty template", "{}\n"),
    ("template without hooks", '{"permissions": {"ask": []}}\n'),
    ("template with no hook", '{"hooks": {}}\n'),
    ("template entry without hooks", '{"hooks": {"Stop": [{}]}}\n'),
    ("template entry hooks null", '{"hooks": {"Stop": [{"hooks": null}]}}\n'),
    ("template hook without command", '{"hooks": {"Stop": [{"hooks": [{}]}]}}\n'),
    ("malformed template JSON", "{not json\n"),
    ("overflowing number in template", '{"hooks": {"Stop": [{"hooks": [{"command": "x.sh", "timeout": 1e999}]}]}}\n'),
    ("NaN in template", '{"hooks": {"Stop": [{"hooks": [{"command": "x.sh", "timeout": NaN}]}]}}\n'),
    ("deeply nested template", '{"x": ' + "[" * 100000 + "]" * 100000 + "}\n"),
)


def digest(path: Path) -> tuple[str, int] | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


def run(helper: Path, *args: str, home: str | None = None,
        cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if home:
        env["HOME"] = home
    try:
        return subprocess.run([sys.executable, str(helper), *args], capture_output=True,
                              text=True, timeout=60, env=env, cwd=cwd, check=False)
    except subprocess.TimeoutExpired:  # a hang is a failure of the contract, not of the oracle
        return subprocess.CompletedProcess([str(helper), *args], 124, "", "TIMEOUT")


def template_triples(hooks_dir: str) -> list[tuple[str, str, str]]:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    out = []
    for event, entries in data["hooks"].items():
        for entry in entries:
            for hook in entry["hooks"]:
                out.append((event, entry.get("matcher", ""),
                            hook["command"].replace(PLACEHOLDER, hooks_dir)))
    return out


def triples(settings: dict) -> list[tuple[str, str, str]]:
    out = []
    for event, entries in (settings.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                out.append((event, entry.get("matcher", ""), hook.get("command", "")))
    return out


def template_ask() -> list[str]:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))["permissions"]["ask"]


class Box:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="itd-hooks-autoinstall-"))
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.hooks = self.tmp / "plugin" / "hooks"
        self.hooks.mkdir(parents=True)
        self.home = self.tmp / "home"
        self.user = self.home / ".claude" / "settings.json"
        self.user_hooks = self.user.parent / "hooks"
        self.user.parent.mkdir(parents=True)
        self.user.write_text('{"model": "opus"}\n', encoding="utf-8")
        self.settings = self.root / ".claude" / "settings.json"

    def args(self, *extra: str) -> list[str]:
        return ["--root", str(self.root), "--hooks-dir", str(self.hooks),
                "--user-settings", str(self.user), *extra]

    def close(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def suite(helper: Path) -> list[str]:
    fails: list[str] = []
    if not helper.is_file():
        check(fails, False, f"helper missing: {helper.relative_to(REPO) if helper.is_relative_to(REPO) else helper}")
    else:
        suite_helper(helper, fails)
    suite_docs(fails)
    return fails


def suite_helper(helper: Path, fails: list[str]) -> None:
    box = Box()
    try:
        user_before = digest(box.user)
        hd = box.hooks.absolute().as_posix()
        expected = template_triples(hd)

        cwd = box.tmp / "cwd"
        cwd.mkdir()
        r = run(helper, home=str(box.home), cwd=str(cwd))
        check(fails, r.returncode == 0 and not r.stdout and not r.stderr, "no-arg: silent exit 0")
        check(fails, not (box.root / ".claude").exists() and not any(cwd.iterdir())
              and sorted(p.name for p in box.home.rglob("*")) == [".claude", "settings.json"]
              and digest(box.user) == user_before, "no-arg: nothing created in root, cwd or HOME")

        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0, f"plan absent: exit 0 (got {r.returncode}: {r.stderr.strip()[:200]})")
        check(fails, not box.settings.exists(), "plan absent: file not created")
        check(fails, "create" in r.stdout and "check-tool-skill.sh" in r.stdout,
              "plan absent: names create and the hooks to add")

        r = run(helper, "apply", *box.args())
        check(fails, refused(r), "apply without --yes: refused (WHY/FIX, no traceback)")
        check(fails, not box.settings.exists(), "apply without --yes: file not created")

        r = run(helper, "apply", *box.args("--yes"))
        check(fails, r.returncode == 0, f"apply --yes absent: exit 0 (got {r.returncode}: {r.stderr.strip()[:200]})")
        data = json.loads(box.settings.read_text(encoding="utf-8")) if box.settings.exists() else {}
        got = triples(data)
        check(fails, sorted(got) == sorted(expected), "apply --yes absent: exactly the template triples")
        text = box.settings.read_text(encoding="utf-8") if box.settings.exists() else ""
        check(fails, PLACEHOLDER not in text and "_comment" not in text,
              "apply --yes absent: placeholder substituted, comments stripped")
        check(fails, (data.get("permissions") or {}).get("ask") == template_ask(),
              "apply --yes absent: permissions.ask from template")
        guard = [t for t in expected if t[2].endswith("state-guard.sh") and t[0] == "PreToolUse"]
        check(fails, len(guard) >= 2 and all(t in got for t in guard),
              "state-guard.sh registered under each of its PreToolUse matchers")

        before = digest(box.settings)
        r = run(helper, "apply", *box.args("--yes"))
        check(fails, r.returncode == 0 and digest(box.settings) == before,
              "second apply --yes: byte- and mtime-identical")
        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0 and digest(box.settings) == before,
              "plan on existing: byte- and mtime-identical")

        # Existing user settings: preserved, merged, no duplicates.
        mine = {"matcher": "Bash", "hooks": [{"type": "command", "command": "/opt/my-guard.sh"}]}
        present = expected[0]
        hooks: dict[str, list] = {"PreToolUse": [mine]}
        hooks.setdefault(present[0], []).append(
            {"matcher": present[1], "hooks": [{"type": "command", "command": present[2]}]})
        existing = {
            "model": "sonnet",
            "env": {"FOO": "1"},
            "hooks": hooks,
            "permissions": {"allow": ["Bash(ls:*)"], "ask": ["Bash(curl:*)", template_ask()[0]]},
        }
        box.settings.parent.mkdir(parents=True, exist_ok=True)
        box.settings.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        before = digest(box.settings)
        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0 and "merge" in r.stdout and digest(box.settings) == before,
              "plan on a file that still needs a merge: names merge, byte- and mtime-identical")
        r = run(helper, "apply", *box.args("--yes"))
        check(fails, r.returncode == 0, f"apply --yes existing: exit 0 (got {r.returncode}: {r.stderr.strip()[:200]})")
        data = json.loads(box.settings.read_text(encoding="utf-8"))
        got = triples(data)
        check(fails, data.get("model") == "sonnet" and data.get("env") == {"FOO": "1"},
              "existing: other keys preserved")
        check(fails, ("PreToolUse", "Bash", "/opt/my-guard.sh") in got, "existing: user's own hook preserved")
        check(fails, all(t in got for t in expected), "existing: every template triple present")
        check(fails, all(got.count(t) == 1 for t in expected), "existing: no duplicated triple")
        perms = data.get("permissions") or {}
        check(fails, perms.get("allow") == ["Bash(ls:*)"], "existing: permissions.allow preserved")
        ask = perms.get("ask") or []
        check(fails, "Bash(curl:*)" in ask and all(ask.count(a) == 1 for a in template_ask())
              and set(template_ask()) <= set(ask), "existing: permissions.ask merged without duplicates")
        before = digest(box.settings)
        r = run(helper, "apply", *box.args("--yes"))
        check(fails, r.returncode == 0 and digest(box.settings) == before,
              "existing: second apply --yes identical")

        # Non-finite numbers are refused at parse time with that reason (not by a later guard).
        for label, body, reason in (("NaN literal", '{"x": NaN}\n', "non-standard JSON constant"),
                                    ("overflowing number", '{"a": 1e999}\n', "is not finite")):
            box.settings.write_text(body, encoding="utf-8")
            r = run(helper, "plan", *box.args())
            check(fails, refused(r) and reason in r.stderr and "unexpected" not in r.stderr,
                  f"{label}: refused at parse time, reason named")
        box.settings.unlink(missing_ok=True)

        # Every malformed settings shape is refused by plan AND apply, without a write.
        for label, body in BAD_SETTINGS:
            box.settings.write_text(body, encoding="utf-8")
            before = digest(box.settings)
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:]))
                check(fails, refused(r) and digest(box.settings) == before,
                      f"{label}: {action[0]} refused (WHY/FIX, no traceback), file untouched")

        # Hooks registered user-level: only permissions reach the project file.
        box.settings.unlink(missing_ok=True)
        # Windows python-wrapper form (quoted, backslashes) still counts as user-level.
        box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": '"C:\\Python312\\python.exe" "'
             + (box.user_hooks.as_posix() + "/check-tool-skill.sh").replace("/", "\\") + '"'}]}]}},
            indent=2) + "\n", encoding="utf-8")
        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0 and "user-level" in r.stdout and not box.settings.exists(),
              "user-level: Windows python-wrapper form detected")
        box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "~/.claude/hooks/check-tool-skill.sh"}]}]}}, indent=2) + "\n",
            encoding="utf-8")
        user_before = digest(box.user)
        r = run(helper, "plan", *box.args(), home=str(box.home))
        check(fails, r.returncode == 0 and "user-level" in r.stdout, "user-level: plan reports it")
        r = run(helper, "apply", *box.args("--yes"), home=str(box.home))
        check(fails, r.returncode == 0, f"user-level: apply exit 0 (got {r.returncode}: {r.stderr.strip()[:200]})")
        data = json.loads(box.settings.read_text(encoding="utf-8")) if box.settings.exists() else {}
        got = triples(data)
        rest = [t for t in expected if not t[2].endswith("/check-tool-skill.sh")]
        check(fails, not any(t[2].endswith("/check-tool-skill.sh") for t in got),
              "user-level: the registered script is not duplicated at project level")
        check(fails, sorted(got) == sorted(rest), "user-level: every other hook still installed")
        check(fails, (data.get("permissions") or {}).get("ask") == template_ask(),
              "user-level: permissions still merged")
        check(fails, digest(box.user) == user_before, "user-level settings never written")

        # A same-named script outside an idea-to-deploy hooks dir is not a registration.
        box.settings.unlink(missing_ok=True)
        box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "/usr/local/other-tool/freeze.sh"}]}]}}, indent=2) + "\n",
            encoding="utf-8")
        r = run(helper, "apply", *box.args("--yes"))
        data = json.loads(box.settings.read_text(encoding="utf-8")) if box.settings.exists() else {}
        check(fails, r.returncode == 0 and sorted(triples(data)) == sorted(expected),
              "unrelated same-named user script: all hooks installed")
        # A quoted user-level path with a space is recognised as one path.
        spaced = box.tmp / "home sp"
        (spaced / ".claude").mkdir(parents=True)
        spaced_user = spaced / ".claude" / "settings.json"
        spaced_user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f'bash "{(spaced / ".claude" / "hooks").as_posix()}/check-tool-skill.sh"'}]}]}})
            + "\n", encoding="utf-8")
        r = run(helper, "plan", "--root", str(box.root), "--hooks-dir", str(box.hooks),
                "--user-settings", str(spaced_user))
        check(fails, r.returncode == 0 and any("user-level" in line and "check-tool-skill.sh" in line
                                               for line in r.stdout.splitlines()),
              "quoted user-level path with a space: recognised")

        # A hooks dir whose name holds JSON-significant characters is substituted as data.
        odd = box.tmp / 'plu"g\\in' / "hooks"
        try:
            odd.mkdir(parents=True)
        except OSError:
            odd = None
        if odd is not None:
            box.settings.unlink(missing_ok=True)
            r = run(helper, "apply", "--root", str(box.root), "--hooks-dir", str(odd),
                    "--user-settings", str(box.user), "--yes")
            data = json.loads(box.settings.read_text(encoding="utf-8")) if box.settings.exists() else {}
            check(fails, r.returncode == 0 and sorted(triples(data)) == sorted(
                template_triples(odd.absolute().as_posix())),
                "hooks dir with a quote and a backslash: template intact, commands point at it")
            box.settings.unlink(missing_ok=True)

        # Another project's .claude/hooks is not the user's idea-to-deploy install.
        box.settings.unlink(missing_ok=True)
        box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"{(box.tmp / 'other-project').as_posix()}/.claude/hooks/check-tool-skill.sh"}]}]}},
            indent=2) + "\n", encoding="utf-8")
        r = run(helper, "apply", *box.args("--yes"), home=str(box.home))
        data = json.loads(box.settings.read_text(encoding="utf-8")) if box.settings.exists() else {}
        check(fails, r.returncode == 0 and sorted(triples(data)) == sorted(expected),
              "foreign project .claude/hooks: not user-level, all hooks installed")

        # A symlinked settings file is updated through its target.
        box.settings.unlink(missing_ok=True)
        target = box.root / "shared" / "settings.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"model": "haiku"}\n', encoding="utf-8")
        try:
            box.settings.symlink_to(target)
        except OSError:
            pass
        else:
            r = run(helper, "apply", *box.args("--yes"))
            data = json.loads(target.read_text(encoding="utf-8"))
            check(fails, r.returncode == 0 and box.settings.is_symlink() and data.get("model") == "haiku"
                  and sorted(triples(data)) == sorted(expected),
                  "symlinked settings: link kept, target merged")

        if box.settings.is_symlink():
            r = run(helper, "plan", *box.args())
            check(fails, r.returncode == 0
                  and f"symlink: writes go to {os.path.realpath(target)}" in r.stdout,
                  "symlinked settings: plan names the real target")
        # Anything that resolves outside the project is refused and nothing changes there.
        box.settings.unlink(missing_ok=True)
        outside = box.tmp / "outside"
        existing = box.tmp / "outside-file.json"
        existing.write_text('{"model": "haiku"}\n', encoding="utf-8")
        cases = (("dangling settings symlink", box.settings, outside / "s.json"),
                 ("settings symlink to an outside file", box.settings, existing),
                 ("dangling .claude dir symlink", box.root / ".claude", outside))
        for label, link, dest in cases:
            if link == box.root / ".claude":
                shutil.rmtree(link, ignore_errors=True)
            try:
                link.symlink_to(dest, target_is_directory=link.name == ".claude")
            except OSError:
                continue
            before = digest(existing)
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:]))
                check(fails, refused(r) and not outside.exists()
                      and digest(existing) == before, f"{label}: {action[0]} refused, nothing outside changed")
            link.unlink()
        (box.root / ".claude").mkdir(exist_ok=True)
        # A symlink loop - at settings.json or at the .claude dir - is refused, link kept.
        claude = box.root / ".claude"
        for label, link in (("settings.json", box.settings), (".claude dir", claude)):
            if link == claude:
                shutil.rmtree(claude, ignore_errors=True)
            try:
                link.symlink_to(link.name)
            except OSError:
                continue
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:]))
                check(fails, refused(r) and link.is_symlink(), f"symlink loop at {label}: {action[0]} refused, link kept")
            link.unlink()
        claude.mkdir(exist_ok=True)

        # The plugin hooks dir is recognised however it is spelled in the user-level settings.
        spelled = {
            "dot-dot segment": f"{box.hooks.parent.as_posix()}/../{box.hooks.parent.name}/hooks/check-tool-skill.sh",
            "$HOME form": "$HOME/plugin/hooks/check-tool-skill.sh",
            "${HOME} form": "${HOME}/plugin/hooks/check-tool-skill.sh",
        }
        for label, command in spelled.items():
            box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": command}]}]}}) + "\n", encoding="utf-8")
            r = run(helper, "plan", *box.args(), home=str(box.tmp))
            check(fails, r.returncode == 0 and any(
                "user-level" in line and "check-tool-skill.sh" in line for line in r.stdout.splitlines()),
                  f"plugin dir spelled with {label}: recognised as user-level")
        link = box.tmp / "hooks-link"
        try:
            link.symlink_to(box.hooks, target_is_directory=True)
        except OSError:
            pass
        else:
            box.user.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                {"type": "command", "command": f"{box.hooks.as_posix()}/check-tool-skill.sh"}]}]}}) + "\n",
                encoding="utf-8")
            r = run(helper, "plan", "--root", str(box.root), "--hooks-dir", str(link),
                    "--user-settings", str(box.user))
            check(fails, r.returncode == 0 and "user-level" in r.stdout,
                  "symlinked --hooks-dir: real-path registration recognised")

        # Unreadable user-level settings produce a visible warning.
        box.user.write_text("{broken\n", encoding="utf-8")
        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0 and "warning" in r.stdout and "user settings" in r.stdout,
              "unreadable user-level settings: plan warns")

        # Every malformed template is refused by plan AND apply, nothing written.
        for label, body in BAD_TEMPLATES:
            bad = box.tmp / "bad-template.json"
            bad.write_text(body, encoding="utf-8")
            box.settings.unlink(missing_ok=True)
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:], "--template", str(bad)))
                check(fails, refused(r) and not box.settings.exists(),
                      f"{label}: {action[0]} refused (WHY/FIX, no traceback), nothing written")

        # A --root that is a symlink loop is refused, not a traceback.
        loop_root = box.tmp / "loop-root"
        try:
            loop_root.symlink_to(loop_root.name)
        except OSError:
            pass
        else:
            r = run(helper, "apply", "--root", str(loop_root), "--hooks-dir", str(box.hooks),
                    "--user-settings", str(box.user), "--yes")
            check(fails, refused(r), "symlink-loop --root: refused (WHY/FIX, no traceback)")

        # Filesystem states around .claude and --root are refused, never a traceback.
        claude = box.root / ".claude"
        shutil.rmtree(claude, ignore_errors=True)
        claude.write_text("not a dir\n", encoding="utf-8")
        for action in (("plan",), ("apply", "--yes")):
            r = run(helper, action[0], *box.args(*action[1:]))
            check(fails, refused(r) and claude.read_text(encoding="utf-8") == "not a dir\n",
                  f".claude is a regular file: {action[0]} refused, file untouched")
        claude.unlink()
        claude.mkdir()
        if os.name == "posix" and os.geteuid() != 0:
            claude.chmod(0o555)
            r = run(helper, "apply", *box.args("--yes"))
            check(fails, refused(r) and not box.settings.exists(),
                  "read-only .claude: apply refused (WHY/FIX, no traceback), nothing written")
            claude.chmod(0o000)
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:]))
                check(fails, refused(r), f"unreadable .claude: {action[0]} refused (WHY/FIX, no traceback)")
            claude.chmod(0o755)
        # A settings path that is not a regular file is refused, never read or hung on.
        box.settings.unlink(missing_ok=True)
        box.settings.mkdir()
        r = run(helper, "plan", *box.args())
        check(fails, refused(r) and box.settings.is_dir(), "settings.json is a directory: refused")
        box.settings.rmdir()
        if hasattr(os, "mkfifo"):
            os.mkfifo(box.settings)
            for action in (("plan",), ("apply", "--yes")):
                r = run(helper, action[0], *box.args(*action[1:]))
                check(fails, refused(r), f"settings.json is a FIFO: {action[0]} refused, no hang")
            box.settings.unlink()
        # An unreadable user-level settings directory only warns.
        if os.name == "posix" and os.geteuid() != 0:
            box.user.parent.chmod(0o000)
            r = run(helper, "plan", *box.args())
            box.user.parent.chmod(0o755)
            check(fails, r.returncode == 0 and "warning" in r.stdout and "Traceback" not in r.stderr,
                  "unreadable user-level settings dir: plan warns, no refusal")
        # A failure after the write says the file was written (deterministic: the report line
        # that follows the write is made to fail).
        box.settings.unlink(missing_ok=True)
        probe = (
            "import builtins, importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('h', sys.argv[1])\n"
            "h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)\n"
            "def boom(*a, **k):\n"
            "    if a and str(a[0]).startswith(('created ', 'merged ')):\n"
            "        raise OSError('report line failed')\n"
            "    return builtins.print(*a, **k)\n"
            "h.print = boom\n"
            "sys.exit(h.main(sys.argv[2:]))\n")
        r = subprocess.run([sys.executable, "-c", probe, str(helper), "apply", *box.args("--yes")],
                           capture_output=True, text=True, timeout=60, check=False,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        check(fails, box.settings.exists() and refused(r) and "already written" in r.stderr,
              "failure after the write: refusal says the file was already written")
        box.settings.unlink(missing_ok=True)
        long_root = box.tmp / ("x" * 300)
        r = run(helper, "apply", "--root", str(long_root), "--hooks-dir", str(box.hooks),
                "--user-settings", str(box.user), "--yes")
        check(fails, refused(r), "overlong --root: refused (WHY/FIX, no traceback)")
        # Unreadable (deeply nested) user-level settings only warn.
        box.user.write_text('{"x": ' + "[" * 100000 + "]" * 100000 + "}\n", encoding="utf-8")
        r = run(helper, "plan", *box.args())
        check(fails, r.returncode == 0 and "warning" in r.stdout and "Traceback" not in r.stderr,
              "deeply nested user-level settings: plan warns, no traceback")

        # A --root that is not a directory is refused, nothing created.
        missing = box.tmp / "no-such-project"
        r = run(helper, "apply", "--root", str(missing), "--hooks-dir", str(box.hooks),
                "--user-settings", str(box.user), "--yes")
        check(fails, refused(r) and not missing.exists(),
              "missing --root: refused, nothing created")
    finally:
        box.close()


def last_step(text: str) -> str:
    body = text.split("## Instructions", 1)[-1]
    body = re.split(r"\n## (?!#)", body, maxsplit=1)[0]
    parts = re.split(r"\n(?=### Step )", body)
    return parts[-1] if parts and parts[-1].startswith("### Step ") else ""


def confirmation_items(step: str) -> tuple[bool, bool]:
    """(every non-«нет» item running `apply ... --yes` starts with an «да» condition,
    exactly one item starts with «нет» and it bans apply and leaves the file untouched).

    Structural only: the ban is found by phrase, not understood, so a self-contradictory item
    that quotes the ban words passes (checker c13); semantics are left to review."""
    items = re.split(r"\n(?=\d+\. )", step)
    no_items = [i for i in items if re.match(r"\d+\. On «нет»", i)]
    run_items = [i for i in items if i not in no_items and "apply" in i and "--yes" in i]
    yes_ok = bool(run_items) and all(re.match(r"\d+\. (?:Only on|On) «да»", i) for i in run_items)
    no_ok = len(no_items) == 1 and bool(
        re.search(r"(?i)do NOT run `apply`|no `apply`", no_items[0])) and bool(
        re.search(r"(?i)not touch|not touched", no_items[0]))
    return yes_ok, no_ok


def suite_docs(fails: list[str]) -> None:
    for skill in ("adopt", "project"):
        text = (REPO / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        step = last_step(text)
        check(fails, "itd_project_hooks.py" in step and " plan" in step and "apply" in step
              and "--yes" in step, f"{skill}: last step runs the helper plan and apply --yes")
        check(fails, bool(re.search(r"(?i)подтвержд|confirm", step)),
              f"{skill}: last step asks for confirmation")
        yes_ok, no_ok = confirmation_items(step)
        check(fails, yes_ok, f"{skill}: every item that runs apply --yes is conditional on «да»")
        check(fails, no_ok, f"{skill}: the single «нет» item forbids apply and leaves the file untouched")
    # The rule itself, on synthetic steps: one well-formed, three that must be rejected.
    good = ("### Step 9: x\n1. Show plan.\n2. Ask.\n3. On «да»: `apply --root R --yes`.\n"
            "4. On «нет» — do NOT run `apply`, the file is not touched; later: `apply --root R --yes`.")
    check(fails, confirmation_items(good) == (True, True), "rule self-test: a well-formed step passes")
    for label, bad in (
            ("unconditional apply", good.replace("3. On «да»: `apply", "3. Then: `apply")),
            ("apply folded into another item",
             good.replace("3. On «да»: `apply --root R --yes`.\n4. On «нет»",
                          "3. Run `apply --root R --yes`; on «нет»")),
            ("«нет» item without a ban", good.replace("do NOT run `apply`, the file is not touched",
                                                      "run it anyway"))):
        check(fails, confirmation_items(bad) != (True, True), f"rule self-test: {label} is rejected")
    for readme in ("README.md", "README.ru.md"):
        text = (REPO / readme).read_text(encoding="utf-8")
        check(fails, "not auto-installed" not in text, f"{readme}: no 'not auto-installed'")
        check(fails, "itd_project_hooks.py" in text, f"{readme}: describes the install step")


MUTATIONS = [
    ("apply without confirmation", "if not args.yes:", "if False:"),
    ("dedupe by command only", "key = (event, matcher, command)", "key = (event, '', command)"),
    ("always rewrite", "if new_text == old_text:", "if False:"),
    ("drop existing keys", "merged = dict(current)", "merged = {}"),
    ("ignore user-level", "& user_names:", "& set():"),
    ("malformed treated as empty", "return None, fail(", "return {}, fail("),
    ("write over the symlink", "write_atomic(target, new_text)", "write_atomic(settings, new_text)"),
    ("any same-named script is user-level", "if dir_forms(parent) & itd_dirs:", "if True:"),
    ("missing root accepted", "if not root.is_dir():", "if False:"),
    ("no path normalisation", "expanded = os.path.expandvars(os.path.expanduser(path))", "expanded = path"),
    ("write outside the project accepted", "if not target.is_relative_to(Path(os.path.realpath(root))):", "if False:"),
    ("no realpath form", "forms.add(os.path.realpath(expanded))", "pass"),
    ("foreign .claude/hooks counts", "if dir_forms(parent) & itd_dirs:", "if dir_forms(parent) & itd_dirs or parent.endswith('.claude/hooks'):"),
    ("entry hooks defaulted", 'if not isinstance(entry.get("hooks"), list):', "if False:"),
    ("empty command accepted", "if not isinstance(command, str) or not command.strip():", "if not isinstance(command, str):"),
    ("template without hooks accepted", "if template and not count:", "if False:"),
    ("whitespace tokenising", "        lexer.whitespace_split = True\n        tokens = list(lexer)", "        tokens = command.split()"),
    ("no top-level refusal guard", "except Exception as exc:  # the diagnostic contract covers the unforeseen too", "except ZeroDivisionError as exc:"),
    ("NaN accepted", "return json.loads(text, parse_constant=reject, parse_float=finite)", "return json.loads(text, parse_float=finite)"),
    ("overflow accepted", "return json.loads(text, parse_constant=reject, parse_float=finite)", "return json.loads(text, parse_constant=reject)"),
    ("non-regular file read", "        if not path.is_file():", "        if False:"),
    ("post-write failure hidden", "if WRITTEN else", "if False else"),
    (".claude as a file unchecked", "if settings.parent.exists() and not settings.parent.is_dir():", "if False:"),
    ("substitute into raw JSON", '    data = strict_json(template.read_text(encoding="utf-8"))', '    data = strict_json(template.read_text(encoding="utf-8").replace(PLACEHOLDER, hooks_dir.as_posix()))'),
    ("template shape unchecked", "    problem = shape_problem(data, template=True)\n    if problem:\n        raise ValueError(problem)\n", ""),
    ("symlink loop accepted", "if exc.errno == errno.ELOOP:", "if False:"),
    ("symlink target hidden in plan", "if target != settings:", "if False:"),
    ("unreadable user settings silent", "        if warning:\n            print(warning)\n", "        if False:\n            print(warning)\n"),
]


def mutations() -> int:
    baseline = suite(HELPER)
    if baseline:
        print("skip mutations: baseline suite is red: " + ", ".join(baseline))
        return 1
    lethal = 0
    for name, old, new in [("identity (control)", "", "")] + MUTATIONS:
        tmp = Path(tempfile.mkdtemp(prefix="itd-hooks-mut-"))
        try:
            copy = tmp / "skills" / "_shared" / HELPER.name
            copy.parent.mkdir(parents=True)
            ref = tmp / "skills" / "adopt" / "references"
            ref.mkdir(parents=True)
            shutil.copy2(TEMPLATE, ref / TEMPLATE.name)
            text = HELPER.read_text(encoding="utf-8")
            if old not in text:
                print(f"  MUTATION {name}: anchor not found")
                continue
            copy.write_text(text.replace(old, new, 1) if old else text, encoding="utf-8")
            fails = suite(copy)
            if not old:
                print(f"  CONTROL copy: {'green' if not fails else 'RED'} ({len(fails)} fails)")
                if fails:
                    return 1
                continue
            print(f"  MUTATION {name}: {'lethal' if fails else 'SURVIVED'} ({len(fails)} fails)")
            lethal += bool(fails)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"mutations lethal: {lethal}/{len(MUTATIONS)}")
    return 0 if lethal == len(MUTATIONS) else 1


def main() -> int:
    args = sys.argv[1:]
    if "--mutations" in args:
        return mutations()
    helper = Path(args[args.index("--helper") + 1]) if "--helper" in args else HELPER
    fails = suite(helper)
    if fails:
        print(f"FAILED: {len(fails)} failed, {PASSES} passed")
        return 1
    print(f"PASSED: 0 failed, {PASSES} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
