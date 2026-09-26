#!/usr/bin/env python3
"""verify_tier_source.py — TIER-SOURCE-1: a tests-only scope takes the goal text out of the floor.

Pilot PILOT-LOW-1 (BACKLOG P1 2026-09-25, RETRO-PILOT-LOW-1 observations 1-2): the strict-class
matcher read the unit goal and the Allowed Change Areas of `.itd/SCOPE_LOCK.md` only, so the same
module got `low` from its docstring and `high` from a detailed description with the word
"payment", and a unit that only adds tests could not leave the high route. Owner rule
(`.itd/DECISIONS.md` 2026-09-26): when every path in the Allowed Change Areas is a test path, the
goal text (keywords and paths) does not force `high`; a strict-class path or keyword inside the
areas still does; a mixed scope, a pathless scope and a missing SCOPE_LOCK keep the goal as a source.

Contract of this oracle (all fixtures are synthetic, not code of the pilot project):

  1. `is_test_path` / `tests_only` accept the declared test paths and refuse look-alikes,
     `..` escapes and a scope without any path (fail-closed, never vacuous).
  2. Pilot-style pairs - `Cover <path> (<docstring>) with pytest tests; tests only, product code
     unchanged` vs a detailed description with a strict word or a strict path - get one tier on a
     tests-only scope, through `match_strict_class` and end to end through
     `skills/task/scripts/itd_unit_log.py activate` (declared `low` stays `low`, the set-aside hit
     is recorded as `riskTierExempt`, no `riskTierForced`). A control check proves each pair's
     goal does hit a strict class without the scope, so the pair exercises the exemption.
  3. The floor stays: a money / auth / secrets path or a strict keyword inside a tests-only scope,
     a mixed scope, a pathless scope, no SCOPE_LOCK, a `..` escape, non-test look-alike names and
     a tests-only SCOPE_LOCK whose Current Task does not open with the unit being activated (a
     stale scope of a previous unit, even one that mentions the new unit elsewhere; activate
     prints a hint), prose or a bare name inside a tests item and a glued token keep `high` for
     a lower declared tier; an area hit next to a goal hit records no `riskTierExempt`.
  4. The goal harness STATE projection drops `riskTierExempt` on the activated and the verified
     branch (executed, not read); the docs name the exemption and the oracle is registered in
     tests/run-all.sh.

`--mutations` copies the product tree into a temp dir, applies independent mutations (including
the pre-fix bytes of the two changed modules from commit 06bee64) and requires the suite to go RED
on every one of them.
Run: sh skills/_shared/itd_py.sh tests/verify_tier_source.py [--mutations]
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX_COMMIT = "06bee64"
TEMPLATE = "Cover {path} ({doc}) with pytest tests; tests only, product code unchanged"

# (label, Allowed Change Areas bullets, template goal, detailed goal, class hit by one of the goals)
PAIRS = (
    ("fx-money-keyword", ["tests/test_fx_rates.py"],
     TEMPLATE.format(path="src/fx/rates.py", doc="Convert an amount between two currencies at the daily rate"),
     "Write pytest tests for the rate converter that turns every customer payment into roubles "
     "before it is settled", "money"),
    ("notify-auth-keyword", ["tests/unit/test_notify.py", "tests/unit/conftest.py"],
     TEMPLATE.format(path="app/notify.py", doc="Send a text message to a user"),
     "Tests for the notifier that sends the login code and the password reset link", "auth"),
    ("report-money-keyword", ["tests/test_report.py"],
     TEMPLATE.format(path="lib/report.py", doc="Build a monthly summary"),
     "Pytest tests for the monthly report that lists invoices, refunds and the ledger balance", "money"),
    ("price-money-goal-path", ["tests/test_price_format.py"],
     TEMPLATE.format(path="src/checkout_utils/fmt.py", doc="Format a price with two decimals"),
     "Pytest tests for the price formatter", "money"),
    ("sverka-money-ru", ["tests/test_sverka.py"],
     TEMPLATE.format(path="src/sverka.py", doc="Сверка двух выгрузок по номеру заказа"),
     "Тесты для модуля сверки оплат с выгрузкой маркетплейса", "money"),
    ("client-secrets-jest", ["web/src/__tests__/client.spec.ts"],
     "Cover web/src/client.ts (HTTP client with retries) with jest tests; tests only, product code unchanged",
     "Jest tests for the HTTP client that attaches the access token to every request", "secrets"),
)
HOT_GOAL = PAIRS[0][3]          # a goal that hits `money` on its own
NEUTRAL_GOAL = TEMPLATE.format(path="src/gw.py", doc="Gateway adapter")

TEST_PATHS = ("tests/test_x.py", "tests/", "tests/unit/helpers.py", "pkg/tests/conftest.py", "tests/./x.py",
              "src/__tests__/a.ts", "test/foo.js", "app/foo_test.go", "web/src/a.spec.ts",
              "web/src/a.test.tsx", "test_fx.py", "conftest.py", "./tests/x.py", "/tests/",
              "tests/unit/*.py")
NON_TEST_PATHS = ("tests\\test_win.py", "tests\\..\\src\\x.py", "\u00a0tests/test_a.py", "tests/test_a.py\u00a0", "tests/test_\u212aey.py", " tests/test_a.py",
                  "**/*", "/", "./", "*", ".", "tests/a\u3164b.py", "tests/\u01c0.py", "tests/\u0442\u0435\u0441\u0442.py",
                  "tests/test_x.py|src/gw.py", "tests/a.py+src/b.py", "tests/a\u2192b.py", "\u201ctests/a.py\u201d",
                  "src/fx.py", "tests/../src/fx.py", "../tests/x.py", "a/../tests/x.py", "testdata/rates.json",
                  "src/contest.py", "latest/x.py", "src/attestation.py", "docs/testing.md",
                  "src/latest_test_results.md", ".github/workflows/test.yml", "e.g", "",
                  "docs/api.spec.yaml", "config/app_test.json", "src/data.test.csv")

# (label, raw Allowed Change Areas lines, goal, expected class) - high stays high
FLOOR = (
    ("money-path-in-tests-scope", ["- `tests/test_payment_gateway.py`"], NEUTRAL_GOAL, "money"),
    ("auth-path-in-tests-scope", ["- `tests/auth/test_session.py`"], NEUTRAL_GOAL, "auth"),
    ("keyword-in-tests-scope", ["- `tests/test_rounding.py` - refund rounding cases"], NEUTRAL_GOAL, "money"),
    ("secrets-path-in-tests-scope", ["- `tests/fixtures/.env.test`"], NEUTRAL_GOAL, "secrets"),
    ("mixed-scope", ["- `tests/test_fx_rates.py`", "- `src/fx/rates.py`"], HOT_GOAL, "money"),
    ("pathless-scope", ["- the unit tests only"], HOT_GOAL, "money"),
    ("dotdot-escape", ["- `tests/../src/fx/rates.py`"], HOT_GOAL, "money"),
    ("lookalike-testdata", ["- `testdata/rates.json`"], HOT_GOAL, "money"),
    ("lookalike-contest", ["- `src/contest.py`"], HOT_GOAL, "money"),
    ("lookalike-docs", ["- `docs/testing.md`"], HOT_GOAL, "money"),
    ("area-hit-and-goal-hit", ["- `tests/test_payment_gateway.py`"], HOT_GOAL, "money"),
    ("prose-in-item", ["- `tests/test_fx_rates.py` (new) plus the rate helper"], HOT_GOAL, "money"),
    ("glued-token", ["- tests/test_fx_rates.py|src/fx/rates.py"], HOT_GOAL, "money"),
    ("glob-everything", ["- `tests/` and `**/*`"], HOT_GOAL, "money"),
    ("letterless-alone", ["- **/*"], HOT_GOAL, "money"),
    ("backslash-path", ["- tests\\test_fx_rates.py"], HOT_GOAL, "money"),
    ("nbsp-padded-code-span", ["- `\u00a0tests/test_fx_rates.py`"], HOT_GOAL, "money"),
    ("invisible-letter-join", ["- tests/test_fx_rates.py\u3164src/fx/rates.py"], HOT_GOAL, "money"),
    ("openapi-spec-not-a-test", ["- `docs/api.spec.yaml`"], HOT_GOAL, "money"),
    ("extensionless-file-in-scope", ["- `tests/test_fx_rates.py`", "- `Dockerfile`"], HOT_GOAL, "money"),
    ("bare-name-in-item", ["- tests/test_fx_rates.py, Dockerfile"], HOT_GOAL, "money"),
    ("prose-line-in-scope", ["Tests and the converter:", "- `tests/test_fx_rates.py`"], HOT_GOAL, "money"),
)

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_module(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scope_md(lines: list[str], unit: str = "U-1", forbidden: tuple[str, ...] = ("- `src/`",)) -> str:
    return (f"# Scope Lock\n\n## Current Task\n\n- {unit}: x\n\n## Allowed Change Areas\n\n"
            + "".join(line + "\n" for line in lines)
            + "\n## Forbidden Change Areas\n\n" + "".join(line + "\n" for line in forbidden))


def strict(rc, goal: str, scope: str, classes: dict, unit: str | None = None):
    """match_strict_class with the unit id when the signature takes one; the pre-fix signature
    has three parameters, and a crash there would hide what the old bytes actually decide."""
    if unit is not None and len(inspect.signature(rc.match_strict_class).parameters) >= 4:
        return rc.match_strict_class(goal, scope, classes, unit)
    return rc.match_strict_class(goal, scope, classes)


def bullets(paths: list[str]) -> list[str]:
    return [f"- `{p}`" for p in paths]


def activate(root: Path, goal: str, tier: str, lines: list[str] | None, unit: str = "U-1",
             forbidden: tuple[str, ...] = ("- `src/`",)):
    """Run activate of U-1 in a throwaway project whose SCOPE_LOCK names `unit`;
    return (rc, output, STATE.currentUnit|None)."""
    with tempfile.TemporaryDirectory() as project:
        mem = Path(project) / ".itd-memory"
        mem.mkdir()
        if lines is not None:
            (Path(project) / ".itd").mkdir()
            (Path(project) / ".itd" / "SCOPE_LOCK.md").write_text(scope_md(lines, unit, forbidden), encoding="utf-8")
        cmd = [sys.executable, str(root / "skills" / "task" / "scripts" / "itd_unit_log.py"),
               "activate", "U-1", "--goal", goal, "--risk-tier", tier, "--dir", str(mem)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=project)
        state = mem / "STATE.json"
        cu = json.loads(read(state)).get("currentUnit") if state.is_file() else None
        return r.returncode, r.stdout + r.stderr, cu


def suite(root: Path, quiet: bool = False) -> list[str]:
    """Return the list of failed check names for the product tree at `root`."""
    local_fails: list[str] = []

    def c(name: str, cond: bool, detail: str = "") -> None:
        if not quiet:
            check(name, cond, detail)
        if not cond:
            local_fails.append(name)

    rc = load_module(root / "skills" / "_shared" / "itd_risk_classes.py", "itd_risk_classes_ts")
    policy = json.loads(read(root / "skills" / "_shared" / "PROPORTIONALITY_POLICY.json"))
    classes = rc.load_strict_classes(policy)
    is_test_path = getattr(rc, "is_test_path", None)
    tests_only = getattr(rc, "tests_only", None)
    exempt_goal_hit = getattr(rc, "exempt_goal_hit", None)
    names_unit = getattr(rc, "names_unit", None)
    c("api-is_test_path", callable(is_test_path))
    c("api-names_unit", callable(names_unit))
    c("api-tests_only", callable(tests_only))
    c("api-exempt_goal_hit", callable(exempt_goal_hit))

    # 1. the predicate
    if callable(is_test_path):
        for p in TEST_PATHS:
            c(f"test-path {p!r}", is_test_path(p) is True)
        for p in NON_TEST_PATHS:
            c(f"non-test-path {p!r}", is_test_path(p) is False)
    if callable(tests_only):
        c("tests-only-empty-is-false", tests_only("") is False)
        c("tests-only-prose-is-false", tests_only("- the unit tests only") is False)
        c("tests-only-all-tests", tests_only("- `tests/test_a.py`\n- `tests/unit/`") is True)
        c("tests-only-mixed-is-false", tests_only("- `tests/test_a.py`\n- `src/a.py`") is False)
        for text, want in (
                ("- backend/tests/test_odds_parser.py (new)", True),
                ("- `tests/test_a.py` (updated)", True),
                ("- tests/unit/", True),
                ("* `web/src/a.spec.ts` (NEW)", True),
                ("- `tests/test_a.py`\n\n- `tests/test_b.py`", True),
                ("- `tests/test_a.py` (new)\n  and `tests/unit/test_b.py` (updated)", False),
                ("- `tests/test_a.py` — новые тесты", False),
                ("- `tests/test_a.py` (created)", False),
                ("- `tests/test_a.py` (new) plus x", False),
                ("- **tests/test_a.py**", False),
                ("- `tests/test_a.py`.", False),
                ("- `tests/test_a.py` `tests/test_b.py`", False),
                ("- tests/test_a.py tests/test_b.py", False),
                ("- `tests/test_a.py` (new) (updated)", False),
                ("- `tests/test_a.py` - new tests for\n  the converter", False),
                ("- `tests/test_a.py` (`pytest -q` must pass)", False),
                ("- `tests/test_retry.py` (new) plus the retry helper in the gateway module", False),
                ("- tests/test_x.py, Dockerfile", False),
                ("- `tests/test_a.py` \u201cgateway.py\u201d", False),
                ("- `tests/test_a.py\n- src/gw.py", False),
                ("- `tests/test_a.py`\n  ```\n  rm -rf src\n  ```", False),
                ("- tests/test_x.py|src/gw.py", False),
                ("- tests/test_x.py+src/gw.py", False),
                ("- tests/test_x.py&src/gw.py", False),
                ("- tests/test_x.py\u2192src/gw.py", False),
                ("- tests/test_x.py\u2014src/gw.py", False),
                ("- `tests/` and `**/*`", False),
                ("- `tests/test_a.py`, `/`", False),
                ("- `tests/test_a.py` and `./`", False),
                ("- `tests/test_a.py` and `../`", False),
                ("- `tests/test_a.py` and `*`", False),
                ("- `tests/test_a.py` and `*/*`", False),
                ("- `tests/test_a.py` and ~", False),
                ("- `tests/test_a.py` and `.`", False),
                ("- `tests/*` \u2192 new", False),
                ("- `tests/*`", True),
                ("- tests/test_fx_rates.py\u3164src/fx/rates.py", False),
                ("- tests/test_fx_rates.py\u01c0src/fx/rates.py", False),
                ("-\u00a0`tests/test_a.py`", False),
                ("- `tests/test_a.py`\u00a0(new)", False),
                ("- **/*", False),
                ("- tests\\test_x.py", False),
                ("\t- `tests/test_a.py`", True),
                ("- `tests/test_a.py`\t(new)", True),
                # this case is decided by str.splitlines (it splits on \v, \f and \r), not by the
                # separator class of _TEST_ITEM_RE: widening `[ \t]` to `\s` leaves it unchanged,
                # so that widening is an equivalent mutant (dropping `\t` is caught by the tab cases)
                ("-\v`tests/test_a.py`", False),
                ("- `\u00a0tests/test_a.py`", False),
                ("- `tests/test_a.py\u001f`", False),
                ("- /", False),
                ("- ./", False),
                ("- `*`", False),
                ("- `.`", False),
                ("1. `tests/test_a.py`\n   - `tests/unit/test_b.py`", True),
                ("- `tests/test_a.py`\n- `Dockerfile`", False),
                ("- `tests/test_a.py`, `Makefile`", False),
                ("Tests and the converter:\n- `tests/test_a.py`", False),
                ("- `tests/test_a.py`\n### Backend\n- `tests/test_b.py`", False),
                ("- `tests/test_a.py`\n```\nrm -rf src\n```", False),
                ("- `tests/test_a.py`\n- and the helpers", False)):
            c(f"tests-only {text!r}", tests_only(text) is want)
    if callable(names_unit):
        ct = "# Scope\n\n## Current Task\n\n{}\n\n## Allowed Change Areas\n\n- `tests/test_a.py`\n"
        for first, uid, want in (("- U-1: x", "U-1", True), ("- **U-1**: x", "U-1", True),
                                 ("- `U-1` - x", "U-1", True), ("U-1 - x", "U-1", True),
                                 ("- U-12: x", "U-1", False), ("- XU-1: x", "U-1", False),
                                 ("- U-1.5: x", "U-1", False), ("- U-7: follow-up of U-1", "U-1", False),
                                 ("- x", "U-1", False), ("- U-1: x", "", False)):
            c(f"names-unit {first!r} {uid!r}", names_unit(ct.format(first), uid) is want)
        c("names-unit-title-only-is-false", names_unit("# U-1\n\n## Current Task\n\n- x\n", "U-1") is False)
        c("names-unit-forbidden-only-is-false",
          names_unit(scope_md(["- `tests/test_a.py`"], "U-7", ("- U-1 is the next unit",)), "U-1") is False)

    # 2. pilot-style pairs: one tier whatever the wording
    for label, paths, template, detailed, cls in PAIRS:
        scope = scope_md(bullets(paths))
        control = [rc.match_strict_class(g, "", classes) for g in (template, detailed)]
        c(f"pair-{label}-control-goal-hits-{cls}",
          any(h and h[0] == cls for h in control) and any(h is None for h in control),
          f"control hits={control}")
        hits = [strict(rc, g, scope, classes, "U-1") for g in (template, detailed)]
        c(f"pair-{label}-matcher-one-tier", hits == [None, None], f"hits={hits}")
        tiers = []
        for which, goal in (("template", template), ("detailed", detailed)):
            code, out, cu = activate(root, goal, "low", bullets(paths))
            tiers.append((cu or {}).get("riskTier"))
            c(f"pair-{label}-{which}-activate-rc0", code == 0, out.strip()[-300:])
            c(f"pair-{label}-{which}-not-forced", bool(cu) and "riskTierForced" not in cu
              and "riskTierMatch" not in cu, f"currentUnit={cu}")
            goal_hit = rc.match_strict_class(goal, "", classes)
            exempt = (cu or {}).get("riskTierExempt")
            if goal_hit:
                c(f"pair-{label}-{which}-exempt-recorded",
                  isinstance(exempt, dict) and exempt.get("class") == goal_hit[0]
                  and "tests-only" in str(exempt.get("reason", ""))
                  and goal_hit[2] in str(exempt.get("match", "")), f"riskTierExempt={exempt}")
                c(f"pair-{label}-{which}-exempt-printed", "tests-only" in out, out.strip()[-300:])
            else:
                c(f"pair-{label}-{which}-no-exempt-note", exempt is None, f"riskTierExempt={exempt}")
        c(f"pair-{label}-activate-one-tier", tiers == ["low", "low"], f"tiers={tiers}")

    # 3. the floor stays high
    for label, lines, goal, cls in FLOOR:
        hit = strict(rc, goal, scope_md(lines), classes, "U-1")
        c(f"floor-{label}-matcher-{cls}", bool(hit) and hit[0] == cls, f"hit={hit}")
        code, out, cu = activate(root, goal, "low", lines)
        forced = (cu or {}).get("riskTierForced") or {}
        c(f"floor-{label}-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
          and forced.get("class") == cls and "riskTierExempt" not in (cu or {}),
          f"rc={code} currentUnit={cu}")
    stale = bullets(["tests/test_fx_rates.py"])
    hit = strict(rc, HOT_GOAL, scope_md(stale, "U-7"), classes, "U-1")
    c("floor-stale-scope-of-U-7-matcher-money", bool(hit) and hit[0] == "money", f"hit={hit}")
    code, out, cu = activate(root, HOT_GOAL, "low", stale, unit="U-7")
    c("floor-stale-scope-of-U-7-activate-high", code == 0 and (cu or {}).get("riskTier") == "high"
      and "riskTierExempt" not in (cu or {}), f"rc={code} currentUnit={cu}")
    c("floor-stale-scope-of-U-7-hint-printed", "does not open with U-1" in out, out.strip()[-300:])
    code, out, cu = activate(root, HOT_GOAL, "low", stale, unit="U-7", forbidden=("- U-1 is the next unit",))
    c("floor-stale-scope-names-U-1-in-forbidden-activate-high",
      code == 0 and (cu or {}).get("riskTier") == "high" and "riskTierExempt" not in (cu or {}),
      f"rc={code} currentUnit={cu}")
    hit = rc.match_strict_class(HOT_GOAL, "", classes)
    c("floor-no-scope-lock-matcher-money", bool(hit) and hit[0] == "money", f"hit={hit}")
    code, out, cu = activate(root, HOT_GOAL, "low", None)
    c("floor-no-scope-lock-activate-high", code == 0 and (cu or {}).get("riskTier") == "high",
      f"rc={code} currentUnit={cu}")
    if callable(exempt_goal_hit):
        c("exempt-hit-none-on-mixed-scope",
          exempt_goal_hit(HOT_GOAL, scope_md(FLOOR[4][1]), classes, "U-1") is None)
        c("exempt-hit-none-without-unit-id",
          exempt_goal_hit(HOT_GOAL, scope_md(bullets(["tests/test_fx_rates.py"])), classes) is None)
        eh = exempt_goal_hit(HOT_GOAL, scope_md(bullets(["tests/test_fx_rates.py"])), classes, "U-1")
        c("exempt-hit-reported-on-tests-scope", bool(eh) and eh[0] == "money" and eh[3] == "goal", f"hit={eh}")

    # 4. goal projection, docs, registration
    # the goal harness STATE projection drops a stale riskTierExempt on both branches
    try:
        gv = load_module(root / "skills" / "goal" / "scripts" / "itd_goal_verify.py", "itd_goal_verify_ts")
        stale = {"class": "money", "match": "x", "reason": "tests-only"}
        with tempfile.TemporaryDirectory() as tmp:
            mem = Path(tmp) / ".itd-memory"
            mem.mkdir()
            goal_path = mem / "GOAL.json"
            goal_path.write_text(json.dumps({
                "version": 1, "goal": "g", "status": "active", "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z", "currentUnitId": "",
                "units": [{"id": "G-9", "criterion": "c", "verificationCommand": "true",
                           "status": "pending", "riskTier": "low"}]}), encoding="utf-8")
            unit = json.loads(read(goal_path))["units"][0]
            for decision, before in (("activated", {"id": "U-old", "status": "verified", "riskTier": "low"}),
                                     ("verified", {"id": "G-9", "status": "in_progress", "riskTier": "low"})):
                (mem / "STATE.json").write_text(json.dumps(
                    {"version": 1, "currentUnit": {**before, "riskTierExempt": stale}}), encoding="utf-8")
                gv.write_state_projection(gv.state_projection(goal_path, unit, decision), goal_path, unit, decision)
                cu = json.loads(read(mem / "STATE.json")).get("currentUnit") or {}
                c(f"goal-{decision}-projection-drops-exempt",
                  cu.get("id") == "G-9" and "riskTierExempt" not in cu, repr(cu)[:200])
    except Exception as exc:  # noqa: BLE001 - a crash is a failed check, not a pass
        c("goal-projection-drops-exempt", False, repr(exc)[:200])
    skill = read(root / "skills" / "task" / "SKILL.md")
    c("task-skill-documents-exemption", "riskTierExempt" in skill and "tests-only" in skill)
    adr = read(root / "docs" / "adr" / "ADR-011-default-risk-tier-low.md")
    c("adr-011-amended", "TIER-SOURCE-1" in adr and "tests-only" in adr)
    runall = read(root / "tests" / "run-all.sh")
    c("registered-in-run-all", "verify_tier_source" in runall)
    return local_fails


def copy_product(dst: Path) -> None:
    for rel in ("skills", "docs/adr"):
        shutil.copytree(ROOT / rel, dst / rel, ignore=shutil.ignore_patterns("__pycache__"))
    (dst / "tests").mkdir()
    shutil.copy2(ROOT / "tests" / "run-all.sh", dst / "tests" / "run-all.sh")


def append(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.write_text(read(p) + "\n" + text + "\n", encoding="utf-8")


def replace_once(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    src = read(p)
    assert old in src, f"mutation marker missing in {rel}: {old!r}"
    p.write_text(src.replace(old, new, 1), encoding="utf-8")


RC_REL = "skills/_shared/itd_risk_classes.py"
LOG_REL = "skills/task/scripts/itd_unit_log.py"
GV_REL = "skills/goal/scripts/itd_goal_verify.py"


def m_prefix_bytes(root: Path) -> None:
    for rel in (RC_REL, LOG_REL):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{PREFIX_COMMIT}:{rel}"],
                           capture_output=True, timeout=30)
        if r.returncode:
            raise RuntimeError(f"cannot read pre-fix bytes of {rel} at {PREFIX_COMMIT}")
        (root / rel).write_bytes(r.stdout)


def mutations() -> None:
    cases = (
        ("prefix-bytes-06bee64", m_prefix_bytes),
        ("every-path-is-a-test-path", lambda r: append(r, RC_REL, "is_test_path = lambda token: True")),
        ("exemption-drops-the-areas-too", lambda r: append(r, RC_REL, (
            "_orig_match = match_strict_class\n"
            "def match_strict_class(goal, scope_text, classes, unit_id=''):\n"
            "    if tests_only_scope(scope_text, unit_id):\n"
            "        return None\n"
            "    return _orig_match(goal, scope_text, classes, unit_id)"))),
        ("dotdot-escape-allowed", lambda r: replace_once(r, RC_REL, 'if ".." in parts:', "if False:")),
        ("spec-of-any-extension-is-a-test", lambda r: append(r, RC_REL, "_CODE_EXTS = _CODE_EXTS | {'yaml', 'yml', 'json', 'csv'}")),
        ("trailing-text-allowed", lambda r: replace_once(
            r, RC_REL, r"(?:[ \t]+\((?:new|updated)\))?[ \t]*$", r"(?:[ \t]+\((?:new|updated)\))?.*$")),
        ("backslash-normalised-before-charset", lambda r: replace_once(
            r, RC_REL, 'raw = token or ""', 'raw = (token or "").replace(chr(92), "/")')),
        ("activated-projection-keeps-exempt", lambda r: replace_once(
            r, GV_REL, 'cur.pop("riskTierExempt", None)\n        else:', 'pass\n        else:')),
        ("verified-projection-keeps-exempt", lambda r: replace_once(
            r, GV_REL, 'cur.pop("riskTierExempt", None)\n        state["currentUnit"] = cur',
            'pass\n        state["currentUnit"] = cur')),
        ("letterless-test-path", lambda r: append(r, RC_REL, (
            "_orig_is_test_path = is_test_path\n"
            "is_test_path = lambda token: _orig_is_test_path(token) or not re.search('[a-z]', (token or '').lower())"))),
        ("normalised-before-charset", lambda r: replace_once(
            r, RC_REL, "if not raw or not _SAFE_PATH_RE.fullmatch(raw):",
            "raw = raw.strip().lower()\n    if not raw or not _SAFE_PATH_RE.fullmatch(raw):")),
        ("unicode-path-charset", lambda r: replace_once(
            r, RC_REL, 're.compile(r"[A-Za-z0-9_.\\-/*?]+")', 're.compile(r"[\\w.\\-/*?]+")')),
        ("path-charset-ignored", lambda r: replace_once(
            r, RC_REL, "if not raw or not _SAFE_PATH_RE.fullmatch(raw):", "if not raw:")),
        ("unit-id-anywhere", lambda r: append(r, RC_REL, (
            "names_unit = lambda scope_text, unit_id: bool(unit_id) and unit_id in (scope_text or '')"))),
        ("exempt-written-when-forced", lambda r: replace_once(
            r, LOG_REL, "exempt = None if forced else RC.exempt_goal_hit(", "exempt = RC.exempt_goal_hit(")),
        ("non-item-lines-skipped", lambda r: replace_once(
            r, RC_REL, "return False                    # any other line", "continue  #")),
        ("vacuous-tests-only", lambda r: append(r, RC_REL, (
            "_orig_tests_only = tests_only\n"
            "tests_only = lambda areas: _orig_tests_only(areas) or not (areas or '').strip()"))),
        ("unit-binding-ignored", lambda r: append(r, RC_REL, "names_unit = lambda scope_text, unit_id: True")),
        ("exempt-note-not-recorded", lambda r: replace_once(
            r, LOG_REL, 'state["currentUnit"]["riskTierExempt"] = exempt_note', "pass")),
    )
    for label, apply in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "product"
            copy_product(root)
            try:
                apply(root)
            except (AssertionError, RuntimeError) as exc:
                check(f"mutation-{label}-applied", False, str(exc))
                continue
            try:
                red = suite(root, quiet=True)
            except Exception as exc:  # a mutant that crashes the suite is caught too
                red = [f"crash: {exc!r}"]
            check(f"mutation-{label}-lethal", bool(red), "suite stayed green")


def main() -> int:
    baseline = suite(ROOT)
    if "--mutations" in sys.argv[1:]:
        if baseline:
            print("skip mutations: baseline suite is red")
        else:
            mutations()
    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
