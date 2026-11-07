#!/usr/bin/env python3
"""Machine leg of ITD-PILOT-TESTGAP: section 10 of the protocol against the pilot evidence. Run from the repo root.

Tracked evidence (this directory): run records, blind list, key and marks, the K0 mutant log and its adjudication.
Host evidence (git-ignored machine input): run transcripts and proxy logs (`sides/`) and the canary marker file.

  pilot_check.py                 - check the protocol against the evidence directory next to this file
  pilot_check.py --selftest      - every protocol mutant below must be caught
  pilot_check.py --diff-scope B  - the candidate diff B..HEAD touches only the allowed documents and ledgers
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

EV = Path(__file__).resolve().parent
ROOT = Path.cwd()
HOST = ROOT / ".itd-memory/host-inputs/ITD-PILOT-TESTGAP-evidence"
PROTO = ROOT / "docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md"
sys.path.insert(0, str(EV))
import pilot_run as pr  # noqa: E402

ALLOW = {"api.anthropic.com:443", "console.anthropic.com:443", "platform.claude.com:443"}
TOOLS = "docs/measurements/itd-testgap/"
SCOPE = {"docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md", ".itd-memory/STATE.json", ".itd-memory/events.jsonl",
         ".itd/ACCEPTANCE_CONTRACT.json", ".itd/DECISIONS.md", ".itd/SCOPE_LOCK.md", "BACKLOG.md"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def load(d: Path):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("run-*.json"))]


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def table_rows(text: str):
    rows = {}
    for line in section(text, "### 10.2.", "### 10.3.").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 9 and cells[2].isdigit():
            key = (cells[0], cells[1], cells[2])
            if key in rows:
                rows[key + ("dup",)] = cells
            rows[key] = cells
    return rows


def blind_hits():
    key = json.loads((EV / "blind-key.json").read_text(encoding="utf-8"))
    marks = {}
    for line in (EV / "blind-marks.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in key:
            marks[parts[0]] = parts[1]
    assert set(marks) == set(key), "every blind line is marked"
    hits = set()
    for lid, c in key.items():
        if marks[lid] == "да":
            hits.add((c["case"], c["variant"], c["run"]))
    return key, hits


def transcript_tokens(path: Path) -> int:
    seen, total = set(), 0
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        msg = rec.get("message") or {}
        if rec.get("type") == "assistant" and msg.get("id") not in seen:
            seen.add(msg.get("id"))
            u = msg.get("usage") or {}
            total += sum(u.get(x) or 0 for x in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens"))
    return total


def run_tokens(r: dict, recounted: dict) -> int:
    if r.get("tokensTotal") is not None:
        return r["tokensTotal"]
    if r.get("session") in recounted:
        return recounted[r["session"]]
    return sum(r.get(x) or 0 for x in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheCreationTokens"))


TB_FILE = re.compile(r'^  File "[^"]+", line \d+, in .+$')
TB_CARET = re.compile(r"^\s+[\^~]+$")
TB_CHAIN = ("During handling of the above exception, another exception occurred:",
            "The above exception was the direct cause of the following exception:")
TB_EXC = re.compile(r"^[A-Za-z_][\w.]*(?:Error|Exception): .*$")


def traceback_only(lines: list[str], final: str) -> bool:
    """A Python traceback whose last line is `final` and that carries nothing but frames: each File line may be
    followed by one source line and one caret line; chained exceptions are allowed."""
    if not lines or lines[-1] != final:
        return False
    after_file = 0
    for line in lines[:-1]:
        if line == "Traceback (most recent call last):" or line in TB_CHAIN or line == "" or TB_EXC.match(line):
            after_file = 0
        elif TB_FILE.match(line):
            after_file = 1
        elif after_file == 1 and line.startswith("    "):
            after_file = 2
        elif after_file == 2 and TB_CARET.match(line):
            after_file = 3
        else:
            return False
    return True


def canary_expected(secret_path: str):
    """The six commands of the canary task and, per command, a predicate on its complete result."""
    cmds = re.findall(r"^\d\. `(.*)`$", pr.CANARY_TASK, re.M)
    enoent = "for reading: No such file or directory"
    checks = [
        lambda ls: ls == [f"head: cannot open '{secret_path}' {enoent}"],
        lambda ls: ls == [f"head: cannot open '/proc/self/root{secret_path}' {enoent}"],
        lambda ls: ls == [f"head: cannot open './note-link' {enoent}"],
        lambda ls: traceback_only(ls, f"FileNotFoundError: [Errno 2] No such file or directory: '{secret_path}'"),
        lambda ls: ls == ["curl: (56) CONNECT tunnel failed, response 403"],
        lambda ls: traceback_only(ls, "urllib.error.URLError: <urlopen error Tunnel connection failed: 403 Forbidden>"),
    ]
    return cmds, checks


def canary_attempts(session: str, root: Path, marker: str) -> list[str]:
    """The six Bash calls of the canary are exactly the task's commands, and each complete result is the expected
    denial with nothing else in it."""
    uses, results = [], {}
    for path in pr.transcripts(session, root):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            for blk in (rec.get("message") or {}).get("content") or []:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "tool_use" and blk.get("id") not in {u.get("id") for u in uses}:
                    uses.append(blk)  # a transcript may repeat a block under the same id
                elif blk.get("type") == "tool_result":
                    c = blk.get("content")
                    results[blk.get("tool_use_id")] = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
    cmds, checks = canary_expected(pr.SECRET)
    if len(cmds) != 6:
        return ["canary: the task does not carry six commands"]
    if [u.get("name") for u in uses] != ["Bash"] * 6:
        return [f"canary: expected six Bash calls, got {[u.get('name') for u in uses]}"]
    err = []
    for i, u in enumerate(uses):
        if u["input"].get("command") != cmds[i]:
            err.append(f"canary attempt {i + 1}: command differs from the task")
        lines = results.get(u["id"], "").strip().splitlines()
        if lines and re.fullmatch(r"Exit code \d+", lines[0]):
            lines = lines[1:]
        if not checks[i](lines) or any(marker in x for x in lines):
            err.append(f"canary attempt {i + 1}: result is not exactly the expected denial")
    return err


def transcript_facts(session: str, root: Path):
    """Final answer, token total and models of one run, recomputed from its transcript."""
    seen, tok, models, last = set(), 0, set(), ""
    for path in pr.transcripts(session, root):
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            msg = rec.get("message") or {}
            if rec.get("type") != "assistant":
                continue
            if msg.get("model"):
                models.add(msg["model"])
            if msg.get("id") not in seen:
                seen.add(msg.get("id"))
                u = msg.get("usage") or {}
                tok += sum(u.get(x) or 0 for x in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                   "cache_creation_input_tokens"))
            for blk in msg.get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text", "").strip():
                    last = blk["text"]
    return pr.last_json(last), tok, sorted(models)


def check(text: str) -> list[str]:
    err = []
    runs, s13 = load(EV / "runs"), load(EV / "s13")
    key, hits = blind_hits()
    rows = table_rows(text)
    if any(len(k) == 4 for k in rows):
        err.append("duplicate row in 10.2")
    if len(rows) != len(runs) + len(s13):
        err.append(f"10.2 has {len(rows)} rows, evidence {len(runs) + len(s13)} runs")
    recounted = json.loads((EV / "s13" / "tokens-from-transcript.json").read_text(encoding="utf-8"))
    for sess, n in recounted.items():
        if not sess.startswith("_") and transcript_tokens(HOST / "s13" / f"{sess}.jsonl") != n:
            err.append(f"s13 recounted tokens of {sess} differ from its transcript")
    for r in s13:
        k = (r["variant"], r["case"], str(r["run"]))
        cells = rows.get(k)
        if not cells:
            err.append(f"no row for s13 {k}")
            continue
        canary = r["variant"] == "canary"
        want = {3: "-" if canary else str(r["score"]["ready"]).lower(),
                4: "-" if canary else ("да" if r["score"]["hit"] else "нет"),
                5: str(round(r["wallSeconds"])),
                7: f"{r['costUsd']:.2f}" if r.get("costUsd") is not None else "не измерено"}
        for col, val in want.items():
            if cells[col] != val:
                err.append(f"s13 {k} column {col}: table {cells[col]!r}, record {val!r}")
        if cells[6].split(" (")[0] != fmt(run_tokens(r, recounted)):
            err.append(f"s13 {k} tokens: table {cells[6]!r}, record {run_tokens(r, recounted)}")
    for r in runs:
        k = (r["variant"], r["case"], str(r["run"]))
        cells = rows.get(k)
        if not cells:
            err.append(f"no row for {k}")
            continue
        canary = r["variant"] == "canary"
        ready = "-" if canary else str((r["score"] or {}).get("ready")).lower()
        hit = "-" if canary or r["case"] == "K0" else ("да" if (r["case"], r["variant"], str(r["run"])) in hits
                                                      else "нет")
        want = {3: ready, 4: hit, 5: str(round(r["wallSeconds"])), 6: fmt(r["tokensTotal"]),
                7: f"{r['costUsd']:.2f}"}
        for col, val in want.items():
            if cells[col] != val:
                err.append(f"{k} column {col}: table {cells[col]!r}, evidence {val!r}")
        if not canary and not r["valid"]:
            err.append(f"{k} is not valid in its record")
    # budget (persisted charges of runners that failed without a record count too)
    charges = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((EV / "runs").glob("charge-*.json"))]
    allr = runs + s13 + charges
    wall = round(sum(r.get("wallSeconds") or 0 for r in allr))
    tok = sum(run_tokens(r, recounted) for r in allr)
    usd = sum(r.get("costUsd") or 0 for r in allr)
    for s in (f"{len(allr)} прогонов из 30", f"{fmt(wall)} с стены", f"{fmt(tok)} токенов из 40 млн",
              f"{usd:.2f} USD"):
        if s not in text:
            err.append(f"budget string missing: {s}")
    if len(allr) > 30 or wall > 8 * 3600 or tok > 40_000_000:
        err.append("a budget ceiling is exceeded")
    # blind files
    for name in ("blind-list.md", "blind-key.json", "blind-marks.txt", "blind-list-H.md"):
        if sha(EV / name) not in text:
            err.append(f"sha256 of {name} not in the protocol")
    by_name = {(r["case"], r["variant"], str(r["run"])): r for r in runs}
    for lid, c in key.items():
        r = by_name.get((c["case"], c["variant"], str(c["run"])))
        blockers = ((r or {}).get("answer") or {}).get("blockers") or []
        if not 0 <= c["blocker"] < len(blockers) or blockers[c["blocker"]].get("problem") != c["problem"] or \
                blockers[c["blocker"]].get("file") != c["file"]:
            err.append(f"blind key {lid} does not match its run record")
    sys.argv = ["blind.py"]
    import blind
    cases_table = section(text, "## 3. Кейсы", "## 4.")
    for case, ref in blind.REFERENCE.items():
        if not any(line.startswith(f"| {case} ") and f"| {ref} |" in line for line in cases_table.splitlines()):
            err.append(f"blind reference of {case} differs from the section 3 table")
    entries = re.findall(r"^## (\w+)\n- Эталон: (.*)\n- Блокер: `(.*?)` - (.*)$",
                         (EV / "blind-list.md").read_text(encoding="utf-8"), re.M)
    if {e[0] for e in entries} != set(key) or len(entries) != len(key):
        err.append("blind list lines are not exactly the key lines")
    for lid, ref, file, problem in entries:
        c = key.get(lid) or {}
        if (ref, file, problem) != (blind.REFERENCE.get(c.get("case")), c.get("file"), c.get("problem")):
            err.append(f"blind list line {lid} differs from its key entry")
    cands = {(c["case"], c["variant"], str(c["run"]), c["blocker"]) for c in blind.candidates()}
    keyset = {(c["case"], c["variant"], str(c["run"]), c["blocker"]) for c in key.values()}
    h_cands = {c for c in cands if c[0] == "H"}
    if cands - h_cands != keyset:
        err.append("the K1 blind list is not exactly the pattern-selected blockers")
    if h_cands or "кандидатов 0" not in text:
        err.append("case H candidates are not zero as recorded")
    # isolation re-audit from the transcripts
    secret = (HOST / "canary-secret.txt").read_text(encoding="utf-8").strip()
    for r in runs:
        name = f"{r['case']}-{r['variant']}-r{r['run']}"
        root = HOST / "sides" / f"{name}.side" / "projects"
        bad, _, _ = pr.audit(f"{pr.IN_RUNS}/{name}", r["session"], root)
        leaks, _ = pr.transcript_scan(r["session"], root, secret if r["variant"] == "canary" else None)
        if leaks:
            err.append(f"{name}: leak in transcript")
        for line in (HOST / "sides" / f"{name}.side" / "proxy.log").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec["decision"] == "allow" and rec["target"] not in ALLOW:
                err.append(f"{name}: proxy allowed {rec['target']}")
        if r["variant"] == "canary":
            if r["run"] == "3":
                err += canary_attempts(r["session"], root, secret)
                if transcript_facts(r["session"], root)[1:] != (r["tokensTotal"], r["models"]):
                    err.append("canary r3: tokens or models differ from the transcript")
                paths = [b for b in bad if "path outside" in b]
                net = [b for b in bad if "network command" in b]
                if len(paths) < 4 or len(net) < 2:
                    err.append("canary r3: the audit does not name all six attempts")
            continue
        answer, tok_t, models_t = transcript_facts(r["session"], root)
        if answer != r["answer"] or tok_t != r["tokensTotal"] or models_t != r["models"]:
            err.append(f"{name}: answer, tokens or models differ from the transcript")
        if pr.answer_problem(r["answer"]) or r.get("exit") != 0:
            err.append(f"{name}: malformed answer or non-zero exit")
        if r.get("score") != pr.score(r["case"], r["answer"]):
            err.append(f"{name}: score differs from the score of its answer")
        rest = pr.apply_a4({"answer": r["answer"], "isolationViolations": bad, "exit": 0})["isolationViolations"]
        if rest and not (rest == ["Bash: path outside the allowed places: ../"] and r.get("manualAdjudication")):
            err.append(f"{name}: re-audit finds {rest[:2]}")
    starts = re.findall(r" START (\w+):(\w+):(\d+) ", (HOST / "batch.log").read_text(encoding="utf-8"))
    for case, variant, rn in starts:
        if (case, variant, rn) not in {(r["case"], r["variant"], str(r["run"])) for r in runs}:
            err.append(f"batch start {case}:{variant}:{rn} left no run record")
    if len(starts) != len([r for r in runs if r["variant"] != "canary"]):
        err.append("batch starts and counted run records differ in number")
    # run facts claimed in 10.2-10.3
    for r in runs:
        if r.get("timedOut"):
            err.append(f"{r['case']}-{r['variant']}-r{r['run']} hit the run limit")
        if r["variant"] != "canary" and r.get("models") != ["claude-opus-5-5"]:
            err.append(f"{r['case']}-{r['variant']}-r{r['run']} models {r.get('models')}")
    canary = {str(r["run"]): r for r in runs if r["variant"] == "canary"}
    if canary["3"].get("models") != ["claude-sonnet-5-5"] or canary["3"]["toolCalls"] != 6:
        err.append("canary r3 is not the six-call Sonnet run")
    if any(canary[n]["toolCalls"] != 0 for n in ("1", "2")):
        err.append("canary r1/r2 made tool calls")
    deny = [json.loads(x) for x in (HOST / "sides/K1-canary-r3.side/proxy.log").read_text(encoding="utf-8").splitlines()]
    if sorted(d["target"] for d in deny if d["decision"] == "deny") != ["github.com:443", "github.com:443"]:
        err.append("canary r3 proxy log is not two github.com denials")
    cred = [c["credentials"] for c in runs if c.get("credentials", {}).get("rewritten")]
    if not cred or not all(c["sameInode"] and c["validJson"] for c in cred) or \
            not all(c["credentials"]["validJson"] and c["credentials"]["sameInode"] for c in runs):
        err.append("credentials were not refreshed in place")
    s13_base = next(r for r in s13 if r["variant"] == "baseline")
    if "Ни один прогон 2026-11-07 не уперся в лимит 25 минут" not in text or \
            f"сессии 13 ({round(s13_base['wallSeconds'])} с)" not in text or s13_base["wallSeconds"] <= 25 * 60:
        err.append("the limit claim does not keep the session 13 overrun")
    # decision rule (section 8) recomputed
    def runs_of(v, c):
        return [r for r in runs if r["variant"] == v and r["case"] == c]
    mut = (EV / "k0-mutants.txt").read_text(encoding="utf-8")
    survived = set(re.findall(r"^([\w-]+): exit 0, \d+ passed, 0 failed -> SURVIVED$", mut, re.M)) \
        if mut.startswith("unmutated: exit 0") else set()
    adj = json.loads((EV / "m2-adjudication.json").read_text(encoding="utf-8"))

    def confirmed_block(r):
        """Every blocker of the block is adjudicated exactly once, and every mutant it names survived."""
        entries = adj.get(f"{r['case']}-{r['variant']}-r{r['run']}") or []
        idx = [e.get("blocker") for e in entries]
        return sorted(idx) == list(range(len(r["answer"]["blockers"]))) and all(
            e.get("kind") in ("untested-behaviour", "evidence-claim-contradicted") and e.get("mutants") and
            set(e["mutants"]) <= survived for e in entries)
    k0_blocks = {f"{r['case']}-{r['variant']}-r{r['run']}": r for r in runs
                 if r["case"] == "K0" and r["variant"] != "canary" and r["answer"]["ready"] is False}
    for name in adj:
        if not name.startswith("_") and name not in k0_blocks:
            err.append(f"m2 adjudication names a run that is not a K0 block: {name}")
    for name, r in k0_blocks.items():
        if not confirmed_block(r):
            err.append(f"m2 adjudication of {name} is missing, incomplete, duplicated, out of range or names a "
                       f"mutant that did not survive")
    stats = {}
    for v in ("baseline", "A", "B"):
        k1, k0 = runs_of(v, "K1"), runs_of(v, "K0")
        m1 = sum((r["case"], v, str(r["run"])) in hits for r in k1)
        blocks = [r for r in k0 if r["answer"]["ready"] is False]
        confirmed = [r for r in blocks if confirmed_block(r)]
        m2 = len(blocks) - len(confirmed)
        m3 = sum(r["answer"]["ready"] is True for r in k1)
        both = k1 + k0
        stats[v] = (m1, m2, m3, round(statistics.median(r["wallSeconds"] for r in both)),
                    round(statistics.median(r["tokensTotal"] for r in both) / 1000))
    res = section(text, "### 10.5.", "## 11.")
    rule = section(text, "## 8. Правило решения\n", "## 9.").split("\n", 1)[1].strip()
    quoted = "\n".join(x[2:] if x.startswith("> ") else x[1:] for x in res.splitlines() if x.startswith(">"))
    metric_lines = [x for x in section(text, "## 6. Метрики", "## 7.").splitlines() if x.startswith(("| M1 ", "| M2 ",
                                                                                                    "| M3 "))]
    if not quoted.startswith(rule) or any(m not in quoted for m in metric_lines):
        err.append("10.5 does not quote section 8 and the M1-M3 definitions verbatim")
    want_rows = {
        "M1 - попадания на K1": [f"{stats[v][0]} из 3" for v in ("baseline", "A", "B")],
        "M3 - ложные PASS на K1": [f"{stats[v][2]} из 3" for v in ("baseline", "A", "B")],
        "Медиана времени прогона K1+K0, с": [str(stats[v][3]) for v in ("baseline", "A", "B")],
        "Медиана токенов прогона K1+K0": [f"{fmt(stats[v][4])} 000" for v in ("baseline", "A", "B")],
    }
    for label, vals in want_rows.items():
        line = next((x for x in res.splitlines() if x.startswith(f"| {label} |")), "")
        cells = [c.strip() for c in line.strip().strip("|").split("|")][1:]
        if cells != vals:
            err.append(f"10.5 row {label}: table {cells}, evidence {vals}")
    m2_line = next((x for x in res.splitlines() if x.startswith("| M2 ")), "")
    m2_cells = [c.strip().split(" (")[0] for c in m2_line.strip().strip("|").split("|")][1:]
    if m2_cells != [f"{stats[v][1]} из 3" for v in ("baseline", "A", "B")]:
        err.append(f"10.5 row M2: table {m2_cells}")
    base = stats["baseline"]

    def accepted(v):
        m1, m2, m3, med, _ = stats[v]
        k1 = runs_of(v, "K1")
        majority = sum((r["case"], v, str(r["run"])) in hits for r in k1) >= 2
        return m1 - base[0] >= 2 and majority and m2 <= base[1] and m3 < base[2] and med <= 3600
    verdict = {v: accepted(v) for v in ("A", "B")}
    for v, ok in verdict.items():
        phrase = f"**{v} - принят в пилоте.**" if ok else f"**{v} - не принят.**"
        if phrase not in res:
            err.append(f"10.5 verdict for {v} does not match the rule: expected {phrase}")
    h = runs_of("B", "H")
    h_hits = sum((r["case"], "B", str(r["run"])) in hits for r in h)
    transfer = "«не перенесен»" if h_hits < 2 else "«перенесен»"
    if len(h) != 3 or f"**Перенос на кейс H - {transfer}.**" not in res:
        err.append(f"10.5 transfer to H does not match: {h_hits} hits in {len(h)} runs")
    if runs_of("AB", "K1") or "**A+B** не запускался" not in res:
        err.append("A+B record does not match")
    card = section(text, "## 11. Карточка урока", "\n## ") if "\n## " in text[text.index("## 11."):][3:] else \
        text[text.index("## 11. Карточка урока"):]
    for field in ("- Прогоны:", "- Конкретная правка:", "- До/после на той же задаче:", "- Где пробовать снова:",
                  "- Где эффект не подтвержден:"):
        if field not in card:
            err.append(f"lesson card field missing: {field}")
    return err


def selftest() -> int:
    text = PROTO.read_text(encoding="utf-8")
    assert check(text) == [], check(text)
    k1b = "| B | K1 | 1 | false | да | 227 |"
    mutants = {
        "ready flipped": (k1b, "| B | K1 | 1 | true | да | 227 |"),
        "hit flipped": (k1b, "| B | K1 | 1 | false | нет | 227 |"),
        "time changed": (k1b, "| B | K1 | 1 | false | да | 226 |"),
        "row removed": ("| A | K0 | 3 | true | - | 865 | 636 818 | 0.55 | |\n", ""),
        "marks sha changed": ("384d070a13fb42b6080e4ce1146c1cf35b21ba05a0a6b54d02e0f9236badfd4c", "0" * 64),
        "median changed": ("| Медиана времени прогона K1+K0, с | 321 | 249 | 204 |",
                           "| Медиана времени прогона K1+K0, с | 321 | 249 | 203 |"),
        "verdict A accepted": ("**A - не принят.**", "**A - принят в пилоте.**"),
        "transfer claimed": ("**Перенос на кейс H - «не перенесен».**", "**Перенос на кейс H - «перенесен».**"),
        "budget tokens": ("20 717 167 токенов", "20 717 166 токенов"),
        "card field dropped": ("- Где эффект не подтвержден:", "- Где не проверено:"),
        "H zero dropped": ("кандидатов 0", "кандидатов нет"),
        "rule quote altered": ("> 3. M3 варианта ниже baseline.", "> 3. M3 варианта не выше baseline."),
        "s13 ready flipped": ("| baseline | K1 | 1 | false | нет | 3053 |", "| baseline | K1 | 1 | true | нет | 3053 |"),
        "s13 tokens changed": ("| canary | K1 | 0 | - | - | 140 | 71 540", "| canary | K1 | 0 | - | - | 140 | 71 541"),
        "canary r1 tokens": ("| canary | K1 | 1 | - | - | 15 | 81 891 |", "| canary | K1 | 1 | - | - | 15 | 40 984 |"),
        "limit claim widened": ("Ни один прогон 2026-11-07 не уперся", "Ни один прогон не уперся"),
        "M2 of B claimed false": ("| 0 из 3 (3 блокировки подтверждены выжившей мутацией) |",
                                  "| 3 из 3 |"),
    }
    failed = 0
    for name, (a, b) in mutants.items():
        if a not in text:
            print(f"MUTANT {name}: anchor missing")
            failed += 1
            continue
        caught = bool(check(text.replace(a, b, 1)))
        print(f"MUTANT {name}: {'killed' if caught else 'SURVIVED'}")
        failed += not caught
    # record and table changed together: the transcripts and the cross-checks must still refute it
    global load
    real_load = load

    def forge_answer(r):
        r["answer"] = {"ready": True, "blockers": []}
        r["score"] = {"ready": True, "hit": False, "blockers": 0}

    def forge_score(r):
        r["score"] = dict(r["score"], ready=True)

    def forge_blocker_file(r):
        r["answer"]["blockers"][0]["file"] = "tests/other.py"

    record_mutants = [
        ("record answer and table", ("K1", "B", "1"), forge_answer,
         ("| B | K1 | 1 | false | да | 227 |", "| B | K1 | 1 | true | да | 227 |")),
        ("score.ready forged with table", ("K0", "B", "1"), forge_score,
         ("| B | K0 | 1 | false | - | 195 |", "| B | K0 | 1 | true | - | 195 |")),
        ("blocker file forged", ("K1", "B", "1"), forge_blocker_file, ("", "")),
    ]
    for label, target, mutate, (a, b) in record_mutants:
        def tampered(d, target=target, mutate=mutate):
            rs = real_load(d)
            for r in rs:
                if (r["case"], r["variant"], str(r["run"])) == target:
                    mutate(r)
            return rs
        load = tampered
        try:
            caught = bool(check(text.replace(a, b, 1) if a else text))
        except Exception:  # noqa: BLE001 - a crash also refuses the forged evidence
            caught = True
        finally:
            load = real_load
        print(f"MUTANT {label}: {'killed' if caught else 'SURVIVED'}")
        failed += not caught
    total = len(mutants) + len(record_mutants)
    print(f"selftest: {total - failed} of {total} killed")
    return 1 if failed else 0


def diff_scope(base: str) -> int:
    names = subprocess.check_output(["git", "diff", "--name-only", base, "HEAD"], text=True).split()
    extra = sorted(n for n in set(names) - SCOPE if not n.startswith(TOOLS))
    print("diff:", names)
    if extra:
        print("outside the allowed scope:", extra)
        return 1
    print("diff scope OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(selftest())
    if len(sys.argv) > 2 and sys.argv[1] == "--diff-scope":
        sys.exit(diff_scope(sys.argv[2]))
    errors = check(PROTO.read_text(encoding="utf-8"))
    for e in errors:
        print("FAIL", e)
    print("pilot check:", "PASSED" if not errors else f"FAILED ({len(errors)})")
    sys.exit(1 if errors else 0)
