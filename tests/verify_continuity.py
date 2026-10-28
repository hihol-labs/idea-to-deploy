#!/usr/bin/env python3
"""verify_continuity.py - one continuity document per workstream (plan session 7, ITD-PLAN-S7).

/session-save keeps the current state of a topic in `.itd-memory/continuity/<topic>.md` (next action, state,
decisions, checks, blockers), rewritten whole; the history is appended to `.itd-memory/HISTORY.md` and never
competes with it. /handoff uses the same document plus a transfer section. The oracle pins:

  1. the skills: session-save SKILL.md is at most 200 lines; its format block has the frontmatter and the five
     sections in order and /handoff names the same sections; the triggers are milestones and irreversible steps;
     no instruction writes the legacy session_*.md, MEMORY.md or the lockfile;
  2. the flags: the documented --sync line and --push-memory block act only in the ITD repository (the top-level
     name of the parsed manifest at the repository root, also from a subdirectory; a nested name does not count) -
     run as written against a stub sync script and a real bare remote; the memory dir without git is ./.itd-memory;
  3. a new session recovers the next action from one document: pre-flight lists the open documents newest first
     with the next action (the skill's own template parses), reads past any number of closed ones, hides them and
     the legacy MEMORY.md index,
     and falls back to that index only in a project without continuity documents; session-open-diagnostic and
     handoff-readiness read the same documents;
  4. CONTINUITY-WRITER-1: state-guard refuses a Write over a document another session changed less than 10
     minutes ago, lets its own rewrite, an Edit, a new or old document and an unknown session pass, and spends
     the shared deny budget.

Run: sh skills/_shared/itd_py.sh tests/verify_continuity.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVE = ROOT / "skills" / "session-save" / "SKILL.md"
HANDOFF = ROOT / "skills" / "handoff" / "SKILL.md"
HOOKS = ROOT / "hooks"
SECTIONS = ("## Следующее действие", "## Состояние", "## Решения", "## Проверки", "## Блокеры")
FRONTMATTER = ("topic:", "status:", "updated:", "branch:", "unit:")

fails: list[str] = []
passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passes
    print(("ok   " if cond else "FAIL ") + name + ((" | " + detail) if (detail and not cond) else ""))
    if cond:
        passes += 1
    else:
        fails.append(name)


def fenced(text: str, lang: str) -> list[list[str]]:
    blocks, current = [], None
    for line in text.splitlines():
        if current is None and line.strip() == "```" + lang:
            current = []
        elif current is not None and line.strip() == "```":
            blocks.append(current)
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def load(name: str, module: str):
    sys.dont_write_bytecode = True  # the hooks directory gets no .pyc from a test
    loader = importlib.machinery.SourceFileLoader(module, str(HOOKS / name))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(module, loader))
    sys.path.insert(0, str(HOOKS))
    try:
        loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS))
    return mod


def write(path: Path, text: str, age: float = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if age:
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
    return path


def doc(topic: str, action: str, status: str = "open") -> str:
    return (f"---\ntopic: {topic}\nstatus: {status}\nupdated: 2026-10-28T09:00Z\nbranch: main @ abc1234\nunit: n/a\n"
            f"---\n\n## Следующее действие\n> [!todo] {action}\n\n## Состояние\n- s\n\n## Решения\n- d\n\n"
            "## Проверки\n- `pytest` -> 1 passed\n\n## Блокеры\n- нет\n")


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)


def shell(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    # Git Bash on Windows (ITD_BASH, as the sync tests), sh elsewhere
    bash = os.environ.get("ITD_BASH") or shutil.which("sh") or "sh"
    return subprocess.run([bash, "-c", script], cwd=str(cwd), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)


def hook_env(tmp: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in ("ITD_STATE_GUARD", "ITD_HANDOFF_READINESS", "CLAUDE_SESSION_ID"):
        env.pop(key, None)
    env["HOME"] = env["USERPROFILE"] = str(tmp / "home")
    hooktmp = tmp / "hooktmp"
    hooktmp.mkdir(exist_ok=True)
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(hooktmp)  # deny budget, sentinels, pre-flight state
    return env


def run_hook(name: str, payload: dict, cwd: Path, env: dict[str, str]) -> tuple[int, dict, str]:
    res = subprocess.run([sys.executable, str(HOOKS / name)], input=json.dumps(payload), cwd=str(cwd), env=env,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        out = json.loads(res.stdout or "{}")
    except ValueError:
        out = {}
    return res.returncode, out if isinstance(out, dict) else {}, res.stdout + res.stderr


def skills_cases() -> None:
    print("[1] the skills")
    save, handoff = SAVE.read_text(encoding="utf-8"), HANDOFF.read_text(encoding="utf-8")
    lines = save.splitlines()
    check("session-save SKILL.md is at most 200 lines", len(lines) <= 200, str(len(lines)))
    templates = [b for b in fenced(save, "markdown") if any(l.startswith("## Следующее") for l in b)]
    template = templates[0] if len(templates) == 1 else []
    heads = [l for l in template if l.startswith("## ")]
    check("one format block: the five sections in order", tuple(heads) == SECTIONS, str(heads))
    front = template[1:template.index("---", 1)] if template[:1] == ["---"] and "---" in template[1:] else []
    check("the format block carries the frontmatter fields",
          tuple(l.split(":", 1)[0] + ":" for l in front) == FRONTMATTER, str(front))
    check("the document lives in .itd-memory/continuity/<тема>.md and is rewritten whole",
          "`.itd-memory/continuity/<тема>.md`" in save and "перезаписывается целиком" in save)
    check("the history is appended apart: .itd-memory/HISTORY.md", "cat >> .itd-memory/HISTORY.md" in save)
    names = [h[3:] for h in SECTIONS]
    check("/handoff writes the same document and names the same sections",
          "тот же формат" in handoff.lower() and all(f"«{n}»" in handoff for n in names)
          and "`.itd-memory/continuity/<тема>.md`" in handoff and "## Передача" in handoff, str(names))
    check("triggers: milestones and irreversible steps, not every sub-step",
          "на вехах и перед необратимым" in save and "Не после каждого коммита" in save)
    legacy = [l for l in lines if re.search(r"session_YYYY|MEMORY\.md|\.active-session\.lock", l)
              and "Старые" not in l and "ведет хук state-guard" not in l]
    check("no instruction writes session_*.md, MEMORY.md or the lockfile", not legacy, str(legacy[:2]))
    check("--close keeps the hygiene boundary", "itd_hygiene.py close" in save)


def flag_cases(tmp: Path) -> None:
    print("[2] --sync and --push-memory act only in the ITD repository")
    save = SAVE.read_text(encoding="utf-8")
    blocks = [b for b in fenced(save, "bash") if any("sync-to-active.sh" in l for l in b)]
    block = blocks[0] if len(blocks) == 1 else []
    prefix = block[:4]
    sync = [l for l in block if l.endswith("# --sync")]
    start = next((i for i, l in enumerate(block) if l.endswith("# --push-memory")), len(block))
    push = block[start:]
    check("one flags block: the repository root and its parsed manifest decide",
          prefix[:1] == ['R="$(git rev-parse --show-toplevel)"']
          and prefix[3:] == ['ITD="$(sh "$T/itd_py.sh" "$T/itd_contract_dir.py" --root "$R")"'], str(prefix))
    check("--sync and --push-memory act only when the manifest parses as idea-to-deploy",
          len(sync) == 1 and sync[0].startswith('[ "$ITD" = docs ] && (cd "$R" && ')
          and any(l.startswith('if [ "$ITD" = docs ] && ') for l in push), str(sync + push[:2]))
    check("no raw-text match of the manifest", "grep -qs" not in save)
    check("the flags run only on the user's explicit flag", "только по явному флагу" in save)
    if len(sync) != 1 or not push:
        return
    env = dict(os.environ)
    env["HOME"] = env["USERPROFILE"] = str(tmp / "flag-home")
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@example.invalid"
    install = Path(env["HOME"]) / ".claude" / "skills" / "_shared"  # the installation the resolver picks
    install.mkdir(parents=True)
    for name in ("itd_py.sh", "itd_tool.sh", "itd_contract_dir.py"):
        shutil.copy2(ROOT / "skills" / "_shared" / name, install / name)
    remote = tmp / "flag-remote.git"
    git(tmp, "init", "-q", "--bare", str(remote))
    memory = Path(env["HOME"]) / ".claude" / "methodology-memory"
    memory.mkdir(parents=True)
    git(memory, "init", "-q")
    git(memory, "remote", "add", "origin", str(remote))
    cases = (("other-project", '{"name": "buying"}', ""),
             ("nested-name", '{"name": "buying", "plugins": [{"name": "idea-to-deploy"}]}', ""),
             ("no-manifest", None, ""),
             ("itd-repo", '{\n\t"name":\n\t"idea-to-deploy",\n  "version": "1"\n}', ""),
             ("itd-repo", None, "sub/dir"))
    for i, (name, manifest, below) in enumerate(cases):
        project = tmp / "flags" / name
        if not (project / ".git").exists():
            git(tmp, "init", "-q", str(project))
            write(project / "scripts" / "sync-to-active.sh", "echo synced > sync.marker\n")
        if manifest is not None:
            write(project / ".claude-plugin" / "plugin.json", manifest)
        (project / "sync.marker").unlink(missing_ok=True)
        cwd = project / below
        cwd.mkdir(parents=True, exist_ok=True)
        write(memory / f"note-{i}.md", "note\n")
        pushed = git(remote, "rev-list", "--all", "--count").stdout.strip() or "0"
        r1 = shell("\n".join(prefix + sync), cwd, env)
        r2 = shell("\n".join(prefix + push), cwd, env)
        after = git(remote, "rev-list", "--all", "--count").stdout.strip() or "0"
        itd, label = name == "itd-repo", name + (f" from {below}" if below else "")
        check(f"--sync in {label}: {'runs' if itd else 'does nothing'}",
              (project / "sync.marker").is_file() == itd, f"rc={r1.returncode} {r1.stderr[:200]}")
        check(f"--push-memory in {label}: {'commits and pushes' if itd else 'does nothing'}",
              (int(after) == int(pushed) + 1) == itd, f"rc={r2.returncode} {pushed}->{after} {r2.stderr[:200]}")

    mem_block = [b for b in fenced(save, "bash") if any(l.startswith("git rev-parse --show-toplevel") for l in b)]
    script = "\n".join(mem_block[0]) if len(mem_block) == 1 else "false"
    nogit = tmp / "nogit"
    nogit.mkdir()
    r = shell(script, nogit, env)
    check("without git the memory dir is ./.itd-memory, not /.itd-memory",
          r.returncode == 0 and (nogit / ".itd-memory" / "continuity").is_dir(), f"rc={r.returncode} {r.stderr[:200]}")
    repo = tmp / "gitsub"
    git(tmp, "init", "-q", str(repo))
    (repo / "a" / "b").mkdir(parents=True)
    r = shell(script, repo / "a" / "b", env)
    check("in a repository the memory dir is the root's .itd-memory",
          r.returncode == 0 and (repo / ".itd-memory" / "continuity").is_dir()
          and not (repo / "a" / "b" / ".itd-memory").exists(), f"rc={r.returncode} {r.stderr[:200]}")


def preflight_cases(tmp: Path) -> None:
    print("[3] a new session recovers the next action from one document")
    env = hook_env(tmp)
    project = tmp / "project"
    project.mkdir()
    git(project, "init", "-q")
    mem = project / ".itd-memory"
    write(mem / "MEMORY.md", "- [old](session_2026-10-01.md) — LEGACY-INDEX\n")
    write(mem / "session_2026-10-01.md", "## Следующие шаги\n1. LEGACY-NEXT\n", age=3600)
    write(mem / "continuity" / "alpha.md", doc("alpha", "ALPHA-NEXT"), age=7200)
    write(mem / "continuity" / "beta.md", doc("beta", "BETA-NEXT", status="done"), age=60)
    write(mem / "continuity" / "gamma.md", doc("gamma", "GAMMA-NEXT"), age=120)
    rc, out, raw = run_hook("pre-flight-check.sh", {"session_id": "cont-1"}, project, env)
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    check("pre-flight lists the open documents with their next action, newest first",
          rc == 0 and "`gamma` (2 мин): GAMMA-NEXT" in ctx and "`alpha` (2 ч): ALPHA-NEXT" in ctx
          and ctx.find("GAMMA-NEXT") < ctx.find("ALPHA-NEXT"), raw[:400])
    check("a closed topic and the legacy index do not compete",
          "BETA-NEXT" not in ctx and "LEGACY-INDEX" not in ctx and "Project memory index" not in ctx, ctx[:400])

    template = [b for b in fenced(SAVE.read_text(encoding="utf-8"), "markdown") if any(
        l.startswith("## Следующее") for l in b)]
    filled = "\n".join(template[0]) if template else ""
    preflight = load("pre-flight-check.sh", "itd_s7_preflight")
    status, action = preflight.continuity_fields(filled)
    check("the skill's own format block parses: status and next action",
          status == "open" and action == "<один точный шаг: можно начать без догадок>", f"{status!r} {action!r}")
    status, action = preflight.continuity_fields("---\nstatus: done # closed\n---\n## Next action\n\nDEPLOY\n")
    check("an English heading and an inline comment parse", (status, action) == ("done", "DEPLOY"))

    many = tmp / "many"
    for i in range(8):
        write(many / ".itd-memory" / "continuity" / f"t{i}.md", doc(f"t{i}", f"T{i}-NEXT"), age=600 + i)
    text = preflight.continuity_context(many / ".itd-memory")
    check("at most five open topics are listed, the rest counted",
          text.count("\n- `") == 5 and "T0-NEXT" in text and "T7-NEXT" not in text and "еще 3" in text, text)
    buried = tmp / "buried" / ".itd-memory"
    write(buried / "continuity" / "old-open.md", doc("old-open", "OLD-OPEN-NEXT"), age=7 * 86400)
    for i in range(45):
        write(buried / "continuity" / f"c{i}.md", doc(f"c{i}", "C-NEXT", status="done"), age=600 + i)
    text = preflight.continuity_context(buried)
    check("an open topic behind 45 newer closed ones is still listed",
          "`old-open` (7 дн): OLD-OPEN-NEXT" in text and "открытых тем нет" not in text, text[:300])
    closed = tmp / "closed"
    write(closed / ".itd-memory" / "MEMORY.md", "LEGACY-INDEX\n")
    write(closed / ".itd-memory" / "continuity" / "x.md", doc("x", "X-NEXT", status="done"))
    git(closed, "init", "-q")
    rc, out, raw = run_hook("pre-flight-check.sh", {"session_id": "cont-2"}, closed, env)
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    check("all topics closed: said so, the legacy index stays hidden",
          "открытых тем нет" in ctx and "LEGACY-INDEX" not in ctx, raw[:300])
    legacy = tmp / "legacy"
    write(legacy / ".itd-memory" / "MEMORY.md", "- LEGACY-INDEX\n")
    git(legacy, "init", "-q")
    rc, out, raw = run_hook("pre-flight-check.sh", {"session_id": "cont-3"}, legacy, env)
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    check("a project without continuity documents keeps the MEMORY.md index",
          "LEGACY-INDEX" in ctx and "Continuity" not in ctx, raw[:300])

    session_open = load("session-open-diagnostic.sh", "itd_s7_session_open")
    diagnostic = session_open.build_diagnostic(project) or ""
    check("session-open-diagnostic shows the newest document, not the legacy session file",
          "BETA-NEXT" in diagnostic and "continuity/beta.md" in diagnostic and "LEGACY-NEXT" not in diagnostic,
          diagnostic[:300])
    readiness = load("handoff-readiness.sh", "itd_s7_readiness")
    fresh = tmp / "fresh"
    write(fresh / ".itd-memory" / "continuity" / "f.md", doc("f", "F"), age=300)
    age = readiness.latest_session_age_min(fresh / ".itd-memory")
    check("handoff-readiness counts a continuity document as the checkpoint", age is not None and 4 < age < 6,
          str(age))
    write(fresh / "dirty.txt", "x")
    git(fresh, "init", "-q")
    rc, out, raw = run_hook("handoff-readiness.sh", {"session_id": "cont-4", "cwd": str(fresh)}, fresh, env)
    check("a dirty tree with a fresh document gets no hint", rc == 0 and "HANDOFF-READINESS" not in raw, raw[:300])
    os.utime(fresh / ".itd-memory" / "continuity" / "f.md", (time.time() - 5 * 3600, time.time() - 5 * 3600))
    rc, out, raw = run_hook("handoff-readiness.sh", {"session_id": "cont-5", "cwd": str(fresh)}, fresh, env)
    check("a dirty tree with a stale document gets the hint", rc == 0 and "HANDOFF-READINESS" in raw, raw[:300])


def guard_cases(tmp: Path) -> None:
    print("[4] CONTINUITY-WRITER-1: state-guard keeps a parallel session from overwriting a document")
    env = hook_env(tmp)
    project = tmp / "guarded"
    (project / ".itd-memory" / "continuity").mkdir(parents=True)
    target = project / ".itd-memory" / "continuity" / "topic.md"
    tag = f"{os.getpid()}-{int(time.time() * 1000)}"

    def pre(sid: str, tool: str = "Write", path: Path = target) -> tuple[int, dict]:
        rc, out, _ = run_hook("state-guard.sh", {"hook_event_name": "PreToolUse", "session_id": sid,
                                                 "cwd": str(project), "tool_name": tool,
                                                 "tool_input": {"file_path": str(path), "content": "x"}},
                              project, env)
        return rc, out.get("hookSpecificOutput") or {}

    def post(sid: str, tool: str = "Write") -> None:
        run_hook("state-guard.sh", {"hook_event_name": "PostToolUse", "session_id": sid, "cwd": str(project),
                                    "tool_name": tool, "tool_input": {"file_path": str(target)}}, project, env)

    def denied(r: tuple[int, dict]) -> bool:
        return r[0] == 2 and r[1].get("permissionDecision") == "deny"

    def passed(r: tuple[int, dict]) -> bool:
        return r[0] == 0 and r[1].get("permissionDecision") != "deny"

    check("a new document passes", passed(pre(f"a-{tag}")))
    write(target, doc("topic", "A"))
    post(f"a-{tag}")
    check("the session that wrote the document rewrites it", passed(pre(f"a-{tag}")))
    r = pre(f"b-{tag}")
    check("another session's Write over the fresh document is denied",
          denied(r) and "документа продолжения" in (r[1].get("permissionDecisionReason") or ""), str(r))
    check("an Edit of the fresh document passes", passed(pre(f"c-{tag}", tool="Edit")))
    check("an unknown session passes (no attribution)", passed(pre("unknown")))
    check("another document of the memory dir passes", passed(pre(f"c-{tag}", path=project / ".itd-memory" / "n.md")))
    write(target, doc("topic", "B"))
    check("a rewrite by someone else makes the first session's Write a deny too", denied(pre(f"a-{tag}")))
    os.utime(target, (time.time() - 1200, time.time() - 1200))
    check("a document older than 10 minutes passes for any session", passed(pre(f"d-{tag}")))
    write(target, doc("topic", "C"))
    budget = [pre(f"e-{tag}") for _ in range(3)]
    check("the shared deny budget: two denies, then a pass with a warning",
          denied(budget[0]) and denied(budget[1]) and passed(budget[2])
          and "CONTINUITY-GUARD" in (budget[2][1].get("additionalContext") or ""), str(budget[2]))
    check("ITD_STATE_GUARD=0 turns the gate off", passed(
        (lambda r: (r[0], r[1].get("hookSpecificOutput") or {}))(run_hook(
            "state-guard.sh", {"hook_event_name": "PreToolUse", "session_id": f"f-{tag}", "cwd": str(project),
                               "tool_name": "Write", "tool_input": {"file_path": str(target)}},
            project, {**env, "ITD_STATE_GUARD": "0"}))))


def main() -> int:
    skills_cases()
    with tempfile.TemporaryDirectory(prefix="itd-continuity-") as raw:
        tmp = Path(raw)
        flag_cases(tmp)
        preflight_cases(tmp)
        guard_cases(tmp)
    print(f"{'PASSED' if not fails else 'FAILED'}: {passes} passed, {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
