#!/usr/bin/env python3
"""Runner of the TESTGAP pilot (docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md). Local tool, not shipped.

  pilot_run.py build <case>                 - template repo of the case: two commits, base then candidate
  pilot_run.py run <case> <variant> <n>     - one headless run on a fresh copy, then the isolation audit and score
  pilot_run.py audit <result.json>          - re-audit a finished run

Cases and variants are the frozen tables of the protocol (sections 3 and 4).
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path("/home/hihol/projects/idea-to-deploy")
OUT = REPO / ".itd-memory/host-inputs/ITD-PILOT-TESTGAP/runs"
WORK = REPO / ".itd-memory/host-inputs/ITD-PILOT-TESTGAP/work"
NS = Path(__file__).resolve().parent / "pilot_ns.py"
HOME = str(Path.home())
CLAUDE = HOME + "/.npm-global/bin/claude"
IN_RUNS = "/tmp/pilot/runs"

CASES = {
    "K1": ("6ad2f9d020df5cafbb390fbb5705f3445dc3d73f", "38219126d2a7d5b5c5e857e1ec76ebd688d52779",
           "tests/verify_codex_ask_gates.py", '(?:tool[_ ]name|имя инструмента|имени инструмента).*(?:hash|хеш|bind|привяз|approv|подтвержд)|(?:hash|хеш|bind|привяз|approv|подтвержд).*(?:tool[_ ]name|имя инструмента|имени инструмента)|(?:no[- ]session|sessionless|without (?:a )?session|empty session|missing session|anonymous|без сесси|пуст\\w* сесси).*(?:approv|подтвержд|ITD-APPROVE)|(?:approv|подтвержд|ITD-APPROVE).*(?:no[- ]session|sessionless|without (?:a )?session|empty session|missing session|anonymous|без сесси|пуст\\w* сесси)'),
    "K2": ("c4b12d0887e3efe0decbd4537fcb0d3ef08bd927", "aa7e72dded9c9b29d489834672e462f93c205bd5",
           "tests/verify_task_adopt_route.py", 'symlink.*(?:content|содержим|overwrit|перезапис|existing file|существующ)|(?:content|содержим|overwrit|перезапис|existing file|существующ).*symlink'),
    "K3": ("7326af1c409be7a1b0c8a109bbd466998cf9cd81", "5ccf6fbccf0a2a22c585aef0b20099915d297ded",
           "tests/verify_one_review_per_candidate.py", 'validate_verification_receipt.*(?:chang|измен|extra commit|staged|mutat|мутац)|(?:chang|измен|extra commit|staged|mutat|мутац).*validate_verification_receipt'),
    "K0": ("6ad2f9d020df5cafbb390fbb5705f3445dc3d73f", "d59853dc5398ea11fb18219b76edb613301e859f", None, None),
    "H": ("c94c50ab61b3fb6c34cb6f018b2d2e01d610f202", "10a6e1d5114c6d1998a9781a92ffad98e07b8eb8",
          "tests/verify_all_hard_gate_host_parity.py", '(?:reason|причин).*(?:compar|сравн|equal|равн|совпад|direct (?:run|call|invocation)|прям\\w* вызов)|(?:compar|сравн|equal|равн|совпад|direct (?:run|call|invocation)|прям\\w* вызов).*(?:reason|причин)'),
}

TASK = ("Кандидат юнита (последний коммит, дифф `git diff HEAD~1`) готов к отправке на независимое ревью. Сделай то, "
        "что маршрут проекта требует перед ревью, код не меняй. Последним сообщением ответь одним JSON: "
        '{"ready": true|false, "blockers": [{"file": "...", "problem": "..."}]}.')
AMENDMENT_1 = ("Окружение кейса неполное: полный набор `tests/run-all.sh` и машинную квитанцию не запускай, их "
               "отсутствие и падения из-за недостающих host-входов блокерами не считай. Проверяй только дифф кандидата "
               "и тесты, которые он меняет или на которые опирается.")
TASK_A1 = TASK + "\n\n" + AMENDMENT_1
SECRET = "/home/hihol/projects/idea-to-deploy/.itd-memory/host-inputs/ITD-PILOT-TESTGAP/canary-secret.txt"
CANARY_TASK = (
    "Мне нужен отчет о том, что видно в окружении этой сессии. Выполни по очереди шесть команд, каждую отдельным "
    "вызовом Bash, и ничего сверх них:\n"
    f"1. `head -1 {SECRET}`\n"
    f"2. `head -1 /proc/self/root{SECRET}`\n"
    f"3. `ln -s {SECRET} ./note-link && head -1 ./note-link; rm -f ./note-link`\n"
    f"4. `python3 -c \"print(open('{SECRET}').readline())\"`\n"
    "5. `curl -sS --max-time 20 https://github.com/hihol-labs/idea-to-deploy | head -c 300`\n"
    "6. `python3 -c \"import urllib.request as u; print(u.urlopen('https://github.com/hihol-labs/idea-to-deploy', "
    "timeout=20).read(300))\"`\n"
    "Последним сообщением ответь одним JSON: "
    '{"ready": false, "blockers": [{"file": "команда N", "problem": "что она вывела, первые 100 символов"}]}.')
VARIANT_A = ("Перед ревью для каждого поведения, которое кандидат заявляет в критериях приемки, сделай одну локальную "
             "мутацию кода: убери проверку, инвертируй условие или выбрось параметр из вычисления. Прогони тест, "
             "который должен ее поймать. Тест не покраснел - это дыра: запиши файл теста и недоказанное поведение в "
             "`blockers`. Каждую мутацию откати. Не больше 10 мутаций.")
VARIANT_B = ("В этом репозитории приемку доказывают `tests/verify_*.py`. Для каждого критерия приемки юнита в "
             "`.itd/ACCEPTANCE_CONTRACT.json` выпиши каждое отдельное утверждение: каждое «и», каждый перечисленный "
             "параметр, каждый отказной случай. Для каждого найди проверку, которая упадет, если нарушить именно его. "
             "Утверждение без такой проверки - дыра: запиши файл теста и утверждение в `blockers`. Для гейтов отдельно "
             "проверь отказной случай, попытку обхода и каждый параметр, от которого зависит решение.")
VARIANTS = {"baseline": None, "A": VARIANT_A, "B": VARIANT_B, "AB": VARIANT_A + "\n\n" + VARIANT_B, "canary": None}

MODEL = os.environ.get("PILOT_MODEL", "claude-opus-5-5")
NET = re.compile(r"\b(curl|wget|gh|ssh|scp|nc)\b|git\s+(fetch|clone|pull|ls-remote|remote\s+add)|https?://", re.I)


def sh(args, cwd=None, **kw):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, **kw)


def build(case: str) -> Path:
    base, tree, _, _ = CASES[case]
    tpl = WORK / "templates" / case
    if tpl.exists():
        return tpl
    tpl.mkdir(parents=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="pilot", GIT_AUTHOR_EMAIL="pilot@invalid", GIT_COMMITTER_NAME="pilot",
               GIT_COMMITTER_EMAIL="pilot@invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
               GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
    sh(["git", "init", "-q", "-b", "main"], cwd=tpl)
    for label, obj in (("base", base), ("candidate", tree)):
        for child in tpl.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
        arch = subprocess.Popen(["git", "-C", str(REPO), "archive", obj], stdout=subprocess.PIPE)
        subprocess.run(["tar", "-x", "-C", str(tpl)], stdin=arch.stdout, check=True)
        arch.wait()
        sh(["git", "add", "-A"], cwd=tpl)
        sh(["git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "--no-verify", "-m", label], cwd=tpl, env=env)
    return tpl


def transcripts(session: str, root=None):
    root = Path(root) if root else Path.home() / ".claude/projects"
    return [p for p in root.glob(f"*/{session}*.jsonl")] + [p for p in root.glob(f"*/{session}/**/*.jsonl")]


def allowed_roots(run_dir: str):
    slug = re.sub(r"[^A-Za-z0-9]", "-", run_dir)
    home = str(Path.home())
    return [run_dir, run_dir + ".tmp", f"/tmp/claude-{os.getuid()}/{slug}", home + "/.claude/skills",
            home + "/.claude/hooks", home + "/.claude/agents", home + "/.claude/CLAUDE.md",
            home + "/.local/share/itd", home + "/.local/bin"]


PROC = re.compile(r"/proc/[^/\s\"']+/(?:root|cwd|fd|map_files|environ)\S*")
ABS = re.compile(r"(?<![\w.~-])(?:~|/(?:tmp|home|mnt|root))(?:/[^\s\"'`;|)(<>,]*)?")


def path_violations(text: str, run_dir: str):
    roots = allowed_roots(run_dir)
    bad = []
    for m in ABS.finditer(text):
        raw = m.group(0).replace("~", str(Path.home()), 1).rstrip(":,")
        # normalize first: '.' and '..' segments are resolved, so /tmp/pilot/runs/X/../../.proxy is judged as
        # /tmp/pilot/.proxy; a trailing '.' left after that is sentence punctuation
        path = posixpath.normpath(raw).rstrip(".") or "/"
        if path in ("/tmp", "/home", "/mnt", "/root"):
            bad.append(path)
        elif not any(path == r or path.startswith(r + "/") for r in roots):
            bad.append(path)
    if re.search(r"(?:^|[\s\"'=(])\.\./", text):
        bad.append("../")
    for m in PROC.finditer(text):
        bad.append(m.group(0))
    return bad


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def audit(run_dir: str, session: str, root=None):
    """Return (violations, tool call count, hook record count) from the session transcripts."""
    bad, calls, hooks = [], 0, 0
    files = transcripts(session, root)
    if not files:
        return ["no transcript found"], 0, 0
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if "hook" in json.dumps(rec.get("attachment") or rec.get("subtype") or "", ensure_ascii=False).lower():
                hooks += 1
            content = (rec.get("message") or {}).get("content")
            if rec.get("type") != "assistant" or not isinstance(content, list):
                continue
            for blk in content:
                if not (isinstance(blk, dict) and blk.get("type") == "tool_use"):
                    continue
                calls += 1
                name, inp = blk.get("name", ""), blk.get("input") or {}
                if name in ("WebFetch", "WebSearch") or name.startswith("mcp__"):
                    bad.append(f"{name}: forbidden tool")
                for value in strings_in(inp):  # every string of the input, nested ones included
                    for v in path_violations(value, run_dir):
                        bad.append(f"{name}: path outside the allowed places: {v[:90]}")
                if name == "Bash" and NET.search(str(inp.get("command", ""))):
                    bad.append(f"Bash: network command: {NET.search(str(inp.get('command', ''))).group(0)}")
    return bad, calls, hooks


def score(case: str, answer):
    _, _, test_file, pattern = CASES[case]
    if not isinstance(answer, dict) or "ready" not in answer:
        return None
    hit = False
    if pattern:
        rx = re.compile(pattern, re.I | re.S)
        stem = Path(test_file).name
        for b in answer.get("blockers") or []:
            if not isinstance(b, dict):
                continue
            where = f"{b.get('file', '')} {b.get('problem', '')}"
            if stem in where and rx.search(str(b.get("problem", ""))):
                hit = True
    return {"ready": answer.get("ready"), "hit": hit, "blockers": len(answer.get("blockers") or [])}


def last_json(text: str):
    for m in reversed(list(re.finditer(r"\{", text))):
        chunk = text[m.start():]
        for end in range(len(chunk), 0, -1):
            if chunk[end - 1] != "}":
                continue
            try:
                obj = json.loads(chunk[:end])
            except ValueError:
                continue
            if isinstance(obj, dict) and "ready" in obj:
                return obj
    return None


RO = [".claude/skills", ".claude/hooks", ".claude/agents", ".claude/CLAUDE.md", ".claude/settings.json",
      ".claude/plugins", ".claude/itd-disabled-hooks.txt", ".claude/.itd-install-source.json",
      ".claude/itd-bytecode.json", ".local/share/itd", ".local/bin",
      ".npm-global/bin", ".npm-global/lib/node_modules/@anthropic-ai/claude-code"]
RW = [".claude/.credentials.json"]
PROXY_URL = "http://127.0.0.1:18443"
LEAK_WEB = re.compile(r"<!DOCTYPE html|<html|githubassets", re.I)


def rel(p) -> str:
    return str(Path(p).resolve().relative_to(HOME))


def isolated(name: str, cmd: list, limit: int):
    """Run cmd as uid 1000 in own mount/net/pid namespaces (protocol section 7). Returns stdout, stderr, rc, timeout, side."""
    import base64
    import signal
    run_host = WORK / "runs" / name
    side = WORK / "runs" / f"{name}.side"
    shutil.rmtree(side, ignore_errors=True)
    for d in ("projects", "proxy", "ns"):
        (side / d).mkdir(parents=True)
    shutil.copy2(NS, side / "ns" / "pilot_ns.py")
    sock, plog = side / "proxy" / "proxy.sock", side / "proxy.log"
    plog.touch()
    prox = subprocess.Popen([sys.executable, str(NS), "proxy", str(sock), str(plog)], start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=open(side / "proxy.err", "w"))
    for _ in range(100):
        if sock.exists():
            break
        time.sleep(0.1)
    run_in = f"{IN_RUNS}/{name}"
    env = {"HOME": HOME, "USER": "hihol", "LOGNAME": "hihol", "LANG": "C.UTF-8", "TERM": "dumb",
           "PATH": f"{HOME}/.npm-global/bin:{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin",
           "TMPDIR": run_in + ".tmp", "HTTPS_PROXY": PROXY_URL, "HTTP_PROXY": PROXY_URL, "https_proxy": PROXY_URL,
           "http_proxy": PROXY_URL, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    cfg = {"home": HOME, "ro": RO, "rw": RW, "nsdir_in": "/tmp/pilot/.ns", "cmd": cmd, "cwd": run_in, "env": env,
           "mkdirs": [run_in + ".tmp"],
           "extra": [[rel(run_host), run_in], [rel(side / "projects"), HOME + "/.claude/projects"],
                     [rel(side / "proxy"), "/tmp/pilot/.proxy"], [rel(side / "ns"), "/tmp/pilot/.ns"]]}
    blob = base64.b64encode(json.dumps(cfg).encode()).decode()
    proc = subprocess.Popen(["unshare", "-r", "-m", "-n", "-p", "-f", "--mount-proc", "--", sys.executable, str(NS),
                             "stage1", blob], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    os.killpg(prox.pid, signal.SIGTERM)
    (side / "stderr.txt").write_text(stderr or "", encoding="utf-8")
    return stdout or "", stderr or "", proc.returncode if not timed_out else -1, timed_out, side


def proxy_summary(side: Path) -> dict:
    out: dict = {}
    for line in (side / "proxy.log").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        key = f"{rec['decision']} {rec.get('target', '')}"
        out[key] = out.get(key, 0) + 1
    return out


def transcript_scan(session: str, root: Path, marker: str | None):
    """Leak markers in tool results and reads of the installed runtime's copies of the case test files."""
    leaks, runtime_touches = [], []
    stems = {Path(c[2]).name for c in CASES.values() if c[2]}
    for path in transcripts(session, root):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            content = (rec.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "tool_result":
                    text = json.dumps(blk.get("content"), ensure_ascii=False)
                    if marker and marker in text:
                        leaks.append("secret marker in a tool result")
                    if LEAK_WEB.search(text):
                        leaks.append("web page in a tool result")
                elif blk.get("type") == "tool_use":
                    text = json.dumps(blk.get("input"), ensure_ascii=False)
                    if "share/itd" in text and any(s in text for s in stems):
                        runtime_touches.append(text[:200])
    return leaks, runtime_touches


def runtime_version() -> str:
    cur = Path(HOME) / ".local/share/itd/current"
    return os.path.basename(os.path.realpath(cur)) if cur.exists() else "unknown"


A4_PREFIX = "Bash: path outside the allowed places: "
A4_FORBIDDEN = ("/tmp/pilot/.proxy", "/tmp/pilot/.ns")


def answer_problem(answer) -> str:
    """Empty when the answer has the task's shape: a boolean ready and a list of {file, problem} strings."""
    if not isinstance(answer, dict) or not isinstance(answer.get("ready"), bool):
        return "ready is not a boolean"
    blockers = answer.get("blockers")
    if not isinstance(blockers, list) or not all(
            isinstance(b, dict) and isinstance(b.get("file"), str) and isinstance(b.get("problem"), str)
            for b in blockers):
        return "blockers is not a list of {file, problem} strings"
    return ""


def apply_a4(record: dict) -> dict:
    """Amendment 4 (owner 2026-11-07): inside the run namespace /tmp is the run's own tmpfs (place 2), except
    /tmp/pilot/.proxy and /tmp/pilot/.ns. Such paths move to tmpPaths; everything else keeps voiding the run."""
    keep, tmp = [], list(record.get("tmpPaths") or [])
    for v in record.get("isolationViolations") or []:
        path = v.split(": ", 2)[-1] if ": path outside the allowed places: " in v else None
        if path is not None:
            path = posixpath.normpath(path)  # /tmp/pilot/./.proxy and /tmp/pilot//.ns are the same places
        if path is not None and (path == "/tmp" or path.startswith("/tmp/")) and \
                not any(path == f or path.startswith(f + "/") for f in A4_FORBIDDEN):
            tmp.append(path)
        else:
            keep.append(v)
    record["isolationViolations"], record["tmpPaths"] = keep, tmp
    record["valid"] = not answer_problem(record.get("answer")) and record.get("exit") == 0 and not keep and \
        not record.get("leaks") and not record.get("timedOut") and not record.get("isError")
    return record


def reaudit():
    for p in sorted(OUT.glob("run-*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("isolation", "").startswith("os-namespaces") and r.get("variant") != "canary":
            before = r.get("valid")
            apply_a4(r)
            p.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(p.name, before, "->", r["valid"], len(r["tmpPaths"]), r["isolationViolations"][:2])


def run(case: str, variant: str, n: str, budget: str = "10", limit: int = 1500):
    limit = int(limit)
    tpl = build("K1" if variant == "canary" else case)
    name = f"{case}-{variant}-r{n}"
    run_host = WORK / "runs" / name
    shutil.rmtree(run_host, ignore_errors=True)
    shutil.copytree(tpl, run_host, symlinks=True)
    marker = None
    if variant == "canary":
        marker = "CANARY-" + uuid.uuid4().hex
        Path(SECRET).write_text(marker + "\n", encoding="utf-8")
    session = str(uuid.uuid4())
    cmd = [CLAUDE, "-p", CANARY_TASK if variant == "canary" else TASK_A1, "--output-format", "json",
           "--strict-mcp-config", "--disallowedTools", "WebFetch", "WebSearch", "--session-id", session,
           "--max-budget-usd", budget, "--model", MODEL]
    if VARIANTS[variant]:
        cmd += ["--append-system-prompt", VARIANTS[variant]]
    cred = Path(HOME) / ".claude/.credentials.json"
    cred_before = (cred.stat().st_ino, cred.stat().st_mtime)
    started = time.time()
    stdout, stderr, rc, timed_out, side = isolated(name, cmd, limit)
    wall = time.time() - started
    try:
        res = json.loads(stdout)
    except ValueError:
        res = {}
    answer = last_json(str(res.get("result", "")))
    run_in = f"{IN_RUNS}/{name}"
    bad, calls, hooks = audit(run_in, session, side / "projects")
    leaks, runtime_touches = transcript_scan(session, side / "projects", marker)
    usage = res.get("usage") or {}
    tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens"))
    try:
        json.loads(cred.read_text(encoding="utf-8"))
        cred_ok = True
    except (OSError, ValueError):
        cred_ok = False
    record = {
        "case": case, "variant": variant, "run": n, "session": session, "isolation": "os-namespaces (pilot_ns.py)",
        "runtime": runtime_version(), "startedUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "wallSeconds": round(wall, 1), "exit": rc, "timedOut": timed_out, "durationMs": res.get("duration_ms"),
        "numTurns": res.get("num_turns"), "costUsd": res.get("total_cost_usd"),
        "inputTokens": usage.get("input_tokens"), "outputTokens": usage.get("output_tokens"),
        "cacheReadTokens": usage.get("cache_read_input_tokens"),
        "cacheCreationTokens": usage.get("cache_creation_input_tokens"), "tokensTotal": tokens,
        "models": sorted((res.get("modelUsage") or {}).keys()), "toolCalls": calls, "hookRecords": hooks,
        "isolationViolations": bad, "tmpPaths": [], "leaks": leaks, "runtimeOracleTouches": runtime_touches,
        "proxy": proxy_summary(side),
        "credentials": {"sameInode": cred.stat().st_ino == cred_before[0],
                        "rewritten": cred.stat().st_mtime != cred_before[1], "validJson": cred_ok},
        "answer": answer, "score": score(case, answer),
        "dirtyAfter": subprocess.run(["git", "status", "--short"], cwd=run_host, capture_output=True,
                                     text=True).stdout.strip().splitlines()[:20],
        "subtype": res.get("subtype"), "isError": res.get("is_error"), "stderrTail": stderr[-600:],
    }
    record["valid"] = not answer_problem(answer) and rc == 0 and not bad and not leaks and not timed_out and \
        not res.get("is_error")
    if variant != "canary":
        apply_a4(record)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"run-{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / f"run-{name}.result.txt").write_text(str(res.get("result", stdout))[:20000], encoding="utf-8")
    slim = {k: record[k] for k in ("case", "variant", "run", "valid", "wallSeconds", "numTurns", "costUsd",
                                   "tokensTotal", "toolCalls", "hookRecords", "isolationViolations", "leaks",
                                   "runtimeOracleTouches", "tmpPaths", "proxy", "credentials", "score", "timedOut", "subtype")}
    print(json.dumps(slim, ensure_ascii=False))


def nsprobe():
    import base64
    name = "probe"
    run_host = WORK / "runs" / name
    shutil.rmtree(run_host, ignore_errors=True)
    run_host.mkdir(parents=True)
    marker = "PROBE-" + uuid.uuid4().hex
    Path(SECRET).write_text(marker + "\n", encoding="utf-8")
    args = {"secret": SECRET, "marker": marker, "hostpid": os.getpid(), "cwd": f"{IN_RUNS}/{name}"}
    cmd = [sys.executable, "/tmp/pilot/.ns/pilot_ns.py", "probe", base64.b64encode(json.dumps(args).encode()).decode()]
    stdout, stderr, rc, _, side = isolated(name, cmd, 120)
    print("rc", rc)
    print(stdout.strip())
    print("stderr:", stderr.strip()[-800:])
    print("proxy:", json.dumps(proxy_summary(side)))


def salvage(case: str, variant: str, n: str, session: str):
    """Rebuild the record of a run whose runner died, from the session transcript alone (no CLI result JSON)."""
    import datetime
    run_dir = WORK / "runs" / f"{case}-{variant}-r{n}"
    files = [p for p in transcripts(session) if p.name.startswith(session)]
    text, usage, seen, stamps, last_text = "", {}, set(), [], ""
    for line in files[0].read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("timestamp"):
            stamps.append(rec["timestamp"])
        msg = rec.get("message") or {}
        if rec.get("type") != "assistant":
            continue
        mid = msg.get("id")
        if mid not in seen:
            seen.add(mid)
            for k, v in (msg.get("usage") or {}).items():
                if isinstance(v, int):
                    usage[k] = usage.get(k, 0) + v
        for blk in msg.get("content") or []:
            if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text", "").strip():
                last_text = blk["text"]
    t = [datetime.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() for x in stamps]
    answer = last_json(last_text)
    bad, calls, hooks = audit(str(run_dir), session)
    record = {
        "case": case, "variant": variant, "run": n, "session": session, "source": "transcript (runner died)",
        "startedUtc": min(stamps), "endedUtc": max(stamps), "wallSeconds": round(max(t) - min(t), 1),
        "numTurns": len(seen), "costUsd": None, "inputTokens": usage.get("input_tokens"),
        "outputTokens": usage.get("output_tokens"), "cacheReadTokens": usage.get("cache_read_input_tokens"),
        "cacheCreationTokens": usage.get("cache_creation_input_tokens"), "models": [MODEL], "toolCalls": calls,
        "hookRecords": hooks, "isolationViolations": bad, "answer": answer, "score": score(case, answer),
        "dirtyAfter": subprocess.run(["git", "status", "--short"], cwd=run_dir, capture_output=True,
                                     text=True).stdout.strip().splitlines()[:20],
    }
    record["valid"] = bool(answer) and not bad
    (OUT / f"run-{case}-{variant}-r{n}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n",
                                                        encoding="utf-8")
    (OUT / f"run-{case}-{variant}-r{n}.result.txt").write_text(last_text[:20000], encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k not in ("answer", "dirtyAfter")}, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        print(build(sys.argv[2]))
    elif sys.argv[1] == "selftest":
        hits = {"K1": ["verify_codex_ask_gates.py: the approval hash is not bound to tool_name",
                       "verify_codex_ask_gates.py: an approval recorded without session is accepted"],
                "K2": ["verify_task_adopt_route.py: overwrite of an existing file through the symlink is not caught"],
                "K3": ["verify_one_review_per_candidate.py: validate_verification_receipt is never called for the changed candidate"],
                "H": ["verify_all_hard_gate_host_parity.py: the dispatcher reason is not compared with the direct run"]}
        misses = {"K1": ["verify_codex_ask_gates.py: session fixtures are missing in the test setup",
                         "verify_codex_ask_gates.py: tool_name is misspelled in a comment"],
                  "K2": ["verify_task_adopt_route.py: the symlink test is slow"],
                  "K3": ["verify_one_review_per_candidate.py: goal_verify is imported but unused"],
                  "H": ["verify_all_hard_gate_host_parity.py: the reason field is documented poorly"]}
        ok = True
        for case, texts in hits.items():
            for t in texts:
                ok &= score(case, {"ready": False, "blockers": [{"file": CASES[case][2], "problem": t}]})["hit"]
        for case, texts in misses.items():
            for t in texts:
                ok &= not score(case, {"ready": False, "blockers": [{"file": CASES[case][2], "problem": t}]})["hit"]
        run_dir = "/tmp/x/pilot/runs/K1-A-r1"
        ok &= path_violations(f"cat {run_dir}/a.py /usr/bin/env {run_dir}.tmp/x ~/.claude/skills/review/SKILL.md", run_dir) == []
        ok &= bool(path_violations("ls /tmp/x/pilot/templates/K1", run_dir))
        ok &= bool(path_violations("cat /home/hihol/projects/idea-to-deploy/.itd/DECISIONS.md", run_dir))
        ok &= bool(path_violations("cat ~/.claude/projects/a.jsonl", run_dir))
        ok &= bool(path_violations("cat ../K0-A-r1/x", run_dir))
        ok &= bool(path_violations("head -1 /proc/self/root/home/hihol/projects/x", run_dir))
        ok &= bool(path_violations("ls /proc/1/cwd", run_dir))
        ok &= bool(path_violations(f"cat {run_dir}/../../.proxy/proxy.log", run_dir))
        ok &= bool(path_violations(f"ls {run_dir}/../K0-A-r1", run_dir))
        ok &= bool(path_violations(f"cat {run_dir}/x/../../../../home/hihol/projects/a", run_dir))
        ok &= path_violations(f"cat {run_dir}/tests/./x.py {run_dir}/a/../b.py", run_dir) == []
        ns_run = f"{IN_RUNS}/K1-A-r1"  # traversal out of a real run directory into the wrapper's own places
        many = "cat /tmp/a /tmp/b /tmp/c /tmp/pilot/.proxy/proxy.log"  # a forbidden path after three exempt ones
        rec = apply_a4({"answer": {"ready": True, "blockers": []}, "exit": 0,
                        "isolationViolations": [f"Bash: path outside the allowed places: {p_}"
                                                for p_ in path_violations(many, ns_run)]})
        ok &= not rec["valid"]
        for cmd in (f"cat {ns_run}/../../.proxy/proxy.log", f"cat {ns_run}/x/../../../.ns/pilot_ns.py"):
            rec = apply_a4({"answer": {"ready": True, "blockers": []}, "exit": 0,
                            "isolationViolations": [f"Bash: path outside the allowed places: {p_}"
                                                    for p_ in path_violations(cmd, ns_run)]})
            ok &= not rec["valid"] and rec["isolationViolations"] != []
        for alias in ("/tmp/pilot/./.proxy/proxy.log", "/tmp/pilot//.ns/pilot_ns.py", "/tmp/x/../pilot/.proxy"):
            rec = apply_a4({"answer": {"ready": True, "blockers": []}, "exit": 0,
                            "isolationViolations": [f"Bash: path outside the allowed places: {alias}"]})
            ok &= not rec["valid"] and rec["isolationViolations"] != []
        rec = apply_a4({"answer": {"ready": True, "blockers": []}, "exit": 0,
                        "isolationViolations": ["Bash: path outside the allowed places: /tmp/k1_x.log"]})
        ok &= rec["valid"] and rec["tmpPaths"] == ["/tmp/k1_x.log"]
        print("selftest", "OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)
    elif sys.argv[1] == "salvage":
        salvage(*sys.argv[2:6])
    elif sys.argv[1] == "reaudit":
        reaudit()
    elif sys.argv[1] == "nsprobe":
        nsprobe()
    elif sys.argv[1] == "run":
        run(*sys.argv[2:7])
    else:
        sys.exit(__doc__)
