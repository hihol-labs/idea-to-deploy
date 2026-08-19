#!/usr/bin/env python3
"""Build or check the declared impact map ``.itd/IMPACT_GRAPH.json`` (LPD-002 R6).

The map is DATA in the repository: ``source path -> suites that exercise it``.
It is fed to ``impact_closure`` (skills/_shared/itd_verification_profiles.py)
as ``impactGraph`` so a point change selects a proportional subset of
``tests/verify_*.py`` instead of the full run. This script derives the
``generated`` section mechanically from the tracked tree; the ``declared``
section is hand-maintained and preserved across rebuilds.

Edge rule (direct, one hop, no source-to-source transitivity — measured on
2026-08-19: transitive stem-matching saturated 148/151 suites per node, i.e.
destroyed proportionality): a suite owns a tracked file when its text contains
the file's repository-relative path, a ``"a" / "b" / "c"`` Path concatenation
that resolves to it, a Python ``import``/``from … import`` that resolves to a
tracked module, or — for code/JSON files whose basename is unique in the
tree — the basename (and, for ``.py``, the module stem of >= 8 characters).

  python3 tests/build_impact_graph.py           # rewrite .itd/IMPACT_GRAPH.json
  python3 tests/build_impact_graph.py --check   # exit 1 when the file drifted

Completeness and proportionality are NOT judged here; that is the
``impact-audit`` operation of the engine, exercised by
tests/verify_verification_profiles.py. This script only keeps the data fresh.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / ".itd" / "IMPACT_GRAPH.json"
SUITE_GLOB = "tests/verify_*.py"
OWNED_GLOBS = ["skills/_shared/*.py", "hooks/*.sh"]
SUITE_RE = re.compile(r"tests/verify_[\w\-]+\.py")
CODE_SUFFIXES = (".py", ".sh", ".ps1")
BASENAME_SUFFIXES = CODE_SUFFIXES + (".json",)
GENERIC_BASENAMES = {"__init__.py", "__main__.py", "index.json", "package.json"}
CONCAT_RE = re.compile(r'((?:"[\w.\-]+"\s*/\s*)+"[\w.\-]+")')
IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\s+([\w.,\s]+?)\s*(?:#.*)?$|import\s+([\w.]+))",
    re.MULTILINE)
SEGMENT_RE = re.compile(r'"([\w.\-]+)"')
MIN_STEM = 8


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(root), capture_output=True, check=True)
    files = [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]
    return sorted(files)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def references(text: str, tracked: list[str], tracked_set: set[str],
               by_basename: dict[str, list[str]]) -> set[str]:
    found: set[str] = set()
    for rel in tracked:
        if rel in text:
            found.add(rel)
    for match in CONCAT_RE.finditer(text):
        joined = "/".join(SEGMENT_RE.findall(match.group(1)))
        if joined in tracked_set:
            found.add(joined)
            continue
        suffix = "/" + joined
        for rel in tracked:
            if rel.endswith(suffix):
                found.add(rel)
    for match in IMPORT_RE.finditer(text):
        package, names, module = match.groups()
        candidates: list[str] = []
        if module:
            candidates.append(module.replace(".", "/"))
        if package:
            base = package.replace(".", "/")
            candidates.append(base)
            for name in re.split(r"[\s,]+", names or ""):
                if name and name != "as":
                    candidates.append(base + "/" + name)
        for candidate in candidates:
            for rel in (candidate + ".py", candidate + "/__init__.py"):
                if rel in tracked_set:
                    found.add(rel)
    for basename, owners in by_basename.items():
        if len(owners) != 1 or basename in GENERIC_BASENAMES:
            continue
        rel = owners[0]
        if not rel.endswith(BASENAME_SUFFIXES):
            continue
        if basename in text:
            found.add(rel)
            continue
        if rel.endswith(".py"):
            stem = basename[:-3]
            if len(stem) >= MIN_STEM and re.search(
                    r"(?<![\w])" + re.escape(stem) + r"(?![\w])", text):
                found.add(rel)
    return found


def build_generated(root: Path) -> dict[str, list[str]]:
    tracked = tracked_files(root)
    tracked_set = set(tracked)
    suites = [rel for rel in tracked if SUITE_RE.fullmatch(rel)]
    by_basename: dict[str, list[str]] = defaultdict(list)
    for rel in tracked:
        by_basename[os.path.basename(rel)].append(rel)
    graph: dict[str, set[str]] = defaultdict(set)
    for suite in suites:
        text = read_text(root / suite)
        for rel in references(text, tracked, tracked_set, by_basename):
            if rel != suite:
                graph[rel].add(suite)
    return {source: sorted(targets) for source, targets in sorted(graph.items())}


def load_existing(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render(existing: dict, generated: dict[str, list[str]]) -> dict:
    return {
        "schemaVersion": "1",
        "purpose": (
            "Declared impact map of this repository: tracked source path -> the "
            "tests/verify_*.py suites that exercise it. Fed to impact_closure "
            "(skills/_shared/itd_verification_profiles.py) as impactGraph so a "
            "point change runs a proportional subset instead of the full set. "
            "Completeness and proportionality are audited by the engine's "
            "impact-audit operation (tests/verify_verification_profiles.py)."),
        "generator": "tests/build_impact_graph.py",
        "universe": {"suites": SUITE_GLOB, "owned": list(OWNED_GLOBS)},
        "declared": existing.get("declared") or {},
        "generated": generated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit 1 when the committed map drifted")
    parser.add_argument("--path", type=Path, default=MAP_PATH)
    args = parser.parse_args(argv)
    generated = build_generated(ROOT)
    existing = load_existing(args.path)
    document = render(existing, generated)
    suites_attached = {target for targets in generated.values() for target in targets}
    summary = (f"nodes={len(generated)} edges={sum(len(v) for v in generated.values())} "
               f"suitesAttached={len(suites_attached)}")
    if args.check:
        if existing.get("generated") != generated or existing.get("universe") != document["universe"]:
            stale = sorted(set(existing.get("generated") or {}) ^ set(generated))
            print(f"DRIFT {args.path.relative_to(ROOT)} {summary}")
            print(f"FIX: python3 tests/build_impact_graph.py  (changed nodes: {stale[:12]})")
            return 1
        print(f"FRESH {args.path.relative_to(ROOT)} {summary}")
        return 0
    args.path.parent.mkdir(parents=True, exist_ok=True)
    args.path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8")
    print(f"WROTE {args.path.relative_to(ROOT)} {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
