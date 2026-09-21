#!/usr/bin/env python3
"""The route metric tells three kinds of `verified` apart (ROUTE-REPAIR-3).

Root cause this test pins (measured on the real .itd-memory/events.jsonl at
tree dba30dd): `lifecyclesVerified` / `unitsVerified` counted every `verified`
lifecycle as one and the same thing. Of the 20 verified rows in the live log
17 were harness transitions with no checker receipt and 3 were written by the
owner's hand (`route: owner` twice, `route: owner-route` once, and twice with
the literal string `none` standing in for a receipt) — and the metric could not
tell any of them from a full independent verification.

Every verified lifecycle therefore belongs to EXACTLY ONE named route class:

  verifiedOwnerRoute   the transition was recorded by the owner — a route label
                       naming the owner, or any writer that is not the harness.
                       Wins over a bound receipt: a path typed by hand next to
                       a hand-written transition was validated by nobody.
  verifiedIndependent  a harness transition whose event binds a checker /
                       adjudication receipt.
  verifiedMachineOnly  a harness transition with no checker receipt.

Spelling is normalised, not trusted: `owner`, `owner-route`, `Owner_Route`
are one label, and `none` / `null` in `checkerReceipt` is the absence of a
receipt, not a receipt. `vcr` keeps its value and its definition.

Each class is proved by MUTATION, inside this oracle: the module is copied to a
tmpdir, one decision is broken, and the same fixture must come out different.
A mutation whose anchor is no longer in the source fails instead of passing
vacuously. Self-contained; one read-only integration check against this
repository. Run:
  python3 tests/verify_route_metric.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
MODULE = SHARED / "itd_unit_lifecycle.py"
METRICS = ROOT / "scripts" / "itd_metrics.py"
PY = sys.executable
sys.path.insert(0, str(SHARED))

CLASSES = ("verifiedIndependent", "verifiedMachineOnly", "verifiedOwnerRoute")

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


def clean_env() -> dict:
    # A child inheriting PYTHONPATH could shadow the module under test, and the
    # mutation probes below depend on importing exactly the copy they name.
    env = {**os.environ, "PYTHONUTF8": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONSTARTUP", None)
    return env


def ev(name: str, decision: str, at: str, **extra) -> dict:
    e = {"id": f"evt-{name}-{decision}-{at}", "at": at, "actor": "harness",
         "type": "unit", "name": name, "decision": decision, "evidence": "x"}
    e.update(extra)
    return e


# unit id -> (extra fields of its `verified` row, expected class)
VERIFIED_ROWS = {
    "U-IND": ({"checkerReceipt": ".itd-memory/verification-loop/U-IND/adjudication-a1.json"},
              "verifiedIndependent"),
    "U-MACH": ({}, "verifiedMachineOnly"),
    "U-MACH-RECEIPT": ({"machineReceipt": ".itd-memory/verification-loop/U/machine-a1.json"},
                       "verifiedMachineOnly"),
    "U-NONE": ({"checkerReceipt": "none"}, "verifiedMachineOnly"),
    "U-NONE-CASE": ({"checkerReceipt": " None "}, "verifiedMachineOnly"),
    "U-NULL": ({"checkerReceipt": "null"}, "verifiedMachineOnly"),
    "U-EMPTY": ({"checkerReceipt": ""}, "verifiedMachineOnly"),
    # An unknown shape is not a receipt: counting it would overstate independence.
    "U-LIST": ({"checkerReceipt": ["a.json"]}, "verifiedMachineOnly"),
    "U-OWN": ({"actor": "human-owner", "route": "owner", "machineReceipt": "none"},
              "verifiedOwnerRoute"),
    "U-OWN-VARIANT": ({"actor": "human-owner", "route": "owner-route"},
                      "verifiedOwnerRoute"),
    # The label alone decides: a harness-written row that names the owner route.
    "U-LABEL-ROUTE": ({"route": "owner-route"}, "verifiedOwnerRoute"),
    "U-LABEL-SPELL": ({"route": " Owner_Route "}, "verifiedOwnerRoute"),
    # The writer alone decides: no label at all, but not the harness.
    "U-HAND": ({"actor": "agent"}, "verifiedOwnerRoute"),
    # Owner wins over a receipt typed next to a hand-written transition
    # (live: ROUTE-REPAIR-1, 2026-09-12).
    "U-OWN-CHECKER": ({"actor": "human-owner", "route": "owner-route",
                       "checkerReceipt": ".itd-memory/verification-loop/X/adjudication-main-a1.json"},
                      "verifiedOwnerRoute"),
}
EXPECTED = {c: sum(1 for _, cls in VERIFIED_ROWS.values() if cls == c) for c in CLASSES}
# 14 verified + 1 blocked (excluded) + 1 open  ->  14 / (16 - 1) = 0.933
EXPECTED_VCR = 0.933


def make_mem(base: Path) -> Path:
    mem = base / "proj" / ".itd-memory"
    mem.mkdir(parents=True)
    units = list(VERIFIED_ROWS) + ["U-BLOCKED", "U-OPEN"]
    (mem / "GOAL.json").write_text(json.dumps({
        "version": "1", "goal": "fixture", "status": "active",
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-03T00:00:00Z",
        "currentUnitId": "",
        "units": [{"id": u, "criterion": "c", "verificationCommand": "true",
                   "status": "pending"} for u in units],
    }), encoding="utf-8")
    events = []
    for i, (unit, (extra, _cls)) in enumerate(VERIFIED_ROWS.items()):
        events.append(ev(unit, "activated", f"2026-01-02T00:{i:02d}:00Z"))
        events.append(ev(unit, "verified", f"2026-01-02T00:{i:02d}:30Z", **extra))
    events.append(ev("U-BLOCKED", "activated", "2026-01-02T01:00:00Z"))
    events.append(ev("U-BLOCKED", "blocked", "2026-01-02T01:00:30Z",
                     checkerReceipt="x.json"))
    events.append(ev("U-OPEN", "activated", "2026-01-02T02:00:00Z"))
    (mem / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return mem


PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
import itd_unit_lifecycle as L
from pathlib import Path
b = L.build(Path(sys.argv[2]))
print(json.dumps({
    "counts": {c: b.get(c) for c in %r},
    "byUnit": {lc["unit"]: lc.get("routeClass") for lc in b["lifecycles"]},
    "verified": b["lifecyclesVerified"], "vcr": b["vcr"],
}))
""" % (CLASSES,)


def probe(module_dir: Path, mem: Path) -> dict | None:
    r = subprocess.run([PY, "-I", "-c", PROBE, str(module_dir), str(mem)],
                       capture_output=True, encoding="utf-8", errors="replace",
                       env=clean_env(), timeout=120)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


# name -> (anchor, replacement, units whose class MUST change under the mutant)
MUTATIONS = {
    "owner class removed": (
        '        return "verifiedOwnerRoute"\n',
        '        pass\n',
        ["U-OWN", "U-OWN-VARIANT", "U-LABEL-ROUTE", "U-LABEL-SPELL", "U-HAND",
         "U-OWN-CHECKER"]),
    "independent class removed": (
        '        return "verifiedIndependent"\n',
        '        pass\n',
        ["U-IND"]),
    "machine-only collapsed into independent": (
        '    return "verifiedMachineOnly"\n',
        '    return "verifiedIndependent"\n',
        ["U-MACH", "U-MACH-RECEIPT", "U-NONE", "U-NONE-CASE", "U-NULL", "U-EMPTY",
         "U-LIST"]),
    "route label trusted verbatim": (
        '_label(event.get("route")) in OWNER_ROUTE_LABELS',
        'event.get("route") == "owner"',
        ["U-LABEL-ROUTE", "U-LABEL-SPELL"]),
    "writer ignored, only the label decides": (
        'by_writer = _label(event.get("actor")) != HARNESS_ACTOR',
        'by_writer = False',
        ["U-HAND"]),
    "literal none trusted as a receipt": (
        '_label(value) not in ABSENT_RECEIPT',
        '_label(value) != ""',
        ["U-NONE", "U-NONE-CASE", "U-NULL"]),
}


def main() -> int:
    import itd_unit_lifecycle as L

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        mem = make_mem(base)
        built = L.build(mem)
        by_unit = {lc["unit"]: lc for lc in built["lifecycles"]}

        # --- each class, on the unmutated module -------------------------
        for unit, (_extra, cls) in VERIFIED_ROWS.items():
            got = by_unit.get(unit, {}).get("routeClass")
            check(f"class: {unit} is {cls}", got == cls, f"got {got!r}")

        for cls in CLASSES:
            check(f"counter: {cls} == {EXPECTED[cls]}",
                  built.get(cls) == EXPECTED[cls], f"got {built.get(cls)!r}")

        # --- exactly one class per verified lifecycle --------------------
        verified = [lc for lc in built["lifecycles"] if lc["outcome"] == "verified"]
        check("exactly one: every verified lifecycle carries one known class",
              bool(verified) and all(lc.get("routeClass") in CLASSES for lc in verified),
              json.dumps([lc["unit"] for lc in verified
                          if lc.get("routeClass") not in CLASSES]))
        others = [lc for lc in built["lifecycles"] if lc["outcome"] != "verified"]
        check("exactly one: a lifecycle that is not verified carries no class",
              len(others) == 2 and all("routeClass" in lc and lc["routeClass"] is None
                                       for lc in others),
              json.dumps([(lc["unit"], lc.get("routeClass", "<missing>")) for lc in others]))
        total = sum(built.get(c) or 0 for c in CLASSES)
        check("sum: the three counters add up to lifecyclesVerified",
              total == built["lifecyclesVerified"] == len(VERIFIED_ROWS),
              f"{total} vs {built['lifecyclesVerified']}")

        # --- vcr keeps its value and definition --------------------------
        denominator = (built["lifecyclesTotal"] - built["lifecyclesExcluded"]
                       - built["lifecyclesWip"])
        check("vcr: value on the fixture is unchanged by classification",
              built["vcr"] == EXPECTED_VCR, f"got {built['vcr']!r}")
        check("vcr: still verified / (total - excluded - wip)",
              built["vcr"] == round(built["lifecyclesVerified"] / denominator, 3))

        # --- itd_metrics.py surfaces all three ---------------------------
        r = subprocess.run([PY, "-I", str(METRICS), str(base)], capture_output=True,
                           encoding="utf-8", errors="replace", env=clean_env(),
                           timeout=120)
        try:
            metrics = json.loads(r.stdout)
        except Exception:
            metrics = {}
        check("metrics: itd_metrics.py exits 0 with JSON", r.returncode == 0 and bool(metrics),
              (r.stderr or "")[-300:])
        for cls in CLASSES:
            check(f"metrics: {cls} surfaced as {EXPECTED[cls]}",
                  metrics.get(cls) == EXPECTED[cls], f"got {metrics.get(cls)!r}")
        check("metrics: the three counters add up to unitsVerified",
              sum(metrics.get(c) or 0 for c in CLASSES) == metrics.get("unitsVerified")
              == len(VERIFIED_ROWS), json.dumps({k: metrics.get(k) for k in
                                                 CLASSES + ("unitsVerified",)}))
        check("metrics: vcr unchanged", metrics.get("vcr") == EXPECTED_VCR,
              f"got {metrics.get('vcr')!r}")
        md = subprocess.run([PY, "-I", str(METRICS), str(base), "--markdown"],
                            capture_output=True, encoding="utf-8", errors="replace",
                            env=clean_env(), timeout=120)
        check("metrics: --markdown table names all three classes",
              md.returncode == 0 and all(f"| {c} |" in md.stdout for c in CLASSES))

        # --- mutation proof ----------------------------------------------
        baseline = probe(SHARED, mem)
        check("mutation: the probe reproduces the in-process result",
              baseline is not None and baseline["byUnit"] ==
              {u: lc.get("routeClass") for u, lc in by_unit.items()},
              json.dumps(baseline))
        source = MODULE.read_text(encoding="utf-8")
        for index, (name, (anchor, replacement, must_change)) in enumerate(MUTATIONS.items()):
            hits = source.count(anchor)
            check(f"mutation [{name}]: anchor is present exactly once", hits == 1,
                  f"{hits} occurrences — the mutant would be vacuous")
            if hits != 1 or baseline is None:
                check(f"mutation [{name}]: kills the expected units", False, "not run")
                continue
            mdir = base / f"mutant-{index}"
            mdir.mkdir()
            (mdir / MODULE.name).write_text(source.replace(anchor, replacement),
                                            encoding="utf-8")
            mutant = probe(mdir, mem)
            survived = (["<mutant did not run>"] if mutant is None else
                        [u for u in must_change
                         if mutant["byUnit"].get(u) == baseline["byUnit"].get(u)])
            check(f"mutation [{name}]: kills the expected units", not survived,
                  "survived: " + json.dumps(survived))
            if mutant is not None:
                untouched = [u for u in baseline["byUnit"] if u not in must_change
                             and mutant["byUnit"].get(u) != baseline["byUnit"].get(u)]
                check(f"mutation [{name}]: changes nothing else", not untouched,
                      json.dumps(untouched))
                check(f"mutation [{name}]: vcr does not depend on the route class",
                      mutant["vcr"] == baseline["vcr"]
                      and mutant["verified"] == baseline["verified"])

    # --- read-only integration against this repository -------------------
    live = ROOT / ".itd-memory"
    if (live / "events.jsonl").exists():
        lb = L.build(live)
        lv = [lc for lc in lb["lifecycles"] if lc["outcome"] == "verified"]
        check("live: every verified lifecycle carries one known class",
              all(lc.get("routeClass") in CLASSES for lc in lv))
        check("live: the three counters add up to lifecyclesVerified",
              sum(lb.get(c) or 0 for c in CLASSES) == lb["lifecyclesVerified"],
              json.dumps({c: lb.get(c) for c in CLASSES}))
        ld = lb["lifecyclesTotal"] - lb["lifecyclesExcluded"] - lb["lifecyclesWip"]
        check("live: vcr keeps its definition",
              lb["vcr"] == (round(lb["lifecyclesVerified"] / ld, 3) if ld else None))
    else:
        check("live: no events.jsonl in this checkout — nothing to integrate", True)

    dupes = sorted({n for n in SEEN_NAMES if SEEN_NAMES.count(n) > 1})
    check("oracle hygiene: every check name is unique", not dupes, json.dumps(dupes))

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
