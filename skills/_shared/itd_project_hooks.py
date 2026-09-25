#!/usr/bin/env python3
"""Offer-and-install of idea-to-deploy enforcement hooks into a project's settings (G-004).

Merges `skills/adopt/references/project-settings-template.json` into
`<root>/.claude/settings.json`. `/adopt` and `/project` run `plan`, show it, ask the user,
and run `apply --yes` only on an explicit yes; a declined offer never reaches this script.

    itd_project_hooks.py                                  # no-op, exit 0
    itd_project_hooks.py plan  --root DIR [--hooks-dir DIR]   # read-only: what would change
    itd_project_hooks.py apply --root DIR [--hooks-dir DIR] --yes

Merge rules (idempotent): a hook is identified by (event, matcher, command), so a script
registered under several matchers of one event is added under each of them; the user's own
hooks, other keys and permissions are kept; `permissions.ask` rules are added by exact
string. A template hook whose script is already registered in the user-level settings
(`~/.claude/settings.json`, read only) from an idea-to-deploy hooks directory (the `hooks` dir
next to that settings file, or the resolved plugin hooks dir) is skipped, so it does not fire twice; the rest are still
installed. A symlinked settings file is updated through its target, which must stay inside the
project (a link that resolves outside `--root`, dangling or not, is refused). The user-level file
is never written.

Exit codes: 0 success or no-op; 1 unreadable settings/template or no hooks dir; 2 usage or
missing confirmation.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

PLACEHOLDER = "{{PLUGIN_HOOKS_DIR}}"
TEMPLATE_REL = Path("adopt") / "references" / "project-settings-template.json"
WRITTEN: list[Path] = []  # set once the settings file is written, so a later failure says so


def strict_json(text: str) -> object:
    """json.loads that refuses NaN/Infinity, literal or overflowing (1e999): not JSON."""
    def reject(name: str) -> object:
        raise ValueError(f"non-standard JSON constant {name}")

    def finite(literal: str) -> float:
        value = float(literal)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"number {literal} is not finite")
        return value
    return json.loads(text, parse_constant=reject, parse_float=finite)


def fail(why: str, fix: str) -> str:
    return f"WHY: {why}\nFIX: {fix}"


def default_template() -> Path:
    return Path(__file__).resolve().parent.parent / TEMPLATE_REL


def default_hooks_dir() -> Path | None:
    home = Path.home() / ".claude"
    candidates = []
    if os.environ.get("CLAUDE_PLUGIN_DIR"):
        candidates.append(Path(os.environ["CLAUDE_PLUGIN_DIR"]) / "hooks")
    candidates += [home / "plugins" / "idea-to-deploy" / "hooks", home / "hooks"]
    for path in candidates:
        if path.is_dir():
            return path
    return None


def load_object(path: Path, what: str) -> tuple[dict | None, str | None]:
    """Return (document, None); a missing file is an empty document."""
    try:
        if not path.exists():
            return {}, None
        if not path.is_file():
            return None, fail(f"{what} {path} is not a regular file",
                              f"replace {path} with a JSON file or move it aside, then rerun; "
                              "nothing was written")
        data = strict_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        return None, fail(f"{what} {path} is not readable JSON ({type(exc).__name__}: {exc})",
                          f"repair or move {path} aside, then rerun; nothing was written")
    problem = shape_problem(data)
    if problem:
        return None, fail(f"{what} {path}: {problem}",
                          f"fix {path}, then rerun; nothing was written")
    return data, None


def shape_problem(data: object, template: bool = False) -> str:
    """Why `data` is not a settings document this script can merge ("" when it is).

    Strict: nothing is defaulted. Every event maps to a list of entry objects; every entry has a
    `hooks` list of hook objects and, if present, a string `matcher`; every hook has a non-empty
    string `command`; `permissions.ask`, if present, is a list of strings. A template must also
    carry at least one hook.
    """
    if not isinstance(data, dict):
        return "not a JSON object"
    hooks = data.get("hooks")
    if hooks is None:
        if template:
            return "the template has no 'hooks'"
    elif not isinstance(hooks, dict):
        return "'hooks' is not an object of event lists"
    else:
        count = 0
        for event, entries in hooks.items():
            if not isinstance(entries, list):
                return f"'hooks.{event}' is not a list"
            for n, entry in enumerate(entries):
                where = f"'hooks.{event}[{n}]'"
                if not isinstance(entry, dict):
                    return f"{where} is not an object"
                if "matcher" in entry and not isinstance(entry["matcher"], str):
                    return f"{where}.matcher is not a string"
                if not isinstance(entry.get("hooks"), list):
                    return f"{where} has no 'hooks' list"
                for k, hook in enumerate(entry["hooks"]):
                    if not isinstance(hook, dict):
                        return f"{where}.hooks[{k}] is not an object"
                    command = hook.get("command")
                    if not isinstance(command, str) or not command.strip():
                        return f"{where}.hooks[{k}] has no non-empty string 'command'"
                    count += 1
        if template and not count:
            return "the template registers no hook"
    perms = data.get("permissions")
    if perms is not None:
        if not isinstance(perms, dict):
            return "'permissions' is not an object"
        ask = perms.get("ask", [])
        if not isinstance(ask, list) or not all(isinstance(r, str) for r in ask):
            return "'permissions.ask' is not a list of strings"
    return ""


def template_settings(template: Path, hooks_dir: Path) -> dict:
    """Parse the template, validate it, then put the hooks dir into the command strings."""
    data = strict_json(template.read_text(encoding="utf-8"))
    problem = shape_problem(data, template=True)
    if problem:
        raise ValueError(problem)
    data = {k: v for k, v in data.items() if not k.startswith("_comment")}
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                hook["command"] = hook["command"].replace(PLACEHOLDER, hooks_dir.as_posix())
    return data


def script_tokens(command: str) -> list[str]:
    """`.sh` paths in a hook command, quoted paths with spaces kept whole, `/` separators."""
    try:
        lexer = shlex.shlex(command, posix=False)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    out = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            token = token[1:-1]
        token = token.replace("\\", "/")
        if token.endswith(".sh"):
            out.append(token)
    return out


def dir_forms(path: str) -> set[str]:
    """Comparable spellings of a directory: as written, with ~/$HOME expanded, and real."""
    expanded = os.path.expandvars(os.path.expanduser(path))
    forms = {path, expanded}
    if os.path.isabs(expanded):
        forms.add(os.path.realpath(expanded))
    return {f.replace("\\", "/").rstrip("/").lower() for f in forms if f}


def itd_script_names(settings: dict, itd_dirs: set[str]) -> set[str]:
    """Script names registered from one of `itd_dirs` (not any same-named file elsewhere)."""
    names = set()
    for entries in (settings.get("hooks") or {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []) or []:
                command = str(hook.get("command", "")) if isinstance(hook, dict) else ""
                for token in script_tokens(command):
                    parent, _, name = token.rpartition("/")
                    if dir_forms(parent) & itd_dirs:
                        names.add(name)
    return names


def merge(current: dict, template: dict, user_names: set[str]) -> tuple[dict, list[str]]:
    merged = dict(current)
    added: list[str] = []
    hooks = {event: [dict(e, hooks=list(e.get("hooks", []))) for e in entries]
             for event, entries in (current.get("hooks") or {}).items()}
    seen = set()
    for event, entries in hooks.items():
        for entry in entries:
            for hook in entry["hooks"]:
                if isinstance(hook, dict):
                    seen.add((event, entry.get("matcher", ""), hook.get("command", "")))
    for event, entries in template.get("hooks", {}).items():
        for entry in entries:
            matcher = entry.get("matcher", "")
            for hook in entry.get("hooks", []):
                command = hook.get("command", "")
                key = (event, matcher, command)
                if key in seen:
                    continue
                if set(n.rsplit("/", 1)[-1] for n in script_tokens(command)) & user_names:
                    continue
                seen.add(key)
                target = next((e for e in hooks.setdefault(event, [])
                               if e.get("matcher", "") == matcher), None)
                if target is None:
                    target = {k: v for k, v in entry.items() if k != "hooks"}
                    target["hooks"] = []
                    hooks[event].append(target)
                target["hooks"].append(dict(hook))
                added.append(f"+ {event} [{matcher or '*'}] {command}")
    if hooks:
        merged["hooks"] = hooks
    ask_rules = (template.get("permissions") or {}).get("ask", [])
    perms = dict(current.get("permissions") or {})
    ask = list(perms.get("ask", []))
    for rule in ask_rules:
        if rule not in ask:
            ask.append(rule)
            added.append(f"+ permissions.ask {rule}")
    if ask_rules:
        perms["ask"] = ask
        merged["permissions"] = perms
    return merged, added


def render(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv: list[str]) -> int:
    """Every failure is a WHY/FIX refusal, never a traceback; writes are atomic, so a refusal
    leaves the settings file as it was."""
    try:
        return run(argv)
    except Exception as exc:  # the diagnostic contract covers the unforeseen too
        written = (f"{WRITTEN[-1]} was already written before the failure; check it"
                   if WRITTEN else "nothing was written (writes are atomic)")
        print(fail(f"unexpected {type(exc).__name__}: {exc}",
                   f"{written}; fix the reported input or path and rerun"), file=sys.stderr)
        return 1


def run(argv: list[str]) -> int:
    if not argv:
        return 0
    parser = argparse.ArgumentParser(prog="itd_project_hooks.py")
    parser.add_argument("action", choices=["plan", "apply"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--hooks-dir")
    parser.add_argument("--template")
    parser.add_argument("--user-settings")
    parser.add_argument("--yes", action="store_true",
                        help="the user explicitly confirmed the install")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()  # a failure here is refused by main()
    if not root.is_dir():
        print(fail(f"project root {root} is not a directory",
                   "pass --root with the existing project directory"), file=sys.stderr)
        return 1
    settings = root / ".claude" / "settings.json"
    for path in (settings.parent, settings):  # a loop at .claude or at settings.json
        try:
            os.stat(path)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                print(fail(f"{path} is a symlink loop",
                           "remove the link or point it at a real path, then rerun; "
                           "nothing was written"), file=sys.stderr)
                return 1
    if settings.parent.exists() and not settings.parent.is_dir():
        print(fail(f"{settings.parent} exists and is not a directory",
                   "move it aside so .claude can be a directory, then rerun; nothing was written"),
              file=sys.stderr)
        return 1
    target = Path(os.path.realpath(settings))
    if not target.is_relative_to(Path(os.path.realpath(root))):
        print(fail(f"{settings} resolves to {target}, outside the project {root} "
                   "(a symlinked .claude or settings.json)",
                   "point the link inside the project or remove it, then rerun; nothing was written"),
              file=sys.stderr)
        return 1
    if args.action == "apply":
        if not args.yes:
            print(fail("apply needs the user's explicit confirmation",
                       "show `plan` to the user; rerun `apply --yes` only after a yes"),
                  file=sys.stderr)
            return 2
    hooks_dir = Path(args.hooks_dir) if args.hooks_dir else default_hooks_dir()
    if hooks_dir is None or not hooks_dir.is_dir():
        print(fail(f"plugin hooks dir not found ({hooks_dir or 'no candidate exists'})",
                   "pass --hooks-dir with the idea-to-deploy hooks directory"), file=sys.stderr)
        return 1
    template_path = Path(args.template) if args.template else default_template()
    try:
        template = template_settings(template_path, hooks_dir.absolute())
    except (OSError, ValueError, RecursionError) as exc:
        print(fail(f"settings template {template_path} is not usable ({type(exc).__name__}: {exc})",
                   "reinstall idea-to-deploy or pass --template"), file=sys.stderr)
        return 1
    current, error = load_object(settings, "project settings")
    if current is None:
        print(error, file=sys.stderr)
        return 1
    user_path = Path(args.user_settings) if args.user_settings \
        else Path.home() / ".claude" / "settings.json"
    user, user_error = load_object(user_path, "user settings")
    warning = (f"warning: user settings {user_path} are unreadable, so no hook is treated as "
               f"registered user-level:\n{user_error}") if user is None else ""
    template_names = {t.rsplit("/", 1)[-1] for entries in template.get("hooks", {}).values()
                      for e in entries for h in e.get("hooks", [])
                      for t in script_tokens(str(h.get("command", "")))}
    # idea-to-deploy hooks installed for this user live next to the user-level settings file
    # (sync-to-active: ~/.claude/hooks) or in the plugin hooks dir; nowhere else counts.
    itd_dirs = dir_forms(hooks_dir.absolute().as_posix()) | dir_forms(
        (user_path.absolute().parent / "hooks").as_posix())
    registered = itd_script_names(user or {}, itd_dirs) & template_names

    merged, added = merge(current, template, registered)
    old_text = settings.read_text(encoding="utf-8") if settings.exists() else ""
    new_text = render(merged)
    if not added:
        new_text = old_text
    state = "create" if not settings.exists() else ("merge" if added else "unchanged")

    if args.action == "plan":
        print(f"plan: {state} {settings}")
        if target != settings:
            print(f"symlink: writes go to {target}")
        if warning:
            print(warning)
        if registered:
            print(f"skip hooks registered user-level in {user_path}: "
                  f"{', '.join(sorted(registered))}")
        for line in added:
            print(line)
        return 0

    if new_text == old_text:
        print(f"unchanged {settings}")
        return 0
    if warning:
        print(warning, file=sys.stderr)
    write_atomic(target, new_text)
    WRITTEN.append(target)
    print(f"{'created' if state == 'create' else 'merged'} {settings}")
    if registered:
        print(f"skip hooks registered user-level in {user_path}: {', '.join(sorted(registered))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
