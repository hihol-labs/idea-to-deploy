#!/usr/bin/env python3
"""verify_adjudication_channel_clock.py - FLAKE-ADJCHAN-1: receipt selection without the clock.

BACKLOG 2026-09-11 (ledger-close BROKER-ISOLATION): the wall clock of this host steps BACKWARDS
(WSL2 resync with Windows, measured -2.478 s and -5.366 s inside 45 seconds). The oracle helper
`newest_receipt` in tests/verify_adjudication_channel.py picked the freshest receipt as
`sorted(..., key=st_mtime)[-1]`, so a receipt written LATER could carry a SMALLER st_mtime and the
helper returned the previous run's file: the `U-v2:general-review` mint got the `U-v2` checker
receipt, refused with `receipt belongs to another unit`, and the suite went red inside the
machine-receipt isolation while it was green on the host. That red leg immobilised the machine
receipt and with it every gate that needs one.

Contract of this oracle (all in a temporary directory; the real oracle is loaded from source,
never executed):

  1. Static (AST of the code, not text): the helper reads neither the clock nor file times, and
     the whole oracle reads no file times.
  2. A fixture with deliberately INVERTED mtimes - the receipt written second is stamped older by
     the measured step - reproduces the defect for an mtime sort (fixture sanity), and the helper
     still selects the receipt minted since the snapshot: clock-free by construction.
  3. Equal mtimes (a tie) do not matter either; nothing new since the snapshot is None; an empty
     receipts root is None; two new receipts since one snapshot are a refusal (an exception), never
     "the last element".
  4. Every checker-receipt pick in the oracle is snapshot-bound (inside `checker`, with `before`),
     so the observed site cannot regress to an unbound search.
  5. This suite is registered in tests/run-all.sh.

RED on the pre-fix helper (no snapshot parameter, st_mtime sort), GREEN after.
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "tests" / "verify_adjudication_channel.py"
RUNALL = ROOT / "tests" / "run-all.sh"
RECEIPTS = Path(".itd-memory") / "verification-loop" / "receipts"
MEASURED_BACKWARD_STEP_SECONDS = 5.366  # BACKLOG 2026-09-11, the larger of the two steps
FILE_TIME_ATTRS = {"st_mtime", "st_mtime_ns", "st_ctime", "st_ctime_ns", "st_atime",
                   "st_atime_ns", "getmtime", "getctime", "getatime"}
CLOCK_ATTRS = FILE_TIME_ATTRS | {"stat", "lstat", "time", "monotonic", "perf_counter",
                                 "time_ns", "monotonic_ns", "now", "utcnow"}

fails: list[str] = []
passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        fails.append(f"{name}: {detail}"[:400])
        print(f"FAIL {name}: {detail}"[:400], file=sys.stderr)


def load_helpers() -> tuple[types.ModuleType, ast.Module, str]:
    """Load only imports, functions and classes of the oracle - none of its top-level runs."""
    source = ORACLE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ORACLE))
    keep = [node for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))]
    module = types.ModuleType("adjudication_channel_helpers")
    module.__file__ = str(ORACLE)
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(ORACLE), "exec"), module.__dict__)
    return module, tree, source


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def attribute_hits(node: ast.AST, names: set[str]) -> list[str]:
    """Attribute and name lookups in CODE (docstrings and comments never count)."""
    hits: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in names:
            hits.append(f"{sub.attr}@{sub.lineno}")
        elif isinstance(sub, ast.Name) and sub.id in names & {"time", "monotonic", "perf_counter"}:
            hits.append(f"{sub.id}@{sub.lineno}")
    return hits


def pick_kind(call: ast.Call) -> str | None:
    """The literal `kind` of a newest_receipt call (positional or keyword); None if not literal."""
    node = call.args[1] if len(call.args) > 1 else next(
        (k.value for k in call.keywords if k.arg == "kind"), None)
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def write_receipt(root: Path, digest: str, name: str, mtime: float | None = None) -> Path:
    path = root / RECEIPTS / digest / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"kind": "checker", "verdict": "BLOCKED"}\n', encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def select(module: types.ModuleType, root: Path, kind: str, before) -> tuple[object, str]:
    """Call the helper with a snapshot; a helper without the parameter is the pre-fix one."""
    try:
        return module.newest_receipt(root, kind, before=before), ""
    except TypeError as exc:
        if "before" in str(exc):
            return None, f"helper accepts no snapshot, selection is not clock-free: {exc}"
        return exc, ""
    except Exception as exc:  # noqa: BLE001 - reported by name
        return exc, ""


def main() -> int:
    module, tree, source = load_helpers()
    check("helper-present", callable(getattr(module, "newest_receipt", None)),
          "newest_receipt is not a function of the oracle")

    # 1. Static: no clock anywhere in the helper or the oracle.
    helper = function_node(tree, "newest_receipt")
    hits = attribute_hits(helper, CLOCK_ATTRS) if helper else ["<no newest_receipt>"]
    check("helper-source-clock-free", helper is not None and not hits,
          f"newest_receipt reads the clock or file times: {hits}")
    oracle_hits = attribute_hits(tree, FILE_TIME_ATTRS)
    check("oracle-file-times-free", not oracle_hits,
          f"the oracle still reads file times: {oracle_hits}")

    with tempfile.TemporaryDirectory(prefix="adjchan-clock-") as td:
        root = Path(td)

        # 2. Inverted mtimes: the receipt written second is stamped older.
        first = write_receipt(root, "0123456789abcdef", "U-v2-checker-1111111111111111.json")
        now = os.stat(first).st_mtime
        snapshot = frozenset((root / RECEIPTS).rglob("*checker*.json"))
        second = write_receipt(root, "0123456789abcdef",
                               "U-v2-general-review-checker-2222222222222222.json",
                               mtime=now - MEASURED_BACKWARD_STEP_SECONDS)
        os.utime(first, (now, now))
        check("fixture-mtimes-inverted",
              os.stat(second).st_mtime < os.stat(first).st_mtime,
              "the later receipt must carry the older st_mtime")
        by_mtime = sorted((root / RECEIPTS).rglob("*checker*.json"),
                          key=lambda p: os.stat(p).st_mtime)[-1]
        check("fixture-reproduces-the-defect", by_mtime == first,
              f"an st_mtime sort had to return the previous run's file, got {by_mtime.name}")
        picked, why = select(module, root, "checker", snapshot)
        check("inverted-mtime-selects-the-minted-receipt", picked == second,
              why or f"expected {second.name}, got {getattr(picked, 'name', picked)!r}")
        picked_first, why = select(module, root, "checker", frozenset())
        # Two receipts and an empty snapshot: ambiguity is a refusal, never the last element.
        check("two-new-receipts-refuse", isinstance(picked_first, Exception),
              why or f"expected a refusal, got {getattr(picked_first, 'name', picked_first)!r}")

        # 3. Equal mtimes, nothing new, empty root.
        tie_root = root / "tie"
        older = write_receipt(tie_root, "fedcba9876543210", "U-adj-checker-aaaaaaaaaaaaaaaa.json")
        stamp = os.stat(older).st_mtime
        tie_snapshot = frozenset((tie_root / RECEIPTS).rglob("*checker*.json"))
        newer = write_receipt(tie_root, "fedcba9876543210",
                              "U-adj-checker-bbbbbbbbbbbbbbbb.json", mtime=stamp)
        os.utime(older, (stamp, stamp))
        check("fixture-mtimes-tied", os.stat(older).st_mtime == os.stat(newer).st_mtime,
              "the tie fixture must stamp both receipts identically")
        picked, why = select(module, tie_root, "checker", tie_snapshot)
        check("tied-mtimes-select-the-minted-receipt", picked == newer,
              why or f"expected {newer.name}, got {getattr(picked, 'name', picked)!r}")
        full = frozenset((tie_root / RECEIPTS).rglob("*checker*.json"))
        picked, why = select(module, tie_root, "checker", full)
        check("nothing-new-is-none", picked is None and not why,
              why or f"expected None, got {getattr(picked, 'name', picked)!r}")
        picked, why = select(module, tie_root, "adjudication", frozenset())
        check("other-kind-absent-is-none", picked is None and not why,
              why or f"expected None, got {getattr(picked, 'name', picked)!r}")
        picked, why = select(module, root / "never-created", "checker", frozenset())
        check("empty-root-is-none", picked is None and not why,
              why or f"expected None, got {getattr(picked, 'name', picked)!r}")

    # 4. Every checker-receipt pick in the oracle is snapshot-bound.
    unbound: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "newest_receipt"):
                continue
            kind = pick_kind(call)
            if kind is None or kind == "checker":
                # A non-literal kind is treated as a checker pick: fail closed.
                bound = node.name == "checker" and any(k.arg == "before" for k in call.keywords)
                if not bound:
                    unbound.append(f"{node.name}:{call.lineno}")
    checker_picks = [call.lineno for call in ast.walk(tree)
                     if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                     and call.func.id == "newest_receipt" and pick_kind(call) in (None, "checker")]
    check("checker-picks-are-snapshot-bound", not unbound and len(checker_picks) == 1,
          f"unbound checker picks: {unbound}; checker picks in the oracle: {checker_picks}")

    # 5. Registered in run-all.
    runall = RUNALL.read_text(encoding="utf-8")
    tokens: set[str] = set()
    for variable in ("CORE", "FULL"):
        match = re.search(rf'^{variable}="([^"]*)"', runall, re.M)
        if match:
            tokens.update(match.group(1).replace("\\\n", " ").split())
    check("run-all-registered", "verify_adjudication_channel_clock" in tokens,
          "verify_adjudication_channel_clock must be a token of CORE or FULL in tests/run-all.sh")

    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed ({passed} passed)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
