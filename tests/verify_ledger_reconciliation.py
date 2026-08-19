#!/usr/bin/env python3
"""Unit-lifecycle accounting and ledger attribution (S10-LEDGER).

Root causes this test pins (all measured on the real .itd-memory/events.jsonl
at tree 4f12fda, see .itd-memory/HANDOFF-S10-LEDGER.md §1):

  1. VCR was computed over a SET OF UNIT NAMES, so repeated activations and
     repeated verifications were invisible, and four legitimately `blocked`
     lifecycles (external blockers) were counted as verification misses,
     pinning the project below VCR 1 since July.
  2. events.jsonl keys unit rows by `name` only. The id `G-001` belongs to at
     least five different units across five different ledgers, so no
     name-keyed accounting can tell them apart.
  3. itd_unit_log.py gated `verified` on "was this name EVER activated", so an
     activation closed in July unlocked a `verified` written in August.

The unit of accounting is therefore the LIFECYCLE (activated -> first terminal),
attributed to the ledger that owns it. Self-contained; synthetic fixtures in a
tmpdir plus one read-only integration check against this repository. Run:
  python3 tests/verify_ledger_reconciliation.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "_shared"))
UNIT_LOG = ROOT / "skills" / "task" / "scripts" / "itd_unit_log.py"
PY = sys.executable

PASSED, FAILED = 0, 0
SEEN_NAMES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    SEEN_NAMES.append(name)
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    # `-I` + cleared import-path env: the parent oracle runs isolated, and a
    # child inheriting PYTHONPATH could shadow the very modules under test, so
    # the suite would validate different code than it claims (reviewer
    # 2026-08-17, security).
    env = {**os.environ, "PYTHONUTF8": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONSTARTUP", None)
    return subprocess.run([PY, "-I", str(script), *args], cwd=str(cwd),
                          capture_output=True, encoding="utf-8",
                          errors="replace", env=env, timeout=120)


def after_last_event(mem: Path, hours: int = 1) -> str:
    """A stamp guaranteed to sort after every row already in the log.

    Hard-coding a "future" date would silently invert once the calendar passes
    it: the row would sort BEFORE the writer's real-time rows and become an
    idempotent re-activation instead of opening a new cycle, changing what the
    test proves without failing (reviewer 2026-08-17).
    """
    from datetime import timedelta
    import itd_unit_lifecycle as _L
    stamps = [_L._parse_at(json.loads(l).get("at"))
              for l in (mem / "events.jsonl").read_text(encoding="utf-8").splitlines()
              if l.strip()]
    latest = max(s for s in stamps if s is not None)
    return (latest + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def LEDGER_OF(mem: Path, unit: str, outcome: str) -> str:
    """Ledger of the single lifecycle of `unit` currently in `outcome`."""
    import itd_unit_lifecycle as _L
    wanted = ("open", "wip") if outcome == "open" else (outcome,)
    hits = [lc["ledger"] for lc in _L.build(mem)["lifecycles"]
            if lc["unit"] == unit and lc["outcome"] in wanted]
    return hits[0] if len(hits) == 1 else ""


def ev(name: str, decision: str, at: str, **extra) -> dict:
    e = {"id": f"evt-{name}-{at}", "at": at, "actor": "harness", "type": "unit",
         "name": name, "decision": decision, "evidence": "x"}
    e.update(extra)
    return e


def ledger(path: Path, unit_ids: list[str], created: str, updated: str) -> None:
    path.write_text(json.dumps({
        "version": "1", "goal": "fixture", "status": "active",
        "createdAt": created, "updatedAt": updated, "currentUnitId": "",
        "units": [{"id": u, "criterion": "c", "verificationCommand": "true",
                   "status": "pending"} for u in unit_ids],
    }, ensure_ascii=False), encoding="utf-8")


def write_events(mem: Path, events: list[dict]) -> None:
    (mem / "events.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
        encoding="utf-8")


def main() -> int:
    try:
        import itd_unit_lifecycle as L
    except ImportError as exc:
        check("skills/_shared/itd_unit_lifecycle.py importable", False, str(exc))
        print(f"\n{PASSED} passed, {FAILED} failed")
        return 1

    # ---------------------------------------------------------------- A. attribution
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        # The real G-001 case: one id, two ledgers, disjoint time windows.
        ledger(mem / "GOAL-axis1.json", ["G-001"],
               "2026-07-05T00:00:00Z", "2026-07-05T23:59:59Z")
        ledger(mem / "GOAL-axis2.json", ["G-001"],
               "2026-07-06T00:00:00Z", "2026-07-06T23:59:59Z")
        write_events(mem, [
            ev("G-001", "activated", "2026-07-05T10:00:00Z"),
            ev("G-001", "verified", "2026-07-05T11:00:00Z"),
            ev("G-001", "activated", "2026-07-06T10:00:00Z"),
            ev("G-001", "verified", "2026-07-06T11:00:00Z"),
            # task-level unit that belongs to no goal ledger at all
            ev("S9-RELEASE", "activated", "2026-08-16T08:00:00Z"),
            ev("S9-RELEASE", "verified", "2026-08-16T20:00:00Z"),
        ])
        r = L.build(mem)
        by_ledger = sorted(lc["ledger"] for lc in r["lifecycles"])
        check("same unit id in two ledgers yields two attributed lifecycles",
              len(r["lifecycles"]) == 3 and by_ledger.count("GOAL-axis1.json") == 1
              and by_ledger.count("GOAL-axis2.json") == 1,
              json.dumps(by_ledger))
        check("unit belonging to no goal ledger attributes to STATE, not unattributed",
              by_ledger.count(L.STATE_LEDGER) == 1 and r["unattributedEvents"] == 0,
              json.dumps(by_ledger))
        check("all lifecycles verified -> vcr 1.0",
              r["vcr"] == 1.0 and r["lifecyclesVerified"] == 3, json.dumps(r["vcr"]))

        # MUTATION: shifting one ledger window so both cover the same event
        # must make attribution ambiguous rather than silently pick one.
        ledger(mem / "GOAL-axis2.json", ["G-001"],
               "2026-07-05T00:00:00Z", "2026-07-06T23:59:59Z")
        r2 = L.build(mem)
        check("overlapping ledger windows make the row unattributed, not guessed",
              r2["unattributedEvents"] >= 2, json.dumps(r2["unattributedEvents"]))

        # An explicit ledger field on the row always wins over inference.
        write_events(mem, [
            ev("G-001", "activated", "2026-07-05T10:00:00Z", ledger="GOAL-axis1.json"),
            ev("G-001", "verified", "2026-07-05T11:00:00Z", ledger="GOAL-axis1.json"),
        ])
        # A manifest entry must NOT be able to reassign a row the machine can
        # already attribute on its own: it explains what cannot be inferred, it
        # does not override inference (reviewer 2026-08-17, high).
        ledger(mem / "GOAL-axis2.json", ["G-002"],
               "2026-07-06T00:00:00Z", "2026-07-06T23:59:59Z")
        write_events(mem, [ev("G-002", "activated", "2026-07-06T10:00:00Z"),
                           ev("G-002", "verified", "2026-07-06T11:00:00Z")])
        (mem / "LEDGER-RECONCILIATION.json").write_text(json.dumps({"entries": [
            {"unit": "G-002", "at": "2026-07-06T10:00:00Z",
             "ledger": "GOAL-axis1.json", "why": "attempted override"}]}),
            encoding="utf-8")
        rov = L.build(mem)
        check("a manifest entry cannot override a uniquely inferable row",
              all(lc["ledger"] == "GOAL-axis2.json"
                  for lc in rov["lifecycles"] if lc["unit"] == "G-002"),
              json.dumps([(lc["unit"], lc["ledger"]) for lc in rov["lifecycles"]]))
        # ...but it MUST apply where inference has no answer at all: a unit whose
        # former ledger no longer exists has no owners, and STATE-by-absence is a
        # default, not a derivation (reviewer 2026-08-17).
        write_events(mem, [ev("GONE-1", "activated", "2026-07-06T10:00:00Z"),
                           ev("GONE-1", "verified", "2026-07-06T11:00:00Z")])
        (mem / "LEDGER-RECONCILIATION.json").write_text(json.dumps({"entries": [
            {"unit": "GONE-1", "at": "2026-07-06T10:00:00Z",
             "ledger": "GOAL-axis1.json", "why": "its ledger was rewritten"},
            {"unit": "GONE-1", "at": "2026-07-06T11:00:00Z",
             "ledger": "GOAL-axis1.json", "why": "its ledger was rewritten"}]}),
            encoding="utf-8")
        rg = L.build(mem)
        check("a manifest entry beats the STATE default for an ownerless unit",
              all(lc["ledger"] == "GOAL-axis1.json"
                  for lc in rg["lifecycles"] if lc["unit"] == "GONE-1")
              and rg["lifecycles"] != [],
              json.dumps([(lc["unit"], lc["ledger"]) for lc in rg["lifecycles"]]))
        (mem / "LEDGER-RECONCILIATION.json").unlink()
        (mem / "GOAL-axis2.json").unlink()
        ledger(mem / "GOAL-axis2.json", ["G-001"],
               "2026-07-05T00:00:00Z", "2026-07-06T23:59:59Z")

        write_events(mem, [
            ev("G-001", "activated", "2026-07-05T10:00:00Z", ledger="GOAL-axis1.json"),
            ev("G-001", "verified", "2026-07-05T11:00:00Z", ledger="GOAL-axis1.json"),
        ])
        r3 = L.build(mem)
        check("explicit ledger field wins over ambiguous inference",
              r3["unattributedEvents"] == 0
              and r3["lifecycles"][0]["ledger"] == "GOAL-axis1.json",
              json.dumps(r3["unattributedEvents"]))

    # ---------------------------------------------------------------- B. lifecycles
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        write_events(mem, [
            # repeated activation with no terminal in between: ONE lifecycle
            ev("A", "activated", "2026-07-10T10:00:00Z"),
            ev("A", "activated", "2026-07-10T10:05:00Z"),
            ev("A", "verified", "2026-07-10T11:00:00Z"),
            # blocked is a legitimate terminal, not a verification miss
            ev("B", "activated", "2026-07-10T10:00:00Z"),
            ev("B", "blocked", "2026-07-10T10:30:00Z"),
            # re-activation after a terminal opens a SECOND lifecycle
            ev("C", "activated", "2026-07-10T10:00:00Z"),
            ev("C", "blocked", "2026-07-10T10:30:00Z"),
            ev("C", "activated", "2026-07-10T12:00:00Z"),
            ev("C", "verified", "2026-07-10T13:00:00Z"),
            # activated and never terminated: real drift, must stay visible
            ev("D", "activated", "2026-07-10T10:00:00Z"),
            # verified again long after its lifecycle closed: re-verification,
            # not a writer bug (real case: PE5-015, HE5-007, HDX-008)
            ev("E", "activated", "2026-07-10T10:00:00Z"),
            ev("E", "verified", "2026-07-10T11:00:00Z"),
            ev("E", "verified", "2026-08-10T09:00:00Z"),
            # verified with no activation ever: writer bug, must be flagged
            ev("F", "verified", "2026-07-10T11:00:00Z"),
            # twice, still with no activation: BOTH remain writer bugs
            ev("G", "verified", "2026-07-10T11:00:00Z"),
            ev("G", "verified", "2026-08-10T09:00:00Z"),
        ])
        r = L.build(mem)
        idx = {}
        for lc in r["lifecycles"]:
            idx.setdefault(lc["unit"], []).append(lc)
        check("repeated activation without an intervening terminal is idempotent",
              len(idx["A"]) == 1, json.dumps(len(idx.get("A", []))))
        check("re-activation after a terminal opens a second lifecycle",
              len(idx["C"]) == 2
              and [lc["outcome"] for lc in idx["C"]] == ["blocked", "verified"],
              json.dumps([lc["outcome"] for lc in idx.get("C", [])]))
        check("activated without a terminal stays an open lifecycle",
              len(idx["D"]) == 1 and idx["D"][0]["outcome"] == "open"
              and r["lifecyclesOpen"] == 1, json.dumps(r["lifecyclesOpen"]))
        check("second verified after a closed verified is a re-verification",
              len(idx["E"]) == 2 and idx["E"][1]["reverification"] is True
              and idx["E"][1]["noActivation"] is False,
              json.dumps([lc.get("reverification") for lc in idx.get("E", [])]))
        # Two verifieds with NO activation at all: the second must stay a
        # noActivation writer bug, not be laundered into a re-verification by
        # the first one (reviewer 2026-08-17, high).
        idx_g = [lc for lc in r["lifecycles"] if lc["unit"] == "G"]
        check("verified twice with no activation stays two writer bugs",
              len(idx_g) == 2 and all(lc["noActivation"] for lc in idx_g)
              and not any(lc["reverification"] for lc in idx_g),
              json.dumps([(lc["noActivation"], lc["reverification"]) for lc in idx_g]))
        check("verified with no activation at all is flagged noActivation",
              idx["F"][0]["noActivation"] is True and r["lifecyclesNoActivation"] == 3,
              json.dumps(r["lifecyclesNoActivation"]))
        # Exact accounting, not "non-null": total 10 = A + B + C*2 + D + E*2 + F
        # + G*2; blocked 2 (B, C#1) leave the denominator; verified 7 (A, C#2,
        # E#1, E#2, F, G#1, G#2); open D stays IN -> 7 / (10-2) = 0.875.
        check("blocked lifecycles leave the VCR denominator but stay counted",
              (r["lifecyclesTotal"], r["lifecyclesVerified"], r["lifecyclesBlocked"],
               r["vcr"]) == (10, 7, 2, round(7 / 8, 3)),
              f"total={r['lifecyclesTotal']} verified={r['lifecyclesVerified']} "
              f"blocked={r['lifecyclesBlocked']} vcr={r['vcr']}")
        check("open lifecycle drags VCR below 1",
              r["vcr"] < 1.0, f"vcr={r['vcr']}")

        # MUTATION: closing D must lift VCR to exactly 1.0 without touching
        # the blocked ones -- i.e. the warning clears by classification, not
        # by hiding anything.
        evs = [json.loads(l) for l in (mem / "events.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()]
        evs.append(ev("D", "abandoned", "2026-07-11T10:00:00Z"))
        write_events(mem, evs)
        r2 = L.build(mem)
        # D closed as `abandoned` -> counted as a miss and kept in the
        # denominator, so 7 / (10-2) is unchanged; blocked stay visible and the
        # drift counter clears. The remaining sub-1 ratio is D itself, stated
        # rather than hinted at.
        check("closing the open lifecycle clears the drift without hiding blocked",
              (r2["lifecyclesOpen"], r2["lifecyclesBlocked"], r2["lifecyclesVerified"],
               r2["vcr"]) == (0, 2, 7, round(7 / 8, 3)),
              f"vcr={r2['vcr']} open={r2['lifecyclesOpen']} "
              f"blocked={r2['lifecyclesBlocked']} verified={r2['lifecyclesVerified']}")

    # ---------------------------------------------------------------- C. writer
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        (mem / "STATE.json").write_text("{}", encoding="utf-8")
        cwd = Path(td)

        r = run(UNIT_LOG, "activate", "U-1", "--goal", "g", "--risk-tier", "low", cwd=cwd)
        check("activate succeeds", r.returncode == 0, r.stdout + r.stderr)
        r = run(UNIT_LOG, "verified", "U-1", "--evidence", "e", cwd=cwd)
        check("verified succeeds inside an open lifecycle", r.returncode == 0,
              r.stdout + r.stderr)

        # THE HOLE: the lifecycle is closed, so a fresh verified must be refused.
        r = run(UNIT_LOG, "verified", "U-1", "--evidence", "e2", cwd=cwd)
        check("verified is refused on a CLOSED lifecycle (stale-activation hole)",
              r.returncode != 0, r.stdout + r.stderr)

        # close: fail-closed terminal for reconciliation
        r = run(UNIT_LOG, "activate", "U-2", "--goal", "g", "--risk-tier", "low", cwd=cwd)
        r = run(UNIT_LOG, "close", "U-2", cwd=cwd)
        check("close without --note is refused (fail-closed)", r.returncode != 0,
              r.stdout + r.stderr)
        blank = run(UNIT_LOG, "close", "U-2", "--note", "   ", cwd=cwd)
        check("close with a whitespace-only --note is refused",
              blank.returncode != 0, blank.stdout + blank.stderr)
        # `activate` would be refused by the WIP gate regardless, which would
        # make this pass vacuously; `backfill-activation` has no WIP gate, so
        # only the blank-id guard can refuse it.
        blankid = run(UNIT_LOG, "backfill-activation", "   ", "--note", "n", cwd=cwd)
        check("a blank unit id is refused before any state or event mutation",
              blankid.returncode != 0, blankid.stdout + blankid.stderr)
        r = run(UNIT_LOG, "close", "U-2", "--note", "superseded by U-3",
                "--outcome", "abandoned", cwd=cwd)
        check("close with --note writes the terminal event", r.returncode == 0,
              r.stdout + r.stderr)

        # Читать лог до проверки, что писатель вообще что-то записал, значит
        # ронять оракул трейсбеком вместо красной проверки (ревьюер
        # 2026-08-17; воспроизвелось на R4c, когда activate стал требовать
        # --risk-tier и переставал создавать events.jsonl).
        check("the writer produced an event log to read",
              (mem / "events.jsonl").is_file())
        rows = [json.loads(l) for l in (mem / "events.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()] \
            if (mem / "events.jsonl").is_file() else []
        closing = [e for e in rows if e["name"] == "U-2" and e["decision"] == "abandoned"]
        check("close is attributed to harness-reconciliation, not plain harness",
              len(closing) == 1 and closing[0]["actor"] == "harness-reconciliation",
              json.dumps(closing)[:200])
        check("writer stamps the ledger field on unit events",
              all(e.get("ledger") for e in rows if e.get("type") == "unit"),
              json.dumps(rows[:2])[:300])
        res = L.build(mem)
        check("writer output has no open lifecycles and no unattributed rows",
              res["lifecyclesOpen"] == 0 and res["unattributedEvents"] == 0,
              json.dumps({k: res[k] for k in ("lifecyclesOpen", "unattributedEvents")}))

    # ---------------------------------------------- B2. malformed and hostile input
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        write_events(mem, [
            ev("A", "activated", "2026-07-10T10:00:00Z"),
            ev("A", "verified", "2026-07-10T11:00:00Z"),
            # a unit row with no usable name: without a guard it built a
            # (STATE, None) lifecycle and landed in the numerator
            {"id": "x", "at": "2026-07-10T12:00:00Z", "actor": "harness",
             "type": "unit", "decision": "verified", "evidence": "x"},
        ])
        r = L.build(mem)
        write_events(mem, [
            ev("A", "activated", "2026-07-10T10:00:00Z"),
            ev("A", "verified", "2026-07-10T11:00:00Z"),
            ev("   ", "verified", "2026-07-10T12:00:00Z"),
        ])
        rw = L.build(mem)
        check("a whitespace-only name is as unusable as an empty one",
              rw["lifecyclesTotal"] == 1 and rw["unattributedEvents"] == 1,
              json.dumps({k: rw[k] for k in ("lifecyclesTotal", "unattributedEvents")}))

        # A syntactically valid but non-object manifest must not abort build().
        # Non-string field types must be rejected before use as a dict key.
        (mem / "LEDGER-RECONCILIATION.json").write_text(json.dumps({
            # NON-EMPTY non-string: an empty list is falsy and was skipped even
            # by the old guard, so it would not have exercised the crash.
            "entries": [{"unit": ["G-001"], "at": ["2026-07-10T12:00:00Z"],
                         "ledger": "GOAL-x.json", "why": "non-string unit"}]}),
            encoding="utf-8")
        try:
            L.build(mem)
            ok = True
        except Exception:
            ok = False
        check("a manifest entry with a non-string field is skipped, not fatal", ok, "")

        # The same unhashable-key class on the EVENT side, plus ordering: a
        # malformed timestamp must not let a terminal precede its activation.
        (mem / "LEDGER-RECONCILIATION.json").write_text(json.dumps({
            "entries": [{"unit": "A", "at": "2026-07-10T10:00:00Z",
                         "ledger": "STATE", "why": "present so the map is loaded"}]}),
            encoding="utf-8")
        write_events(mem, [
            ev("A", "activated", "2026-07-10T10:00:00Z"),
            {"id": "b", "at": [], "actor": "harness", "type": "unit",
             "name": "A", "decision": "verified", "evidence": "x"},
        ])
        # The defect was REORDERING, not the row's existence: a terminal with an
        # unusable stamp used to sort as datetime.min and overtake its own
        # activation. Dropping such rows was an over-correction that silently
        # loses events from legacy logs with no `at` at all (it broke
        # verify_retro_scan). The row is kept, inherits the previous stamp and
        # stays in file order, so the terminal closes its own cycle.
        try:
            rt = L.build(mem)
            lcs = [lc for lc in rt["lifecycles"] if lc["unit"] == "A"]
            ok = (len(lcs) == 1 and lcs[0]["outcome"] == "verified"
                  and not lcs[0]["noActivation"] and rt["lifecyclesOpen"] == 0)
        except Exception:
            ok = False
            rt = {}
        check("a terminal with an unusable stamp closes its own cycle, not a new one",
              ok, json.dumps([(lc["unit"], lc["outcome"], lc["noActivation"])
                              for lc in rt.get("lifecycles", [])])[:200])
        # `attribute()` is public and reachable without build()'s timestamp
        # pre-filter, so its own key-type guard is pinned by a direct call.
        try:
            L.attribute({"type": "unit", "name": "A", "at": []}, [],
                        {("A", "x"): "GOAL-x.json"})
            direct_ok = True
        except Exception:
            direct_ok = False
        # Own variable, asserted IMMEDIATELY: a shared `ok` was clobbered by a
        # build() call inserted between this call and its check, so the
        # assertion silently stopped testing the direct call (reviewer
        # 2026-08-17) — same vacuous-pin class caught in r2 and r9.
        check("attribute() tolerates a non-string timestamp on a direct call",
              direct_ok, "")
        # Same unhashable class on the LEDGER side.
        (mem / "GOAL-broken.json").write_text(json.dumps({
            "version": "1", "goal": "x", "status": "active",
            "createdAt": "2026-07-10T00:00:00Z", "updatedAt": "2026-07-10T23:59:59Z",
            "currentUnitId": "", "units": [{"id": ["G-1"]}, {"id": "  "}]}),
            encoding="utf-8")
        try:
            L.build(mem)
            ok = True
        except Exception:
            ok = False
        check("a ledger with a non-string unit id is skipped, not fatal", ok, "")
        (mem / "GOAL-broken.json").unlink()

        (mem / "LEDGER-RECONCILIATION.json").unlink()

        for junk in ("[]", '"x"', "3"):
            (mem / "LEDGER-RECONCILIATION.json").write_text(junk, encoding="utf-8")
            try:
                L.build(mem)
                ok = True
            except Exception:
                ok = False
            check(f"a non-object reconciliation manifest ({junk}) degrades, not aborts",
                  ok, junk)
        # The junk loop leaves its last manifest on disk; drop it before the
        # name-guard scenario below.
        (mem / "LEDGER-RECONCILIATION.json").unlink()

        write_events(mem, [
            ev("A", "activated", "2026-07-10T10:00:00Z"),
            ev("A", "verified", "2026-07-10T11:00:00Z"),
            {"id": "x", "at": "2026-07-10T12:00:00Z", "actor": "harness",
             "type": "unit", "decision": "verified", "evidence": "x"},
        ])
        r = L.build(mem)
        check("a unit row without a usable name is malformed, not a lifecycle",
              r["lifecyclesTotal"] == 1 and r["unattributedEvents"] == 1
              and r["unattributedSample"][0]["reason"] == "missing-unit-name",
              json.dumps({k: r[k] for k in ("lifecyclesTotal", "unattributedEvents")}))

        # An unreadable events log must degrade, not abort both consumers.
        (mem / "events.jsonl").unlink()
        (mem / "events.jsonl").mkdir()
        try:
            r = L.build(mem)
            ok = r["lifecyclesTotal"] == 0
        except Exception as exc:  # noqa: BLE001 - the point is that it must not raise
            ok = False
            r = {"error": str(exc)}
        check("an unreadable events log degrades instead of aborting consumers",
              ok, json.dumps(r)[:200])

    # ------------------------------------------------- B3. WIP is ledger-scoped
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        ledger(mem / "GOAL-axis1.json", ["G-001"],
               "2026-07-05T00:00:00Z", "2026-07-05T23:59:59Z")
        ledger(mem / "GOAL-axis2.json", ["G-001"],
               "2026-07-06T00:00:00Z", "2026-07-06T23:59:59Z")
        write_events(mem, [
            ev("G-001", "activated", "2026-07-05T10:00:00Z", ledger="GOAL-axis1.json"),
            ev("G-001", "activated", "2026-07-06T10:00:00Z", ledger="GOAL-axis2.json"),
        ])
        (mem / "STATE.json").write_text(json.dumps({"currentUnit": {
            "id": "G-001", "status": "in_progress", "ledger": "GOAL-axis2.json"}}),
            encoding="utf-8")
        r = L.build(mem)
        # STATE describes at most ONE cycle: marking by id alone relabelled every
        # open cycle of that name as WIP and excluded them all from the
        # denominator (reviewer 2026-08-17).
        check("only the STATE-named ledger's cycle is WIP; the other stays open",
              r["lifecyclesWip"] == 1 and r["lifecyclesOpen"] == 1,
              json.dumps({k: r[k] for k in ("lifecyclesWip", "lifecyclesOpen")}))
        wip = [lc for lc in r["lifecycles"] if lc["outcome"] == "wip"]
        check("the WIP cycle is the one in the ledger STATE names",
              len(wip) == 1 and wip[0]["ledger"] == "GOAL-axis2.json",
              json.dumps([(lc["ledger"], lc["outcome"]) for lc in r["lifecycles"]]))

        # Without a recorded ledger STATE cannot tell the two apart, so marking
        # either would be a guess: none is marked.
        (mem / "STATE.json").write_text(json.dumps({"currentUnit": {
            "id": "G-001", "status": "in_progress"}}), encoding="utf-8")
        r = L.build(mem)
        check("with two candidates and no recorded ledger, none is guessed as WIP",
              r["lifecyclesWip"] == 0 and r["lifecyclesOpen"] == 2,
              json.dumps({k: r[k] for k in ("lifecyclesWip", "lifecyclesOpen")}))

    # ------------------------------------------------- C2. writer vs ambiguous id
    # Reviewer finding (2026-08-17, high/correctness): authorization looked up an
    # open lifecycle by unit name across ALL ledgers while the written event was
    # stamped with a ledger resolved separately. For an id owned by several
    # ledgers that stamped `STATE`, so a terminal could be authorized by the open
    # lifecycle of one ledger and then land under another -- leaving the real
    # lifecycle open forever and minting a no-activation terminal. That is the
    # exact drift class this unit exists to remove.
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        (mem / "STATE.json").write_text("{}", encoding="utf-8")
        cwd = Path(td)
        ledger(mem / "GOAL-axis1.json", ["G-001"],
               "2026-07-05T00:00:00Z", "2026-07-05T23:59:59Z")
        ledger(mem / "GOAL-axis2.json", ["G-001"],
               "2026-07-06T00:00:00Z", "2026-07-06T23:59:59Z")

        r = run(UNIT_LOG, "activate", "G-001", "--goal", "g", "--risk-tier", "low", cwd=cwd)
        check("activate of an id owned by several ledgers is refused without --ledger",
              r.returncode != 0, r.stdout + r.stderr)

        r = run(UNIT_LOG, "activate", "G-001", "--goal", "g", "--risk-tier", "low",
                "--ledger", "GOAL-axis1.json", cwd=cwd)
        check("activate with an explicit ledger succeeds", r.returncode == 0,
              r.stdout + r.stderr)
        rows = [json.loads(l) for l in (mem / "events.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()]
        check("the activation is stamped with the chosen ledger, not STATE",
              rows[-1].get("ledger") == "GOAL-axis1.json", json.dumps(rows[-1])[:200])

        r = run(UNIT_LOG, "verified", "G-001", "--evidence", "e", cwd=cwd)
        check("terminal resolves to the ledger that actually holds the open lifecycle",
              r.returncode == 0, r.stdout + r.stderr)
        rows = [json.loads(l) for l in (mem / "events.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()]
        check("the terminal is NOT written under STATE while a ledger lifecycle is open",
              rows[-1].get("ledger") == "GOAL-axis1.json", json.dumps(rows[-1])[:200])

        res = L.build(mem)
        opened = [lc for lc in res["lifecycles"] if lc["outcome"] == "open"]
        check("no ledger lifecycle is left open by the writer",
              not opened, json.dumps([(lc["ledger"], lc["unit"]) for lc in opened]))
        check("the writer minted no no-activation terminal",
              res["lifecyclesNoActivation"] == 0,
              json.dumps(res["lifecyclesNoActivation"]))

        # A terminal explicitly aimed at the WRONG ledger must be refused rather
        # than silently opening a second, no-activation lifecycle there.
        act = run(UNIT_LOG, "activate", "G-001", "--goal", "g2", "--risk-tier", "low",
                  "--ledger", "GOAL-axis2.json", cwd=cwd)
        # Without this the next check passes vacuously: if the axis2 activation
        # failed there is no open lifecycle anywhere and the refusal proves
        # nothing (reviewer 2026-08-17, high/correctness).
        check("the second lifecycle really opened in axis2",
              act.returncode == 0
              and LEDGER_OF(mem, "G-001", "open") == "GOAL-axis2.json",
              act.stdout + act.stderr)
        r = run(UNIT_LOG, "verified", "G-001", "--evidence", "e",
                "--ledger", "GOAL-axis1.json", cwd=cwd)
        check("terminal aimed at a ledger with no open lifecycle is refused",
              r.returncode != 0, r.stdout + r.stderr)

        # An explicit ledger that does not OWN the unit must be refused outright,
        # otherwise a caller could forge a lifecycle under an unrelated ledger
        # and close it themselves (reviewer 2026-08-17, high/security).
        ledger(mem / "GOAL-other.json", ["Z-9"],
               "2026-07-07T00:00:00Z", "2026-07-07T23:59:59Z")
        r = run(UNIT_LOG, "activate", "G-001", "--goal", "forge", "--risk-tier", "low",
                "--ledger", "GOAL-other.json", cwd=cwd)
        check("explicit ledger that does not own the unit is refused",
              r.returncode != 0, r.stdout + r.stderr)
        r = run(UNIT_LOG, "activate", "G-001", "--goal", "forge", "--risk-tier", "low",
                "--ledger", L.STATE_LEDGER, cwd=cwd)
        check("STATE is refused for an id that has ledger owners",
              r.returncode != 0, r.stdout + r.stderr)

        # backfill must be scoped to the resolved ledger: an activation under a
        # different ledger may not suppress it (reviewer, medium/error-handling).
        # A forged/corrupt append-only row carrying an explicit `ledger` that does
        # NOT own the unit opens a lifecycle there; implicit resolution must not
        # then adopt that unowned ledger, or history would bypass the ownership
        # check of the explicit branch (reviewer 2026-08-17, high/security).
        # STATE.currentUnit holds the axis2 WIP. Closing a DIFFERENT ledger's
        # cycle of the same id must not flip it to verified (reviewer 2026-08-17).
        st = json.loads((mem / "STATE.json").read_text(encoding="utf-8"))
        check("STATE records the ledger of the WIP cycle",
              (st.get("currentUnit") or {}).get("ledger") == "GOAL-axis2.json",
              json.dumps(st.get("currentUnit")))
        # Re-open an axis1 cycle straight in the log (axis1 is an OWNER, so this
        # is legitimate history, unlike the forged unowned row further below).
        with (mem / "events.jsonl").open("a", encoding="utf-8") as fh:
            # Derived from the log itself, never a hard-coded "future" date.
            fh.write(json.dumps(ev("G-001", "activated", after_last_event(mem),
                                   ledger="GOAL-axis1.json"), ensure_ascii=False) + "\n")
        other = run(UNIT_LOG, "verified", "G-001", "--evidence", "e",
                    "--ledger", "GOAL-axis1.json", cwd=cwd)
        st2 = json.loads((mem / "STATE.json").read_text(encoding="utf-8"))
        check("closing another ledger's cycle leaves the STATE WIP untouched",
              other.returncode == 0
              and (st2.get("currentUnit") or {}).get("status") == "in_progress"
              and (st2.get("currentUnit") or {}).get("ledger") == "GOAL-axis2.json",
              other.stdout + other.stderr + " | " + json.dumps(st2.get("currentUnit")))

        # A LEGACY STATE entry (no `ledger`) must not describe a colliding id's
        # cycles wholesale, or closing ledger B would again complete ledger A's
        # WIP — the r6 hole, narrower (reviewer 2026-08-17, high).
        st_legacy = json.loads((mem / "STATE.json").read_text(encoding="utf-8"))
        st_legacy["currentUnit"].pop("ledger", None)
        (mem / "STATE.json").write_text(json.dumps(st_legacy), encoding="utf-8")
        with (mem / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev("G-001", "activated", after_last_event(mem),
                                   ledger="GOAL-axis1.json"), ensure_ascii=False) + "\n")
        leg = run(UNIT_LOG, "verified", "G-001", "--evidence", "e",
                  "--ledger", "GOAL-axis1.json", cwd=cwd)
        st_after = json.loads((mem / "STATE.json").read_text(encoding="utf-8"))
        check("a legacy STATE without ledger does not describe a colliding id",
              leg.returncode == 0
              and (st_after.get("currentUnit") or {}).get("status") == "in_progress",
              leg.stdout + leg.stderr + " | " + json.dumps(st_after.get("currentUnit")))
        st_legacy["currentUnit"]["ledger"] = "GOAL-axis2.json"
        (mem / "STATE.json").write_text(json.dumps(st_legacy), encoding="utf-8")

        # `state_describes` is the only reader of STATE.currentUnit.ledger. A
        # falsy NON-string there (`[]`, `{}`, `0`, `false`) is a malformed
        # record, not a legacy one: `or ""` folded it into the legacy branch,
        # which for a uniquely-owned id answers True and lets a corrupt STATE
        # describe any cycle of that name (reviewer 2026-08-17, medium — the
        # same external-input type class as the timestamp and ledger-id
        # guards). Z-9 is owned by GOAL-other.json alone in this tmpdir, so the
        # legacy branch WOULD say True — that is what makes the pin discriminate.
        import importlib.util
        spec = importlib.util.spec_from_file_location("itd_unit_log_under_test", UNIT_LOG)
        UL = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(UL)
        legacy_ok = UL.state_describes(mem, {"id": "Z-9"}, "Z-9", "GOAL-other.json")
        check("state_describes: a legacy record without ledger describes a uniquely-owned id",
              legacy_ok is True, repr(legacy_ok))
        exact_ok = UL.state_describes(mem, {"id": "Z-9", "ledger": "GOAL-other.json"},
                                      "Z-9", "GOAL-other.json")
        check("state_describes: a string ledger is matched exactly",
              exact_ok is True, repr(exact_ok))
        malformed = {v: UL.state_describes(mem, {"id": "Z-9", "ledger": json.loads(v)},
                                           "Z-9", "GOAL-other.json")
                     for v in ("[]", "{}", "0", "false")}
        check("state_describes: a falsy non-string ledger is malformed, not legacy",
              all(res is False for res in malformed.values()), json.dumps(malformed))
        typed = UL.state_describes(mem, {"id": "Z-9", "ledger": ["GOAL-other.json"]},
                                   "Z-9", "GOAL-other.json")
        check("state_describes: a truthy non-string ledger never matches",
              typed is False, repr(typed))

        # The axis1 row above sorts after every "now" row the writer appends, so
        # its cycle would stay open and give implicit resolution a valid owned
        # candidate. Close it in the log at an even later stamp.
        with (mem / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev("G-001", "verified", after_last_event(mem),
                                   ledger="GOAL-axis1.json"), ensure_ascii=False) + "\n")

        # Close the legitimate axis2 cycle first, so the forged one below is the
        # ONLY open cycle and implicit resolution has nothing valid to pick.
        closed = run(UNIT_LOG, "verified", "G-001", "--evidence", "e",
                     "--ledger", "GOAL-axis2.json", cwd=cwd)
        check("the legitimate axis2 cycle closes normally",
              closed.returncode == 0, closed.stdout + closed.stderr)
        with (mem / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev("G-001", "activated", "2026-07-09T10:00:00Z",
                                   ledger="GOAL-forged.json"), ensure_ascii=False) + "\n")
        r = run(UNIT_LOG, "verified", "G-001", "--evidence", "e", cwd=cwd)
        combined = r.stdout + r.stderr
        check("an open cycle in an UNOWNED ledger never resolves implicitly",
              r.returncode != 0 and "GOAL-forged.json" not in combined.split("игнорируются")[0],
              combined)
        rows_after = [json.loads(l) for l in (mem / "events.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()]
        check("no terminal was appended under the unowned ledger",
              not [e for e in rows_after if e.get("ledger") == "GOAL-forged.json"
                   and e.get("decision") != "activated"],
              json.dumps([e.get("ledger") for e in rows_after[-3:]]))

        ledger(mem / "GOAL-axis3.json", ["G-001"],
               "2026-07-08T00:00:00Z", "2026-07-08T23:59:59Z")
        r = run(UNIT_LOG, "backfill-activation", "G-001", "--note", "n",
                "--ledger", "GOAL-axis3.json", cwd=cwd)
        check("backfill is not blocked by an activation in another ledger",
              r.returncode == 0, r.stdout + r.stderr)
        r = run(UNIT_LOG, "backfill-activation", "G-001", "--note", "n",
                "--ledger", "GOAL-axis3.json", cwd=cwd)
        check("backfill is refused once that ledger already has an activation",
              r.returncode != 0, r.stdout + r.stderr)

    # --------------------------------------- C3. atomicity ordering (structural)
    # An append failure after STATE was written leaves STATE claiming a state the
    # accounting cannot see. Exercising a real I/O failure per branch is heavy;
    # the invariant is an ORDER, so it is pinned structurally over the source —
    # and over EVERY branch, because fixing two of three is exactly how this
    # class kept coming back (reviewer 2026-08-17).
    src = UNIT_LOG.read_text(encoding="utf-8")
    for branch, anchor in (("activate", 'if a.command == "activate":'),
                           ("verified", 'if a.command == "verified":'),
                           ("close", 'if a.command == "close":'),
                           ("backfill", "# backfill-activation")):
        seg = src[src.index(anchor):]
        seg = seg[:seg.index("return 0") + 8]
        ae, ss = seg.find("append_event"), seg.find("save_state")
        check(f"{branch}: the event is appended before STATE is persisted",
              ae >= 0 and (ss < 0 or ae < ss), f"append_event@{ae} save_state@{ss}")

    # ------------------------------------------------- D. frozen real-history fixture
    # The live-repo section below is conditional by nature (.itd-memory/events.jsonl
    # is gitignored, so a fresh clone has none). Making the whole oracle skip with
    # it let the advertised checks pass without ever validating real history
    # (reviewer 2026-08-17, medium/repository-hygiene). This frozen fixture carries
    # the same shape and is always checked.
    fixture = ROOT / "tests" / "fixtures" / "ledger-reconciliation"
    check("frozen real-history fixture exists", fixture.is_dir(), str(fixture))
    if fixture.is_dir():
        r = L.build(fixture)
        check("fixture: every unit event is attributable to exactly one ledger",
              r["unattributedEvents"] == 0,
              json.dumps(r["unattributedSample"][:3], ensure_ascii=False))
        check("fixture: no lifecycle is left open",
              r["lifecyclesOpen"] == 0,
              json.dumps([lc["unit"] for lc in r["lifecycles"]
                          if lc["outcome"] == "open"]))
        check("fixture: the colliding id yields one lifecycle per owning ledger",
              len({lc["ledger"] for lc in r["lifecycles"]
                   if lc["unit"] == "G-001"}) == 2,
              json.dumps([lc["ledger"] for lc in r["lifecycles"]
                          if lc["unit"] == "G-001"]))
        # Two: PE5-008 (external blocker) and the reconciled historical row
        # whose ledger no longer exists.
        check("fixture: blocked lifecycles are reported and left out of the ratio",
              r["lifecyclesBlocked"] == 2 and r["vcr"] == 1.0,
              f"vcr={r['vcr']} blocked={r['lifecyclesBlocked']} "
              f"verified={r['lifecyclesVerified']} total={r['lifecyclesTotal']}")

    # ---------------------------------------------------------------- E. this repo
    real = ROOT / ".itd-memory"
    if (real / "events.jsonl").exists():
        r = L.build(real)
        check("repo: every unit event is attributable to exactly one ledger",
              r["unattributedEvents"] == 0,
              f"unattributed={r['unattributedEvents']} "
              f"sample={json.dumps(r['unattributedSample'][:3], ensure_ascii=False)}")
        check("repo: no lifecycle is left open",
              r["lifecyclesOpen"] == 0,
              json.dumps([lc["unit"] for lc in r["lifecycles"]
                          if lc["outcome"] == "open"]))
        check("repo: blocked lifecycles are reported, not counted as misses",
              r["lifecyclesBlocked"] >= 1 and r["vcr"] == 1.0,
              f"vcr={r['vcr']} blocked={r['lifecyclesBlocked']} "
              f"verified={r['lifecyclesVerified']} total={r['lifecyclesTotal']}")

    # ------------------------------------- G. explained vs anomalous (R4e)
    # A `verified` row with no activation is the writer anomaly that started
    # this whole ledger work. But one live row is NOT a writer defect: the
    # bulk-housekeeping line of 2026-08-10 marks G-001 verified in three axis
    # ledgers at once, belongs to none of them, and is documented in
    # LEDGER-RECONCILIATION.json. Counting it as an anomaly made the retro fact
    # cry wolf forever, so `unexplained` is the honest anomaly counter and the
    # explained row stays visible in the raw count.
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / ".itd-memory"
        mem.mkdir()
        write_events(mem, [ev("H-1", "verified", "2026-08-10T09:22:19Z")])
        raw = L.build(mem)
        check("an unexplained verified row without activation is an anomaly",
              raw["lifecyclesNoActivation"] == 1
              and raw["lifecyclesNoActivationUnexplained"] == 1,
              json.dumps({k: raw[k] for k in
                          ("lifecyclesNoActivation",
                           "lifecyclesNoActivationUnexplained")}))
        check("the anomaly is named, not just counted",
              [(lc["unit"], lc["endedAt"])
               for lc in L.unexplained_no_activation(mem)]
              == [("H-1", "2026-08-10T09:22:19Z")],
              json.dumps(L.unexplained_no_activation(mem)))
        (mem / "LEDGER-RECONCILIATION.json").write_text(json.dumps({"entries": [
            {"unit": "H-1", "at": "2026-08-10T09:22:19Z", "ledger": "RECONCILIATION",
             "why": "bulk housekeeping row belonging to no single ledger"}]}),
            encoding="utf-8")
        explained = L.build(mem)
        check("an explained row stays visible but stops being an anomaly",
              explained["lifecyclesNoActivation"] == 1
              and explained["lifecyclesNoActivationUnexplained"] == 0
              and L.unexplained_no_activation(mem) == [],
              json.dumps({k: explained[k] for k in
                          ("lifecyclesNoActivation",
                           "lifecyclesNoActivationUnexplained")}))
        # Fail-closed both ways: an entry without `why` explains nothing, and an
        # entry for a different row does not launder this one.
        for label, entry in (
            ("an entry without why explains nothing",
             {"unit": "H-1", "at": "2026-08-10T09:22:19Z",
              "ledger": "RECONCILIATION", "why": "  "}),
            ("an entry for another row does not explain this one",
             {"unit": "H-1", "at": "2026-08-10T09:22:20Z",
              "ledger": "RECONCILIATION", "why": "off-by-one second"}),
        ):
            (mem / "LEDGER-RECONCILIATION.json").write_text(
                json.dumps({"entries": [entry]}), encoding="utf-8")
            check(label, L.build(mem)["lifecyclesNoActivationUnexplained"] == 1)
        # Over-block canary: a properly activated verified cycle is never an
        # anomaly, explained or not.
        write_events(mem, [ev("H-2", "activated", "2026-08-10T10:00:00Z"),
                           ev("H-2", "verified", "2026-08-10T10:30:00Z")])
        (mem / "LEDGER-RECONCILIATION.json").unlink()
        healthy = L.build(mem)
        check("a properly activated cycle is never flagged as an anomaly",
              healthy["lifecyclesVerified"] == 1
              and healthy["lifecyclesNoActivationUnexplained"] == 0,
              json.dumps({k: healthy[k] for k in
                          ("lifecyclesVerified",
                           "lifecyclesNoActivationUnexplained")}))

    # The repository's own ledger, when its (gitignored) event log is present:
    # every verified-without-activation row must be explained. In an isolated
    # tracked-only tree there is no event log at all, and the check reports that
    # honestly instead of passing by silence.
    live = ROOT / ".itd-memory"
    if (live / "events.jsonl").is_file():
        unexplained = L.unexplained_no_activation(live)
        check("this repository has no unexplained verified-without-activation row",
              unexplained == [],
              json.dumps(unexplained, ensure_ascii=False))
    else:
        check("repository event log is absent (isolated tree): live row check skipped",
              True)

    # ------------------------------------------------------- F. oracle hygiene
    # A duplicated scenario block once shipped inside this file (r8/r10 merges):
    # two identical `a ledger with a non-string unit id` checks and a redundant
    # unlink (reviewer 2026-08-17). Duplicates inflate the advertised count
    # without adding a guarantee, so every check name must be unique.
    dupes = sorted({n for n in SEEN_NAMES if SEEN_NAMES.count(n) > 1})
    check("oracle hygiene: every check name is unique (no duplicated blocks)",
          not dupes, json.dumps(dupes))

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
