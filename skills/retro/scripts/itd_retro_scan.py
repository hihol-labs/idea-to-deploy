#!/usr/bin/env python3
"""Retro telemetry scanner — the harness-side fact collector for /retro (v1.46.0).

The self-improvement loop is split three ways, on purpose:
  FACTS    — this script (deterministic aggregation, zero judgment);
  PROPOSALS — the model (/retro Step 2 turns facts into ranked release
              candidates WITH evidence quoted from this output);
  MERGE    — the human (nothing lands without the ordinary PR pipeline).
The script never edits anything and never decides anything — the same
«харнес считает, агент интерпретирует, человек мержит» boundary as
itd_goal_verify.py (v1.45.0), applied to methodology improvement itself.

Sources scanned (all optional — missing ones are reported as absent, never
fatal):
  <workspace>/*/.itd-memory/events.jsonl  — unit events: activated / verified /
      regressed / verification_failed / blocked → per-project VCR + global VCR
  <workspace>/*/.itd-memory/GOAL.json     — goal status, N/M verified,
      backpressure, blocked units with reasons
  <workspace>/*/.itd-memory/STATE.json    — pending gates, blockers
  <tmp>/claude-skill-ledger-*.jsonl       — SKILL_BYPASS records (skill, reason)
  <tmp>/claude-cost-*.json                — cost-tracker session ledgers

Ships inside the skill (skills/retro/scripts/) so both sync-to-active and the
plugin install deliver it. Stdlib only.

Usage:
  itd_retro_scan.py [WORKSPACE ...] [--tmp-dir DIR] [--json]

WORKSPACE defaults to the current directory. --tmp-dir overrides the ledger
location (default: tempfile.gettempdir(); tests point it at a fixture dir).
Exit codes: 0 report printed (even if all sources are empty), 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

CLIP = 80
# USD per 1M tokens — MUST stay in sync with COST_PER_1M_TOKENS in
# hooks/cost-tracker.sh (the ledger persists total_tokens only; USD is derived
# at read time there and here). Same env override as the hook.
COST_PER_1M_USD_DEFAULT = 30.0


def clip(s: str, n: int = CLIP) -> str:
    s = (s or "").replace("\n", " ").replace("|", "\\|").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    except Exception:
        pass
    return out


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def scan_project(mem: Path) -> dict:
    """Aggregate one project's .itd-memory dir into plain counts."""
    p: dict = {"project": mem.parent.name}

    events = [e for e in read_jsonl(mem / "events.jsonl") if e.get("type") == "unit"]
    activated = {e.get("name") for e in events if e.get("decision") == "activated"}
    verified = {e.get("name") for e in events if e.get("decision") == "verified"}
    p["unitsActivated"] = len(activated)
    p["unitsVerified"] = len(verified)
    p["vcr"] = round(len(verified) / len(activated), 3) if activated else None
    p["regressions"] = sum(1 for e in events if e.get("decision") == "regressed")
    p["failedVerifications"] = sum(
        1 for e in events if e.get("decision") == "verification_failed")

    goal = read_json(mem / "GOAL.json")
    if goal:
        units = [u for u in (goal.get("units") or []) if isinstance(u, dict)]
        p["goal"] = clip(goal.get("goal") or "")
        p["goalStatus"] = goal.get("status") or ""
        p["goalVerified"] = sum(1 for u in units if u.get("status") == "verified")
        p["goalTotal"] = len(units)
        p["goalBackpressure"] = sum(
            1 for u in units if u.get("status") in ("pending", "in_progress", "blocked"))
        p["goalBlocked"] = [
            {"id": u.get("id"), "reason": clip(u.get("blockedReason") or "")}
            for u in units if u.get("status") == "blocked"]

    state = read_json(mem / "STATE.json")
    if state:
        gates = state.get("gateResults") or {}
        p["pendingGates"] = sorted(
            k for k, v in gates.items() if v not in ("", "n/a", "passed"))[:10]
        p["blockers"] = [clip(str(b)) for b in (state.get("blockers") or [])[:5]]

    return p


def scan_ledgers(tmp_dir: Path) -> dict:
    """Bypass + cost ledgers from the hook tempdir. Counts only.

    Record shapes mirror the ACTUAL producers (review finding v1.46.0 — the
    scanner was first built against an assumed shape and read zero from real
    ledgers):
      check-tool-skill.sh log_bypass() writes {"ts", "tool", "reason"} — there
      is no "skill" key, so grouping is honestly BY TOOL;
      cost-tracker.sh persists {"total_tokens", ...} — USD is never stored,
      it is derived here with the hook's own rate (same env override).
    """
    bypasses: dict[str, int] = {}
    bypass_reasons: list[str] = []
    bypass_sessions = 0  # one ledger file == one session that logged >=1 bypass
    # v1.66.0 (retro-2026-07-08 P1): the hook now flags "ceremonial" bypasses —
    # markers that arrived while the gate was open anyway (fresh grace window /
    # read-only command). Real escapes and habit annotations are different
    # friction signals; count them separately so the metric stays honest.
    bypass_ceremonial = 0
    for path in sorted(tmp_dir.glob("claude-skill-ledger-*.jsonl")):
        recs = read_jsonl(path)
        if not recs:
            continue
        bypass_sessions += 1
        for rec in recs:
            tool = str(rec.get("tool") or rec.get("skill") or "unknown")
            bypasses[tool] = bypasses.get(tool, 0) + 1
            if rec.get("ceremonial"):
                bypass_ceremonial += 1
            reason = str(rec.get("reason") or "").strip()
            if reason:
                bypass_reasons.append(clip(f"{tool}: {reason}"))

    import os
    try:
        per_1m = float(os.environ.get("ITD_COST_PER_1M_USD",
                                      COST_PER_1M_USD_DEFAULT))
    except Exception:
        per_1m = COST_PER_1M_USD_DEFAULT
    cost_tokens = 0
    cost_usd = 0.0
    cost_sessions = 0
    for path in sorted(tmp_dir.glob("claude-cost-*.json")):
        data = read_json(path)
        if not data:
            continue
        cost_sessions += 1
        try:
            tokens = int(data.get("total_tokens") or 0)
        except (TypeError, ValueError):
            tokens = 0
        cost_tokens += tokens
        if tokens:
            cost_usd += (tokens / 1_000_000) * per_1m
        else:
            # forward-compat: accept a pre-computed USD field if a future
            # ledger version ever persists one
            for key in ("estimatedUsd", "estimated_usd", "usd", "totalUsd"):
                try:
                    cost_usd += float(data.get(key))
                    break
                except (TypeError, ValueError):
                    continue

    bypass_total = sum(bypasses.values())
    return {
        "bypassTotal": bypass_total,
        "bypassCeremonialTotal": bypass_ceremonial,
        "bypassByTool": dict(sorted(bypasses.items(), key=lambda kv: -kv[1])[:5]),
        "bypassReasonsTail": bypass_reasons[-10:],
        # bypass/session is the friction metric that must trend DOWN release to
        # release (ceremony bypasses are the tax the read-only allowlist + grace
        # window exist to cut). Normalising by session makes it comparable
        # across retros of different length.
        "bypassSessionCount": bypass_sessions,
        "bypassPerSession": round(bypass_total / bypass_sessions, 2) if bypass_sessions else 0.0,
        "costSessions": cost_sessions,
        "costTokensTotal": cost_tokens,
        "costUsdEstimate": round(cost_usd, 2),
    }


def build(workspaces: list[Path], tmp_dir: Path) -> dict:
    projects: list[dict] = []
    seen: set[str] = set()  # resolved .itd-memory paths — overlapping
    for ws in workspaces:  # workspace args must not double-count a project
        candidates = []
        if (ws / ".itd-memory").is_dir():
            candidates.append(ws / ".itd-memory")
        candidates.extend(sorted(ws.glob("*/.itd-memory")))
        for mem in candidates:
            key = str(mem.resolve())
            if key in seen:
                continue
            seen.add(key)
            projects.append(scan_project(mem))

    activated = sum(p["unitsActivated"] for p in projects)
    verified = sum(p["unitsVerified"] for p in projects)
    report = {
        "workspaces": [str(w) for w in workspaces],
        "projectsScanned": len(projects),
        "unitsActivated": activated,
        "unitsVerified": verified,
        "vcrGlobal": round(verified / activated, 3) if activated else None,
        "regressions": sum(p["regressions"] for p in projects),
        "failedVerifications": sum(p["failedVerifications"] for p in projects),
        "projectsBelowVcr1": [
            p["project"] for p in projects
            if p["vcr"] is not None and p["vcr"] < 1.0],
        "goalsActive": [
            {"project": p["project"], "goal": p.get("goal"),
             "verified": p.get("goalVerified"), "total": p.get("goalTotal"),
             "backpressure": p.get("goalBackpressure"),
             "blocked": p.get("goalBlocked")}
            for p in projects if p.get("goalStatus") == "active"],
        "projects": projects,
    }
    report.update(scan_ledgers(tmp_dir))
    return report


def render_markdown(r: dict) -> str:
    out: list[str] = []
    out.append("## Retro scan — факты из телеметрии (без интерпретации)")
    out.append("")
    out.append(f"Проектов с `.itd-memory`: **{r['projectsScanned']}** "
               f"(workspace: {', '.join(r['workspaces'])})")
    vcr = r["vcrGlobal"]
    out.append(f"**VCR глобально:** {vcr if vcr is not None else 'n/a (unit-событий нет)'} "
               f"({r['unitsVerified']}/{r['unitsActivated']} юнитов), "
               f"регрессий: {r['regressions']}, "
               f"проваленных верификаций: {r['failedVerifications']}")
    if r["projectsBelowVcr1"]:
        out.append(f"**Проекты с VCR<1.0:** {', '.join(r['projectsBelowVcr1'])}")
    out.append("")
    if r["goalsActive"]:
        out.append("**Активные цели (/goal):**")
        for g in r["goalsActive"]:
            line = (f"- {g['project']}: {g['goal']} — "
                    f"{g['verified']}/{g['total']} verified, "
                    f"давление {g['backpressure']}")
            if g["blocked"]:
                line += "; blocked: " + "; ".join(
                    f"{b['id']} ({b['reason']})" for b in g["blocked"])
            out.append(line)
        out.append("")
    out.append(f"**SKILL_BYPASS:** всего {r['bypassTotal']}"
               + (f" за {r['bypassSessionCount']} сессий "
                  f"(**{r['bypassPerSession']}/сессия** — метрика трения, "
                  f"должна падать от релиза к релизу)"
                  if r.get("bypassSessionCount") else "")
               + (f", по инструментам: " + ", ".join(
                   f"{k}×{v}" for k, v in r["bypassByTool"].items())
                  if r["bypassByTool"] else "")
               + (f"; из них ceremonial (гейт уже был открыт — привычная "
                  f"аннотация, не реальный обход): {r['bypassCeremonialTotal']}"
                  if r.get("bypassCeremonialTotal") else ""))
    if r["bypassReasonsTail"]:
        out.append("<details><summary>Последние причины bypass</summary>")
        out.append("")
        for reason in r["bypassReasonsTail"]:
            out.append(f"- {reason}")
        out.append("")
        out.append("</details>")
    out.append(f"**Cost-леджеры:** {r['costSessions']} сессий"
               + (f", {r['costTokensTotal']} токенов" if r["costTokensTotal"] else "")
               + (f", ~${r['costUsdEstimate']}" if r["costUsdEstimate"] else ""))
    out.append("")
    per = [p for p in r["projects"]
           if p["unitsActivated"] or p.get("goalTotal") or p.get("pendingGates")]
    if per:
        out.append("| Проект | Юниты (verified/activated) | VCR | Регрессии | Незакрытые гейты |")
        out.append("|---|---|---|---|---|")
        for p in per:
            gates = ", ".join(p.get("pendingGates") or []) or "—"
            out.append(f"| {p['project']} | {p['unitsVerified']}/{p['unitsActivated']} "
                       f"| {p['vcr'] if p['vcr'] is not None else '—'} "
                       f"| {p['regressions']} | {clip(gates, 60)} |")
    return "\n".join(out)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(
        description="Deterministic telemetry aggregation for the /retro cycle")
    p.add_argument("workspaces", nargs="*", default=None,
                   help="workspace roots to scan (default: current dir)")
    p.add_argument("--tmp-dir", type=Path, default=None,
                   help="ledger dir override (default: system tempdir)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    workspaces = [Path(w) for w in (args.workspaces or ["."])]
    for ws in workspaces:
        if not ws.is_dir():
            print(f"ERROR: workspace not found: {ws}")
            return 2
    tmp_dir = args.tmp_dir or Path(tempfile.gettempdir())

    report = build(workspaces, tmp_dir)
    if args.json:
        slim = {k: v for k, v in report.items() if k != "projects"}
        print(json.dumps(slim, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
