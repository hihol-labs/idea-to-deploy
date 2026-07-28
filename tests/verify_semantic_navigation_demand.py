#!/usr/bin/env python3
"""Fail-closed oracle for the real-pilot semantic-navigation demand gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMAND = ROOT / "docs" / "semantic-navigation" / "DEMAND.json"
INDEX = ROOT / "docs" / "harness-demo-pilots" / "INDEX.json"
REGISTRY = ROOT / "docs" / "templates" / "itd" / "TOOL_CAPABILITY_REGISTRY.json"
PILOT_ORACLE = ROOT / "tests" / "verify_harness_demo_pilots.py"
PORTABLE_ORACLE = ROOT / "tests" / "verify_harness_demo_portable.py"


class DemandError(AssertionError):
    """Deterministic demand-gate failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DemandError(message)


def load(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    require(result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def registry_navigation(registry: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row for row in registry.get("tools", [])
        if isinstance(row, dict) and row.get("id") == "semantic-navigation"
    ]
    require(len(rows) == 1, "registry must contain exactly one semantic-navigation row")
    return rows[0]


def validate(
    demand: dict[str, Any],
    index: dict[str, Any],
    registry: dict[str, Any],
    *,
    check_files: bool,
    portable_sources: dict[str, dict[str, str]] | None = None,
) -> None:
    require(
        demand.get("version") == 1
        and demand.get("kind") == "semantic-navigation-demand-decision",
        "demand artifact version/kind drifted",
    )
    source = demand.get("source") or {}
    require(
        source.get("path") == "docs/harness-demo-pilots/INDEX.json"
        and source.get("sha256") == sha256(INDEX),
        "demand source is not bound to the exact pilot index",
    )
    thresholds = demand.get("thresholds") or {}
    required_languages = thresholds.get("requiredLanguages")
    required_operations = thresholds.get("requiredOperations")
    require(
        thresholds.get("minimumVerifiedPilots") == 3
        and required_languages == ["python", "typescript"]
        and thresholds.get("minimumTasksPerRequiredLanguage") == 1
        and required_operations == ["definitions", "references", "outline"],
        "demand thresholds were weakened or reordered",
    )

    rows = {
        row.get("episode"): row
        for row in index.get("episodes", [])
        if isinstance(row, dict)
    }
    observations = demand.get("observations")
    require(
        isinstance(observations, list)
        and len(observations) == 3
        and [row.get("episode") for row in observations] == ["A", "B", "C"]
        and source.get("episodes") == ["A", "B", "C"],
        "demand must use the exact three serial pilot episodes",
    )

    tasks_by_language: dict[str, list[str]] = {
        language: [] for language in required_languages
    }
    for observation in observations:
        episode = observation.get("episode")
        pilot = rows.get(episode)
        require(isinstance(pilot, dict), f"pilot {episode} is missing")
        require(
            pilot.get("status") == "passed"
            and pilot.get("externalAdoptionEvidence") is False
            and observation.get("unitId") == pilot.get("unitId")
            and observation.get("candidateTree") == pilot.get("candidateTree")
            and observation.get("adjudicationReceipt")
            == pilot.get("adjudicationReceipt"),
            f"observation {episode} is not bound to its verified pilot",
        )
        language = observation.get("language")
        require(language in required_languages, f"unsupported language in {episode}")
        paths = observation.get("paths")
        require(
            isinstance(paths, list)
            and paths
            and set(paths) <= set(pilot.get("allowedPaths") or []),
            f"observation {episode} paths escape its exact pilot scope",
        )
        require(
            observation.get("operations") == required_operations,
            f"observation {episode} lacks required navigation operations",
        )
        symbol = observation.get("symbol")
        require(isinstance(symbol, str) and symbol.isidentifier(),
                f"observation {episode} symbol is malformed")
        tasks_by_language[language].append(episode)
        if check_files:
            worktree = pathlib.Path(str(pilot.get("worktreeRoot") or "")).resolve()
            require(
                git(worktree, "write-tree") == pilot.get("candidateTree"),
                f"pilot {episode} worktree no longer has the indexed tree",
            )
            occurrences = sum(
                (worktree / path).read_text(encoding="utf-8", errors="replace").count(symbol)
                for path in paths
            )
            require(
                occurrences >= 2,
                f"pilot {episode} does not contain definition/reference evidence for {symbol}",
            )
        elif portable_sources is not None:
            texts = portable_sources.get(str(observation.get("unitId"))) or {}
            require(set(texts) == set(paths),
                    f"portable source set for pilot {episode} is incomplete")
            occurrences = sum(texts[path].count(symbol) for path in paths)
            require(
                occurrences >= 2,
                f"portable pilot {episode} lacks definition/reference evidence for {symbol}",
            )

    activated = (
        len(observations) >= thresholds["minimumVerifiedPilots"]
        and all(
            len(tasks_by_language[language])
            >= thresholds["minimumTasksPerRequiredLanguage"]
            for language in required_languages
        )
    )
    expected_status = "activated" if activated else "not_activated"
    aggregate = demand.get("aggregate") or {}
    require(
        aggregate.get("verifiedPilots") == len(observations)
        and aggregate.get("languages") == required_languages
        and aggregate.get("tasksByLanguage") == tasks_by_language,
        "demand aggregate is not derived from observations",
    )
    decision = demand.get("decision") or {}
    require(
        decision.get("status") == expected_status
        and decision.get("implementationUnit") == "HDX-013"
        and decision.get("externalAdoptionEvidence") is False
        and decision.get("completionEvidence") is False,
        "demand decision does not follow the deterministic threshold",
    )

    navigation = registry_navigation(registry)
    gate = navigation.get("demandGate") or {}
    require(
        gate.get("status") == expected_status
        and gate.get("evidence") == "docs/semantic-navigation/DEMAND.json"
        and gate.get("evidenceSha256") == sha256(DEMAND),
        "tool registry demand gate is not bound to the decision artifact",
    )
    semantic = navigation.get("semanticNavigation")
    if semantic not in ({}, None):
        require(
            expected_status == "activated"
            and isinstance(semantic, dict)
            and semantic.get("provider") == "skills/_shared/itd_semantic_navigation.py"
            and semantic.get("languages") == required_languages
            and semantic.get("operations") == required_operations,
            "provider declaration is not downstream of the activated demand gate",
        )
        if check_files:
            provider = ROOT / semantic["provider"]
            require(provider.is_file(),
                    "activated provider declaration points to a missing file")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portable", action="store_true")
    args = parser.parse_args(argv)
    demand, index, registry = load(DEMAND), load(INDEX), load(REGISTRY)
    oracle = PORTABLE_ORACLE if args.portable else PILOT_ORACLE
    pilot = subprocess.run(
        [sys.executable, str(oracle)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    require(pilot.returncode == 0, f"pilot provenance failed: {pilot.stdout}{pilot.stderr}")
    check_files = not args.portable
    portable_sources = None
    if args.portable:
        spec = importlib.util.spec_from_file_location(
            "portable_semantic_sources", PORTABLE_ORACLE)
        require(spec is not None and spec.loader is not None,
                "portable semantic source verifier cannot be imported")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        portable_sources = module.verified_semantic_sources()
    validate(demand, index, registry, check_files=check_files,
             portable_sources=portable_sources)

    mutations: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    forged = copy.deepcopy(demand)
    forged["source"]["sha256"] = "0" * 64
    mutations.append(("index hash", forged, registry))
    forged = copy.deepcopy(demand)
    forged["decision"]["status"] = "unknown"
    mutations.append(("decision enum", forged, registry))
    forged = copy.deepcopy(demand)
    forged["observations"].pop()
    mutations.append(("pilot count", forged, registry))
    forged = copy.deepcopy(demand)
    forged["observations"][2]["language"] = "python"
    mutations.append(("language demand", forged, registry))
    forged = copy.deepcopy(demand)
    forged["observations"][0]["operations"].remove("references")
    mutations.append(("operation demand", forged, registry))
    forged = copy.deepcopy(demand)
    forged["decision"]["externalAdoptionEvidence"] = True
    mutations.append(("external adoption", forged, registry))
    forged_registry = copy.deepcopy(registry)
    registry_navigation(forged_registry)["demandGate"]["status"] = "not_activated"
    mutations.append(("registry decision", demand, forged_registry))
    forged = copy.deepcopy(demand)
    forged["observations"][1]["symbol"] = "missing_symbol"
    mutations.append(("symbol provenance", forged, registry))

    guards = 0
    for label, demand_value, registry_value in mutations:
        try:
            validate(demand_value, index, registry_value, check_files=check_files,
                     portable_sources=portable_sources)
        except DemandError:
            guards += 1
        else:
            raise DemandError(f"mutation guard failed: {label}")
    print(json.dumps({
        "status": "PASSED",
        "decision": demand["decision"]["status"],
        "verifiedPilots": demand["aggregate"]["verifiedPilots"],
        "languages": demand["aggregate"]["languages"],
        "mutationGuards": guards,
        "externalAdoptionEvidence": False,
        "provenanceMode": "portable" if args.portable else "live",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DemandError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAILED", "why": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
