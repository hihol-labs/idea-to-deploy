#!/usr/bin/env python3
"""verify_stop_rule_closed_contract.py — STOPRULE-STUB-1: the live binding knows the closed contract.

BACKLOG P1 2026-10-01: after every ledger-close `activeFollowup` is the record that
`scripts/itd_closure_delta.py` requires (`{unitId: "", status: "none", note?}`), while
`itd_stop_rule.live_policy_binding` demanded a non-empty unit id and raised. `tests/verify_stop_rule.py`
calls the live binding on the repository at import time, so it and the aggregate
`tests/verify_route_debts.py` were red on main between units. Owner decision 2026-10-01 (variant A,
`.itd/DECISIONS.md`): the binding returns the state NO_ACTIVE_UNIT for exactly that record; variant B
(closure-delta accepts a stub naming the closed unit) is rejected - the binding would then report
ALIGNED for a closed unit.

Contract of this oracle (fixtures are synthetic; the last check copies the tracked tree):

  1. The closed record - exactly `{unitId: "", status: "none"}` plus an optional `note` of any type
     (closure-delta does not check its type either, so the binding accepts what the writer accepts) - with
     `STATE.currentUnit` absent or in a terminal lifecycle status gives `state: NO_ACTIVE_UNIT`,
     `aligned: false`, empty unit ids and no criteria, and raises nothing.
  2. Every other shape keeps the refusal (`StopRuleError`): an empty unit id with another or a
     missing status, extra keys, a blank unit id, an `activeFollowup` or `STATE.currentUnit` that is
     not an object, and the closed record while `STATE.currentUnit` is in progress, has no status or
     is not an object. The pre-existing results carry `state` ALIGNED or ROUTE_DEFECT.
  3. `scripts/itd_stop_rule.py --check-binding` prints `BINDING   NO_ACTIVE_UNIT` with a WHY and a
     FIX line and exits 2 (no review may start), `--json` carries the state; a refused shape prints
     `STOP-RULE INPUT REJECTED` and no traceback.
  4. Drift guards: the closed-record keys equal `FOLLOWUP_EMPTY_KEYS` of
     `scripts/itd_closure_delta.py`, the terminal statuses equal `TERMINALS` of
     `skills/_shared/itd_unit_lifecycle.py` (both read as literals, not imported).
  5. The docs name the state and the oracle is registered in tests/run-all.sh.
  6. Full run only: on a copy of the tracked tree whose acceptance contract carries the closed record
     and whose STATE.currentUnit is verified, `tests/verify_stop_rule.py` exits 0.

`--mutations` copies the product files into a temp dir, applies independent mutations (including the
pre-fix bytes of `scripts/itd_stop_rule.py` from commit 58ded36) and requires checks 1-5 to go RED.
Run: sh skills/_shared/itd_py.sh tests/verify_stop_rule_closed_contract.py [--mutations]
"""
from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX_COMMIT = "58ded36"
RULE_REL = "scripts/itd_stop_rule.py"
POLICY_REL = ".itd/STOP_RULE_POLICY.json"
CLOSED = {"unitId": "", "status": "none", "note": "No active unit - U-1 closed"}
TERMINALS = ("verified", "blocked", "skipped", "abandoned", "superseded")

# (label, activeFollowup, STATE document) - the closed contract: NO_ACTIVE_UNIT, no exception
CLOSED_CASES = [
    ("closed-with-note-after-verified", CLOSED, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-without-note", {"unitId": "", "status": "none"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-empty-note", {"unitId": "", "status": "none", "note": ""}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-no-current-unit", CLOSED, {}),
    ("closed-current-unit-null", CLOSED, {"currentUnit": None}),
    ("closed-note-null", {"unitId": "", "status": "none", "note": None}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-note-number", {"unitId": "", "status": "none", "note": 0}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-note-list", {"unitId": "", "status": "none", "note": []}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-note-false", {"unitId": "", "status": "none", "note": False}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-note-object", {"unitId": "", "status": "none", "note": {}}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
] + [(f"closed-after-{status}", CLOSED, {"currentUnit": {"id": "U-1", "status": status}})
     for status in TERMINALS]

# (label, activeFollowup, STATE document) - still refused
REFUSED_CASES = [
    ("empty-id-status-open", {"unitId": "", "status": "open"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("empty-id-without-status", {"unitId": ""}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("empty-id-status-closed", {"unitId": "", "status": "closed"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("closed-with-extra-key", {**CLOSED, "openedAt": "2026-10-01"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("blank-id-status-none", {"unitId": "  ", "status": "none"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("null-id-status-none", {"unitId": None, "status": "none"}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("empty-follow-up", {}, {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("follow-up-not-an-object", "none", {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("follow-up-a-list", ["U-1"], {"currentUnit": {"id": "U-1", "status": "verified"}}),
    ("open-follow-up-ledger-unit-a-string", {"unitId": "U-1", "status": "open"}, {"currentUnit": "U-1"}),
    ("open-follow-up-ledger-unit-a-list", {"unitId": "U-1", "status": "open"}, {"currentUnit": ["U-1"]}),
    ("closed-but-ledger-unit-without-status", CLOSED, {"currentUnit": {"id": "U-1"}}),
    ("closed-but-ledger-unit-empty", CLOSED, {"currentUnit": {}}),
    ("closed-but-ledger-unit-not-an-object", CLOSED, {"currentUnit": "U-1"}),
    ("closed-but-ledger-status-not-a-string", CLOSED, {"currentUnit": {"id": "U-1", "status": ["verified"]}}),
] + [(f"closed-but-ledger-{status}", CLOSED, {"currentUnit": {"id": "U-1", "status": status}})
     for status in ("in_progress", "verifying", "recovery_required", "pending", "VERIFIED", "")]

fails: list[str] = []
checked = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global checked
    checked += 1
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


def literal(path: Path, name: str):
    """The literal value assigned to a module-level `name` (set/frozenset/tuple calls unwrapped)."""
    for node in ast.parse(read(path)).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = node.value
            if isinstance(value, ast.Call) and getattr(value.func, "id", "") in ("frozenset", "set", "tuple"):
                value = value.args[0] if value.args else ast.Tuple(elts=[], ctx=ast.Load())
            return ast.literal_eval(value)
    raise LookupError(f"{name} is not assigned in {path}")


def fixture(scratch: Path, follow_up, state: dict, criteria: list | None = None) -> Path:
    (scratch / ".itd").mkdir()
    (scratch / ".itd-memory").mkdir()
    (scratch / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps(
        {"activeFollowup": follow_up, "criteria": criteria or []}, ensure_ascii=False), encoding="utf-8")
    (scratch / ".itd-memory" / "STATE.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return scratch


def cli(root: Path, project: Path, *extra: str):
    r = subprocess.run([sys.executable, str(root / RULE_REL), "--check-binding", "--root", str(project),
                        "--policy", str(root / POLICY_REL), *extra],
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def suite(root: Path, quiet: bool = False, full: bool = True) -> list[str]:
    """Return the list of failed check names for the product tree at `root`."""
    local_fails: list[str] = []

    def c(name: str, cond: bool, detail: str = "") -> None:
        if not quiet:
            check(name, cond, detail)
        if not cond:
            local_fails.append(name)

    rule = load_module(root / RULE_REL, "itd_stop_rule_closed_contract")
    policy = rule.load_policy(root / POLICY_REL)
    c("api-NO_ACTIVE_UNIT", getattr(rule, "NO_ACTIVE_UNIT", None) == "NO_ACTIVE_UNIT")

    # 1. the closed contract
    for label, follow_up, state in CLOSED_CASES:
        with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
            project = fixture(Path(scratch), follow_up, state, [{"id": "U-1-a", "status": "passed"}])
            try:
                b = rule.live_policy_binding(policy, project)
            except Exception as exc:  # noqa: BLE001 - any exception is the defect
                c(f"closed-{label}-no-exception", False, f"{type(exc).__name__}: {exc}")
                continue
            c(f"closed-{label}-state", b.get("state") == "NO_ACTIVE_UNIT", f"binding={b}")
            c(f"closed-{label}-not-aligned", b.get("aligned") is False and b.get("statusSatisfied") is False,
              f"binding={b}")
            c(f"closed-{label}-no-unit-no-criteria",
              (b.get("ledgerUnit"), b.get("contractUnit"), b.get("criteriaPresent"),
               b.get("criteriaTotal"), b.get("criteriaMatchingStatus")) == ("", "", False, 0, 0), f"binding={b}")
            c(f"closed-{label}-required-status-reported",
              b.get("requiredCriteriaStatus") == policy["policyBinding"]["requireCriteriaStatus"], f"binding={b}")

    # 2. everything else is refused; the old results name their state
    for label, follow_up, state in REFUSED_CASES:
        with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
            project = fixture(Path(scratch), follow_up, state, [{"id": "U-1-a", "status": "passed"}])
            try:
                b = rule.live_policy_binding(policy, project)
            except rule.StopRuleError:
                c(f"refused-{label}", True)
            except Exception as exc:  # noqa: BLE001
                c(f"refused-{label}", False, f"{type(exc).__name__} instead of StopRuleError: {exc}")
            else:
                c(f"refused-{label}", False, f"accepted: {b}")
    for label, contract_unit, statuses, want in (
            ("aligned", "U-1", ["passed"], "ALIGNED"),
            ("foreign-unit", "U-2", ["passed"], "ROUTE_DEFECT"),
            ("pending-criterion", "U-1", ["pending"], "ROUTE_DEFECT"),
            ("no-criteria", "U-1", [], "ROUTE_DEFECT")):
        with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
            project = fixture(Path(scratch), {"unitId": contract_unit, "status": "open"},
                              {"currentUnit": {"id": "U-1", "status": "in_progress"}},
                              [{"id": f"U-1-{i}", "status": s} for i, s in enumerate(statuses)])
            b = rule.live_policy_binding(policy, project)
            c(f"state-{label}", b.get("state") == want and b.get("aligned") is (want == "ALIGNED"), f"binding={b}")
    # the closed record with a unit in progress is a broken contract, not an aligned one
    with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
        project = fixture(Path(scratch), CLOSED, {"currentUnit": {"id": "U-1", "status": "in_progress"}})
        try:
            rule.live_policy_binding(policy, project)
            c("refused-message-names-the-unit-in-progress", False, "accepted")
        except rule.StopRuleError as exc:
            c("refused-message-names-the-unit-in-progress", "in_progress" in str(exc), str(exc))

    # 3. the CLI
    with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
        project = fixture(Path(scratch), CLOSED, {"currentUnit": {"id": "U-1", "status": "verified"}})
        code, out, err = cli(root, project)
        c("cli-exit-2", code == 2, f"rc={code} out={out!r} err={err!r}")
        c("cli-prints-state", "BINDING   NO_ACTIVE_UNIT" in out, out)
        c("cli-prints-why-and-fix", "WHY:" in out and "FIX:" in out, out)
        c("cli-no-traceback", "Traceback" not in out + err, err[-300:])
        code, out, err = cli(root, project, "--json")
        try:
            data = json.loads(out)
        except ValueError:
            data = {}
        c("cli-json-state", code == 2 and data.get("state") == "NO_ACTIVE_UNIT" and data.get("aligned") is False,
          f"rc={code} out={out!r}")
    with tempfile.TemporaryDirectory(prefix="itd-stub-") as scratch:
        project = fixture(Path(scratch), CLOSED, {"currentUnit": {"id": "U-1", "status": "in_progress"}})
        code, out, err = cli(root, project)
        c("cli-refused-shape", code == 2 and "STOP-RULE INPUT REJECTED" in err
          and "Traceback" not in out + err and "NO_ACTIVE_UNIT" not in out, f"rc={code} out={out!r} err={err!r}")

    # 4. drift guards against the two writers of the shapes
    try:
        keys = set(literal(root / RULE_REL, "CLOSED_FOLLOWUP_KEYS"))
        terminals = tuple(literal(root / RULE_REL, "LEDGER_TERMINAL_STATUSES"))
    except (LookupError, ValueError, SyntaxError) as exc:
        keys, terminals = None, None
        c("drift-constants-present", False, repr(exc))
    if keys is not None:
        c("drift-closed-keys-equal-closure-delta",
          keys == set(literal(root / "scripts" / "itd_closure_delta.py", "FOLLOWUP_EMPTY_KEYS")), str(keys))
        c("drift-terminals-equal-lifecycle",
          set(terminals) == set(literal(root / "skills" / "_shared" / "itd_unit_lifecycle.py", "TERMINALS")),
          str(terminals))

    # 5. docs and registration
    docs = " ".join(read(root / "docs" / "VERIFICATION_LOOP.md").split())
    c("docs-name-the-state", "NO_ACTIVE_UNIT" in docs and "STOPRULE-STUB-1" in docs)
    c("registered-in-run-all", "verify_stop_rule_closed_contract" in read(root / "tests" / "run-all.sh"))

    # 6. the tracked tree between units
    if full:
        c("tracked-tree-with-closed-contract-runs-verify-stop-rule", *between_units(root))
    return local_fails


def between_units(root: Path) -> tuple[bool, str]:
    """Copy the tracked files, put the closed record into the contract and a verified unit into STATE,
    run tests/verify_stop_rule.py there."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, timeout=60)
    if listed.returncode:
        return False, "git ls-files failed"
    with tempfile.TemporaryDirectory(prefix="itd-stub-tree-") as scratch:
        tree = Path(scratch) / "repo"
        for rel in filter(None, listed.stdout.decode("utf-8").split("\0")):
            src = root / rel
            if src.is_file() and not src.is_symlink():
                (tree / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tree / rel)
        contract_path = tree / ".itd" / "ACCEPTANCE_CONTRACT.json"
        contract = json.loads(read(contract_path))
        contract["activeFollowup"] = dict(CLOSED)
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        state_path = tree / ".itd-memory" / "STATE.json"
        state = json.loads(read(state_path))
        state["currentUnit"] = {**(state.get("currentUnit") or {"id": "U-1"}), "status": "verified"}
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        r = subprocess.run([sys.executable, "tests/verify_stop_rule.py"], cwd=tree, capture_output=True,
                           text=True, timeout=600)
        tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
        return r.returncode == 0, f"rc={r.returncode} tail={tail}"


PRODUCT_FILES = (RULE_REL, POLICY_REL, "scripts/itd_closure_delta.py", "skills/_shared/itd_unit_lifecycle.py",
                 "docs/VERIFICATION_LOOP.md", "tests/run-all.sh")


def copy_product(dst: Path) -> None:
    for rel in PRODUCT_FILES:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst / rel)


def replace_once(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    src = read(p)
    assert src.count(old) == 1, f"mutation marker must occur exactly once in {rel}: {old!r} ({src.count(old)})"
    p.write_text(src.replace(old, new, 1), encoding="utf-8")


def m_prefix_bytes(root: Path) -> None:
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{PREFIX_COMMIT}:{RULE_REL}"], capture_output=True, timeout=30)
    if r.returncode:
        raise RuntimeError(f"cannot read pre-fix bytes of {RULE_REL} at {PREFIX_COMMIT}")
    (root / RULE_REL).write_bytes(r.stdout)


def mutations() -> None:
    cases = (
        (f"prefix-bytes-{PREFIX_COMMIT}", m_prefix_bytes),
        ("extra-keys-accepted", lambda r: replace_once(
            r, RULE_REL, "set(followup) <= CLOSED_FOLLOWUP_KEYS", "True")),
        ("any-status-accepted", lambda r: replace_once(
            r, RULE_REL, 'followup.get("status") == "none"', "True")),
        ("blank-id-accepted", lambda r: replace_once(
            r, RULE_REL, 'followup.get("unitId") == ""', 'not str(followup.get("unitId", "")).strip()')),
        ("note-type-required", lambda r: replace_once(
            r, RULE_REL, 'and followup.get("status") == "none")',
            'and followup.get("status") == "none" and isinstance(followup.get("note", ""), str))')),
        ("note-bool-refused", lambda r: replace_once(
            r, RULE_REL, 'and followup.get("status") == "none")',
            'and followup.get("status") == "none" and not isinstance(followup.get("note"), bool))')),
        ("note-object-refused", lambda r: replace_once(
            r, RULE_REL, 'and followup.get("status") == "none")',
            'and followup.get("status") == "none" and not isinstance(followup.get("note"), dict))')),
        ("ledger-unit-type-unguarded", lambda r: replace_once(
            r, RULE_REL, 'current.get("id") if isinstance(current, dict) else None', 'current.get("id")')),
        ("follow-up-type-unguarded", lambda r: replace_once(
            r, RULE_REL, 'raise StopRuleError(f"activeFollowup must be an object, got {type(followup).__name__}")',
            "pass")),
        ("ledger-unit-in-progress-ignored", lambda r: replace_once(
            r, RULE_REL, "status not in LEDGER_TERMINAL_STATUSES", "False")),
        ("ledger-without-unit-refused", lambda r: replace_once(
            r, RULE_REL, "current is not None and status", "status")),
        ("no-active-unit-aligned", lambda r: replace_once(
            r, RULE_REL, '"statusSatisfied": False, "aligned": False}', '"statusSatisfied": False, "aligned": True}')),
        ("no-active-unit-reports-closed-unit", lambda r: replace_once(
            r, RULE_REL, '"state": NO_ACTIVE_UNIT, "ledgerUnit": ""',
            '"state": NO_ACTIVE_UNIT, "ledgerUnit": str((current or {}).get("id", ""))')),
        ("old-results-without-state", lambda r: replace_once(
            r, RULE_REL, '"state": "ALIGNED" if aligned else "ROUTE_DEFECT",', "")),
        ("cli-why-fix-dropped", lambda r: replace_once(
            r, RULE_REL, "if state == NO_ACTIVE_UNIT:", "if False:")),
        ("cli-exit-0-on-no-active-unit", lambda r: replace_once(
            r, RULE_REL, 'return 0 if binding["aligned"]', 'return 0 if binding["aligned"] or binding["state"] == NO_ACTIVE_UNIT')),
        ("closed-keys-drift", lambda r: replace_once(
            r, RULE_REL, 'CLOSED_FOLLOWUP_KEYS = frozenset({"unitId", "status", "note"})',
            'CLOSED_FOLLOWUP_KEYS = frozenset({"unitId", "status", "note", "closedAt"})')),
        ("terminals-drift", lambda r: replace_once(
            r, RULE_REL, '"abandoned", "superseded")', '"abandoned", "superseded", "in_progress")')),
        ("docs-dropped", lambda r: replace_once(r, "docs/VERIFICATION_LOOP.md", "NO_ACTIVE_UNIT", "NO_UNIT")),
        ("unregistered", lambda r: replace_once(
            r, "tests/run-all.sh", " verify_stop_rule_closed_contract", "")),
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
                red = suite(root, quiet=True, full=False)
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
    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed ({checked - len(fails)} passed)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
