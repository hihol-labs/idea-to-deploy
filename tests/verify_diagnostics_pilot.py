#!/usr/bin/env python3
"""Fail-closed validation for diagnostic observations, labels, and results."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import pathlib
import statistics
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
PILOT = ROOT / "docs" / "diagnostics-pilot"
RUNNER = ROOT / "skills" / "_shared" / "itd_incremental_diagnostics.py"
COLLECTOR = ROOT / "skills" / "_shared" / "itd_diagnostics_pilot.py"
COLLECTOR_OBSERVATION_TREE = "419bfbd378c1983383704c4fe7a71c5ee07cb9f1"
COLLECTOR_RELATIVE_PATH = "skills/_shared/itd_diagnostics_pilot.py"
OBSERVATIONS_SHA256 = (
    "58ed3a534c0e47cbe76e8b3ea16d83c8f62803834d3fac681235db9d550f23f1"
)
REFERENCED_DIGEST = "58ed3a…f23f1"
DECISION_TEXT = (
    "Одобряю HDX-007 labels: все 30 known-broken-sentinel emissions являются "
    "actionable для observations SHA-256 58ed3a…f23f1."
)
ATTESTATION_BOUNDARY = {
    "source": "explicit-user-message-in-current-session",
    "assurance": "honest-host-orchestrator",
    "cryptographicAttestation": False,
}
PROBE_SOURCE = (
    "import pathlib,sys\n"
    "value=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
    "if 'BROKEN' in value:\n"
    "    print('known-broken-sentinel')\n"
    "    raise SystemExit(1)\n"
    "raise SystemExit(0)\n"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observation_collector_sha256() -> str:
    completed = subprocess.run(
        ["git", "show",
         f"{COLLECTOR_OBSERVATION_TREE}:{COLLECTOR_RELATIVE_PATH}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    require(completed.returncode == 0,
            "saved observation-time collector tree is unavailable")
    return hashlib.sha256(completed.stdout).hexdigest()


def validate_collector_write_safety() -> None:
    spec = importlib.util.spec_from_file_location(
        "_itd_diagnostics_pilot_safety", COLLECTOR)
    require(spec is not None and spec.loader is not None,
            "active collector cannot be loaded for write-safety validation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="itd-collector-write-") as raw:
        directory = pathlib.Path(raw)
        destination = directory / "observations.json"
        legacy_temporary = directory / "observations.json.tmp"
        victim = directory / "victim.txt"
        victim.write_text("untouched", encoding="utf-8")
        symlink_supported = True
        try:
            legacy_temporary.symlink_to(victim)
        except OSError:
            symlink_supported = False
            legacy_temporary.write_text("legacy", encoding="utf-8")
        module.write_json_atomic(destination, {"status": "safe"})
        require(load(destination) == {"status": "safe"},
                "active collector did not publish the intended JSON")
        require(
            (victim.read_text(encoding="utf-8") == "untouched"
             if symlink_supported else
             legacy_temporary.read_text(encoding="utf-8") == "legacy"),
            "active collector followed or overwrote the predictable legacy temp",
        )
        require(not list(directory.glob(".observations.json.*.tmp")),
                "active collector left an exclusive temporary file behind")


def validate_observations() -> tuple[dict, dict]:
    observations_path = PILOT / "OBSERVATIONS.json"
    packet_path = PILOT / "LABEL_PACKET.json"
    observations = load(observations_path)
    packet = load(packet_path)
    require(observations.get("status") == "awaiting-human-labels"
            and observations.get("externalAdoptionEvidence") is False
            and observations.get("measurement") == "host-observed",
            "observation authority/measurement boundary is invalid")
    require(observations.get("baseline") ==
            "same project checks without incremental diagnostics"
            and observations.get("treatment") ==
            "same project checks with the opt-in incremental profile",
            "frozen A/B arms drifted")
    require((observations.get("environment") or {}).get("runnerSha256") ==
            sha256(RUNNER), "observation runner provenance is stale")
    validate_collector_write_safety()
    runs = observations.get("labeledRuns") or []
    baseline = [row for row in runs if row.get("arm") == "baseline"]
    treatment = [row for row in runs if row.get("arm") == "treatment"]
    require(len(baseline) == len(treatment) >= 30,
            "at least 30 paired runs per arm are required")
    baseline_ids = {row.get("pairId") for row in baseline}
    treatment_ids = {row.get("pairId") for row in treatment}
    require(None not in baseline_ids and baseline_ids == treatment_ids
            and len(baseline_ids) == len(baseline),
            "pair ids must be unique and one-to-one")
    require(all(isinstance(row.get("latencyMs"), int) and row["latencyMs"] >= 0
                and row.get("completionEvidence") is False for row in runs),
            "latency must be host-observed and non-acceptance")
    emissions = [row["emissions"][0] for row in treatment]
    require(len(emissions) >= 30
            and all(row.get("diagnosticId") == "known-broken-sentinel"
                    and row.get("exitCode") == 1
                    and row.get("humanLabel") is None
                    for row in emissions),
            "pre-decision emissions must remain explicitly unlabeled")
    require(packet.get("status") in {"awaiting-human-decision", "approved"}
            and packet.get("observationsSha256") == sha256(observations_path)
            and packet.get("emissionIds") == [row["id"] for row in emissions],
            "label packet is stale or prefilled")
    if packet["status"] == "awaiting-human-decision":
        require(packet.get("decision") is None,
                "pending packet cannot contain a decision")
    else:
        require(isinstance(packet.get("decision"), dict),
                "approved packet must contain the human decision")
    return observations, packet


def validate_labels() -> tuple[dict, dict]:
    observations, packet = validate_observations()
    decision = packet.get("decision")
    require(packet.get("status") == "approved"
            and isinstance(decision, dict)
            and set(decision) == {
                "actor",
                "recordedAt",
                "decisionText",
                "referencedDigest",
                "observationsSha256",
                "attestationBoundary",
                "labels",
            }
            and decision.get("actor") == "human"
            and decision.get("decisionText") == DECISION_TEXT
            and decision.get("referencedDigest") == REFERENCED_DIGEST
            and decision.get("observationsSha256") == OBSERVATIONS_SHA256
            and packet["observationsSha256"] == OBSERVATIONS_SHA256
            and decision.get("attestationBoundary") == ATTESTATION_BOUNDARY
            and isinstance(decision.get("recordedAt"), str)
            and decision["recordedAt"].strip(),
            "exact user decision or its honest-host attestation boundary drifted")
    labels = decision.get("labels")
    require(isinstance(labels, dict)
            and set(labels) == set(packet["emissionIds"])
            and all(value in {"actionable", "nonactionable"}
                    for value in labels.values()),
            "human labels must cover every exact emission id")
    provenance = packet.get("probeProvenance") or {}
    require(provenance == {
        "observationsSha256": packet["observationsSha256"],
        "probeVersion": "deterministic-known-broken-sentinel-v1",
        "probeSourceSha256": hashlib.sha256(
            PROBE_SOURCE.encode("utf-8")).hexdigest(),
        "collectorObservationTree": COLLECTOR_OBSERVATION_TREE,
        "collectorPath": COLLECTOR_RELATIVE_PATH,
        "collectorSha256": observation_collector_sha256(),
        "activeCollectorSha256": sha256(COLLECTOR),
        "activeCollectorRepair": "exclusive-same-directory-temp-fsync-replace",
    }, "probe/collector provenance is not exact or observation-bound")
    return observations, packet


def validate_results() -> dict:
    observations, packet = validate_labels()
    results = load(PILOT / "RESULTS.json")
    require(results.get("sourceObservationsSha256") ==
            packet["observationsSha256"]
            and results.get("humanDecision") == packet["decision"],
            "RESULTS is not bound to the human-labeled observations")
    expected = copy.deepcopy(observations)
    expected["status"] = "passed-default-off"
    expected["sourceObservationsSha256"] = packet["observationsSha256"]
    expected["labelPacketSha256"] = sha256(PILOT / "LABEL_PACKET.json")
    expected["probeProvenance"] = packet["probeProvenance"]
    expected["humanDecision"] = packet["decision"]
    labels = packet["decision"]["labels"]
    for row in expected["labeledRuns"]:
        if row["arm"] == "treatment":
            for emission in row["emissions"]:
                emission["humanLabel"] = labels[emission["id"]]
    runs = results.get("labeledRuns") or []
    treatment = [row for row in runs if row.get("arm") == "treatment"]
    emissions = [
        emission for row in treatment for emission in (row.get("emissions") or [])
    ]
    require(len(treatment) >= 30 and len(emissions) >= 30
            and all(row.get("humanLabel") in {"actionable", "nonactionable"}
                    for row in emissions),
            "RESULTS lacks complete labels")
    latencies = sorted(row["latencyMs"] for row in treatment)
    median = statistics.median(latencies)
    p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
    noise = sum(row["humanLabel"] == "nonactionable" for row in emissions) / len(emissions)
    expected["decisionMetrics"] = {
        "medianLatencyMs": median,
        "p95LatencyMs": p95,
        "falseNoiseRatio": noise,
        "thresholds": {
            "medianLatencyMsMax": 2000,
            "p95LatencyMsMax": 5000,
            "falseNoiseRatioMax": 0.1,
        },
        "decision": "thresholds-passed-profile-remains-default-off",
    }
    require(results == expected,
            "RESULTS must be the exact label-only projection of OBSERVATIONS")
    require(median <= 2000 and p95 <= 5000 and noise <= 0.1,
            "frozen latency/noise thresholds failed")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("observations", "labels", "results"),
                        required=True)
    args = parser.parse_args()
    try:
        if args.phase == "observations":
            observations, packet = validate_observations()
            runs = observations["labeledRuns"]
            result = {
                "status": "PASSED",
                "pairs": len(runs) // 2,
                "emissions": len([r for r in runs if r["arm"] == "treatment"]),
                "labels": packet["status"],
            }
        elif args.phase == "labels":
            _, packet = validate_labels()
            result = {
                "status": "PASSED",
                "labels": len(packet["decision"]["labels"]),
            }
        else:
            results = validate_results()
            result = {"status": "PASSED", "runs": len(results["labeledRuns"])}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        print(json.dumps({
            "status": "FAILED",
            "why": str(exc),
            "fix": "collect or label the exact missing evidence; do not synthesize it",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
