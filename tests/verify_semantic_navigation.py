#!/usr/bin/env python3
"""Behavioral and honesty checks for provider-neutral semantic navigation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "skills" / "_shared" / "itd_semantic_navigation.py"
REGISTRY = ROOT / "docs" / "templates" / "itd" / "TOOL_CAPABILITY_REGISTRY.json"
DEMAND = ROOT / "docs" / "semantic-navigation" / "DEMAND.json"
PILOT_INDEX = ROOT / "docs" / "harness-demo-pilots" / "INDEX.json"
EXPECTED_DEMAND_SHA = "bae187f61809d876bfc4eacf9c65c35548183b27b0b65cf212eb34d18ac77a5d"


class Failure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


def run(root: pathlib.Path, language: str, operation: str,
        symbol: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, str(PROVIDER), "--root", str(root), "--language", language,
         "--operation", operation, "--symbol", symbol],
        cwd=ROOT, text=True, capture_output=True, timeout=10, check=False,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result, payload


def tree_snapshot(root: pathlib.Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            snapshot[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return snapshot


def validate_registry() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    navigation = next(row for row in registry["tools"]
                      if row["id"] == "semantic-navigation")
    demand = navigation["demandGate"]
    semantic = navigation["semanticNavigation"]
    require(demand == {
        "status": "activated",
        "evidence": "docs/semantic-navigation/DEMAND.json",
        "evidenceSha256": EXPECTED_DEMAND_SHA,
    }, "registry demand gate is not exactly evidence-bound")
    require(hashlib.sha256(DEMAND.read_bytes()).hexdigest() == EXPECTED_DEMAND_SHA,
            "demand evidence changed")
    require(semantic["provider"] == "skills/_shared/itd_semantic_navigation.py",
            "provider path is not host-neutral and repository-relative")
    require(semantic["languages"] == ["python", "typescript"],
            "language coverage is not exact")
    require(semantic["operations"] == ["definitions", "references", "outline"],
            "operation coverage is not exact")
    require(semantic["confidence"] == {"python": "high", "typescript": "medium"},
            "confidence declaration is inflated or incomplete")
    require(semantic["fallback"]["semantic"] is False
            and semantic["fallback"]["confidence"] == "textual",
            "fallback is not honestly non-semantic")
    require(semantic["network"] is False and semantic["shell"] is False
            and semantic["sideEffects"] == "none",
            "read-only provider boundaries are not declared")


def validate_python(root: pathlib.Path) -> None:
    (root / "sample.py").write_text(
        "def reconcile(value: str) -> bool:\n"
        "    shadow = 'reconcile is not a reference'\n"
        "    return bool(value)\n\n"
        "# reconcile in a comment is not a reference\n"
        "result = reconcile('x')\n",
        encoding="utf-8",
    )
    definition, d_payload = run(root, "python", "definitions", "reconcile")
    reference, r_payload = run(root, "python", "references", "reconcile")
    outline, o_payload = run(root, "python", "outline", "reconcile")
    require(definition.returncode == reference.returncode == outline.returncode == 0,
            "Python semantic query failed")
    for payload in (d_payload, r_payload, o_payload):
        require(payload["semantic"] is True and payload["confidence"] == "high",
                "Python AST result is not honestly labelled")
        require(payload["warnings"] == [], "valid Python produced warnings")
    require([(item["kind"], item["line"]) for item in d_payload["results"]]
            == [("definition", 1)], "Python definition is inaccurate")
    require([(item["kind"], item["line"]) for item in r_payload["results"]]
            == [("reference", 6)], "Python references include strings/comments or miss the call")
    symbols = {item["symbol"] for item in o_payload["results"]}
    require({"reconcile", "shadow", "result"} <= symbols,
            "Python outline omits declared symbols")
    require(len({json.dumps(payload["results"], sort_keys=True)
                 for payload in (d_payload, r_payload, o_payload)}) == 3,
            "Python operations are not distinct")


def validate_typescript(root: pathlib.Path) -> None:
    (root / "sample.ts").write_text(
        "export function reconcile(value: string): boolean {\n"
        "  const nested = value;\n"
        "  return !!nested;\n"
        "}\n"
        "const decoy = 'reconcile'; // reconcile is masked\n"
        "const result = reconcile('x');\n",
        encoding="utf-8",
    )
    _, d_payload = run(root, "typescript", "definitions", "reconcile")
    _, r_payload = run(root, "typescript", "references", "reconcile")
    _, o_payload = run(root, "typescript", "outline", "reconcile")
    for payload in (d_payload, r_payload, o_payload):
        require(payload["semantic"] is True and payload["confidence"] == "medium",
                "bounded TypeScript result inflates or omits confidence")
    require([(item["kind"], item["line"]) for item in d_payload["results"]]
            == [("definition", 1)], "TypeScript definition is inaccurate")
    require([(item["kind"], item["line"]) for item in r_payload["results"]]
            == [("reference", 6)], "TypeScript references include strings/comments or miss the call")
    symbols = {item["symbol"] for item in o_payload["results"]}
    require({"reconcile", "decoy", "result"} <= symbols,
            "TypeScript outline omits covered declarations")
    require("nested" not in symbols,
            "TypeScript top-level outline leaked a nested declaration")
    require(len({json.dumps(payload["results"], sort_keys=True)
                 for payload in (d_payload, r_payload, o_payload)}) == 3,
            "TypeScript operations are not distinct")


def validate_fallbacks(base: pathlib.Path) -> int:
    guards = 0
    text_root = base / "text"
    text_root.mkdir()
    (text_root / "notes.txt").write_text("call reconcile here\n", encoding="utf-8")
    (text_root / "oversize.txt").write_bytes(b"x" * 1_000_001)
    result, payload = run(text_root, "text", "references", "reconcile")
    require(result.returncode == 0 and payload["semantic"] is False
            and payload["confidence"] == "textual"
            and payload["results"][0]["kind"] == "textual-match",
            "unsupported-language fallback masquerades as semantic")
    require("oversize-skipped:oversize.txt" in payload["warnings"],
            "textual fallback hid a bounded-corpus warning")
    guards += 1

    bad_py = base / "bad-python"
    bad_py.mkdir()
    (bad_py / "broken.py").write_text("def reconcile(:\n", encoding="utf-8")
    _, payload = run(bad_py, "python", "definitions", "reconcile")
    require(payload["semantic"] is False and payload["confidence"] == "textual"
            and "parse-or-read-failure-textual-fallback" in payload["warnings"],
            "unparseable Python did not fail over honestly")
    guards += 1

    bad_ts = base / "bad-typescript"
    bad_ts.mkdir()
    (bad_ts / "broken.ts").write_text(
        "function reconcile(value: string) {\n", encoding="utf-8")
    _, payload = run(bad_ts, "typescript", "definitions", "reconcile")
    require(payload["semantic"] is False and payload["confidence"] == "textual"
            and "parse-or-read-failure-textual-fallback" in payload["warnings"],
            "unparseable TypeScript did not fail over honestly")
    guards += 1

    invalid_utf8 = base / "invalid-utf8"
    invalid_utf8.mkdir()
    (invalid_utf8 / "valid.py").write_text(
        "def reconcile():\n    return True\n", encoding="utf-8")
    (invalid_utf8 / "invalid.py").write_bytes(b"\xff\xfe\x00")
    _, payload = run(invalid_utf8, "python", "definitions", "reconcile")
    require(payload["semantic"] is False and payload["confidence"] == "textual"
            and any(warning == "invalid-utf8:invalid.py"
                    for warning in payload["warnings"]),
            "invalid UTF-8 was silently omitted from semantic coverage")
    guards += 1
    return guards


def validate_boundaries(base: pathlib.Path) -> int:
    guards = 0
    root = base / "bounded"
    outside = base / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "inside.py").write_text("result = reconcile('inside')\n", encoding="utf-8")
    (outside / "secret.py").write_text("result = reconcile('outside')\n", encoding="utf-8")
    link = root / "escape.py"
    try:
        link.symlink_to(outside / "secret.py")
    except (OSError, NotImplementedError):
        link = None
    before = tree_snapshot(base)
    first, payload = run(root, "python", "references", "reconcile")
    second, repeated = run(root, "python", "references", "reconcile")
    require(first.returncode == second.returncode == 0 and payload == repeated,
            "provider output is not deterministic")
    require({item["path"] for item in payload["results"]} == {"inside.py"},
            "provider followed a symlink or read outside root")
    require(tree_snapshot(base) == before, "provider mutated its input tree")
    guards += 3

    root_link = base / "root-link"
    try:
        root_link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        root_link = None
    if root_link is not None:
        linked, _ = run(root_link, "python", "references", "reconcile")
        require(linked.returncode != 0,
                "symlink supplied as the declared root was accepted")
        guards += 1

    spec = importlib.util.spec_from_file_location("itd_semantic_navigation_test", PROVIDER)
    require(spec is not None and spec.loader is not None,
            "provider could not be loaded for descriptor race checks")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    race_root = base / "race"
    race_root.mkdir()
    race_outside = outside / "race.py"
    race_outside.write_text("secret = reconcile('outside')\n", encoding="utf-8")
    race_file = race_root / "candidate.py"
    race_file.write_text("safe = True\n", encoding="utf-8")
    original_open = module.os.open
    replaced = False

    def replace_before_open(path, flags):
        nonlocal replaced
        if pathlib.Path(path) == race_file and not replaced:
            race_file.unlink()
            race_file.symlink_to(race_outside)
            replaced = True
        return original_open(path, flags)

    module.os.open = replace_before_open
    try:
        text, warning = module.read_atomic(race_file, race_root)
    finally:
        module.os.open = original_open
    require(text is None and warning and warning.startswith("unreadable:"),
            "regular-file-to-symlink replacement before open escaped no-follow")
    guards += 1

    race_file.unlink()
    race_file.write_text("safe = True\n", encoding="utf-8")
    original_fstat = module.os.fstat
    replaced = False

    def replace_after_open(descriptor):
        nonlocal replaced
        opened = original_fstat(descriptor)
        if not replaced:
            race_file.unlink()
            race_file.symlink_to(race_outside)
            replaced = True
        return opened

    module.os.fstat = replace_after_open
    try:
        text, warning = module.read_atomic(race_file, race_root)
    finally:
        module.os.fstat = original_fstat
    require(text is None and warning and warning.startswith("containment-race:"),
            "regular-file-to-symlink replacement after open escaped inode validation")
    guards += 1

    missing = subprocess.run(
        [sys.executable, str(PROVIDER), "--root", str(base / "missing"),
         "--language", "python", "--operation", "references", "--symbol", "x"],
        cwd=ROOT, text=True, capture_output=True, timeout=10, check=False,
    )
    require(missing.returncode != 0 and "UNVERIFIED" in missing.stderr,
            "missing root did not fail closed")
    guards += 1

    invalid, _ = run(root, "python", "references", "../escape")
    require(invalid.returncode != 0, "invalid semantic identifier was accepted")
    guards += 1

    capped = base / "capped"
    capped.mkdir()
    content = "\n".join(
        [f"value_{number} = {number}" for number in range(600)]
        + ["target = 1"]
    ) + "\n"
    (capped / "many.py").write_text(content, encoding="utf-8")
    _, payload = run(capped, "python", "outline", "target")
    require(len(payload["results"]) == 500
            and payload["results"][0]["symbol"] == "target"
            and "result-limit" in payload["warnings"],
            "result accumulation is not capped while preserving the query symbol")
    guards += 1

    corpus = base / "corpus"
    corpus.mkdir()
    for number in range(5_001):
        (corpus / f"{number:04d}.py").touch()
    _, payload = run(corpus, "python", "outline", "target")
    require("corpus-file-limit:5000" in payload["warnings"],
            "corpus traversal has no observable file budget")
    guards += 1

    entries = base / "entries"
    entries.mkdir()
    for number in range(6_001):
        (entries / f"{number:04d}.txt").touch()
    _, payload = run(entries, "python", "outline", "target")
    require("corpus-entry-limit:6000" in payload["warnings"],
            "nonmatching filesystem entries bypass the traversal budget")
    guards += 1
    return guards


def validate_real_pilot_demand() -> int:
    demand = json.loads(DEMAND.read_text(encoding="utf-8"))
    index = json.loads(PILOT_INDEX.read_text(encoding="utf-8"))
    pilots = {row["episode"]: row for row in index["episodes"]}
    checks = 0
    for observation in demand["observations"]:
        pilot = pilots[observation["episode"]]
        root = pathlib.Path(pilot["worktreeRoot"]).resolve()
        require(root.is_dir(), f"pilot {observation['episode']} worktree is missing")
        for operation in observation["operations"]:
            result, payload = run(root, observation["language"], operation,
                                  observation["symbol"])
            require(result.returncode == 0 and payload.get("semantic") is True,
                    f"pilot {observation['episode']} {operation} is not semantic")
            require(payload.get("results"),
                    f"pilot {observation['episode']} {operation} found no results")
            expected_kind = {
                "definitions": "definition",
                "references": "reference",
                "outline": "symbol",
            }[operation]
            require(any(item.get("kind") == expected_kind
                        and item.get("symbol") == observation["symbol"]
                        for item in payload["results"]),
                    f"pilot {observation['episode']} {operation} misses the demanded symbol")
            checks += 1
    return checks


def main() -> int:
    try:
        require(PROVIDER.is_file(), "semantic-navigation provider is missing")
        validate_registry()
        with tempfile.TemporaryDirectory(prefix="itd-semantic-navigation-") as raw:
            base = pathlib.Path(raw)
            python_root = base / "python"
            typescript_root = base / "typescript"
            python_root.mkdir()
            typescript_root.mkdir()
            validate_python(python_root)
            validate_typescript(typescript_root)
            guards = validate_fallbacks(base) + validate_boundaries(base)
        pilot_checks = validate_real_pilot_demand()
    except (Failure, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAILED", "why": str(exc),
                          "fix": "Repair the provider or registry without weakening honest fallback labels."},
                         sort_keys=True))
        return 1
    print(json.dumps({
        "status": "PASSED",
        "languages": ["python", "typescript"],
        "operations": ["definitions", "references", "outline"],
        "fallback": "semantic:false",
        "boundaryGuards": guards,
        "realPilotChecks": pilot_checks,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
