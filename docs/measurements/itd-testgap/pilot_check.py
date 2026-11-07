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


def check(text: str) -> list[str]:
    err = []
    runs, s13 = load(EV / "runs"), load(EV / "s13")
    key, hits = blind_hits()
    rows = table_rows(text)
    if any(len(k) == 4 for k in rows):
        err.append("duplicate row in 10.2")
    if len(rows) != len(runs) + len(s13):
        err.append(f"10.2 has {len(rows)} rows, evidence {len(runs) + len(s13)} runs")
    for r in s13:
        cells = rows.get((r["variant"], r["case"], str(r["run"])))
        if not cells or cells[5] != str(round(r["wallSeconds"])):
            err.append(f"s13 row {r['variant']} {r['case']} {r['run']} missing or time differs")
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
    # budget
    allr = runs + s13
    wall = round(sum(r.get("wallSeconds") or 0 for r in allr))
    tok = sum(r.get("tokensTotal") or sum(r.get(x) or 0 for x in ("inputTokens", "outputTokens", "cacheReadTokens",
                                                                    "cacheCreationTokens")) for r in allr)
    usd = sum(r.get("costUsd") or 0 for r in runs) + 1.44  # s13 canary price recorded in 10.1 (transcript has none)
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
        r = by_name[(c["case"], c["variant"], str(c["run"]))]
        if r["answer"]["blockers"][c["blocker"]]["problem"] != c["problem"]:
            err.append(f"blind key {lid} does not match its run record")
    sys.argv = ["blind.py"]
    import blind
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
                paths = [b for b in bad if "path outside" in b]
                net = [b for b in bad if "network command" in b]
                if len(paths) < 4 or len(net) < 2:
                    err.append("canary r3: the audit does not name all six attempts")
            continue
        rest = pr.apply_a4({"answer": r["answer"], "isolationViolations": bad})["isolationViolations"]
        if rest and not (rest == ["Bash: path outside the allowed places: ../"] and r.get("manualAdjudication")):
            err.append(f"{name}: re-audit finds {rest[:2]}")
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
        entries = adj.get(f"{r['case']}-{r['variant']}-r{r['run']}") or []
        blockers = r["answer"]["blockers"]
        return any(0 <= e["blocker"] < len(blockers) and e["mutant"] in survived for e in entries)
    stats = {}
    for v in ("baseline", "A", "B"):
        k1, k0 = runs_of(v, "K1"), runs_of(v, "K0")
        m1 = sum((r["case"], v, str(r["run"])) in hits for r in k1)
        blocks = [r for r in k0 if r["score"]["ready"] is False]
        confirmed = [r for r in blocks if confirmed_block(r)]
        m2 = len(blocks) - len(confirmed)
        m3 = sum(r["score"]["ready"] is True for r in k1)
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
        "budget tokens": ("20 645 627 токенов", "20 645 626 токенов"),
        "card field dropped": ("- Где эффект не подтвержден:", "- Где не проверено:"),
        "H zero dropped": ("кандидатов 0", "кандидатов нет"),
        "rule quote altered": ("> 3. M3 варианта ниже baseline.", "> 3. M3 варианта не выше baseline."),
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
    print(f"selftest: {len(mutants) - failed} of {len(mutants)} killed")
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
