#!/usr/bin/env python3
"""Evidence-backed, human-gated learning proposal/experiment ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ALLOWED_EXTERNAL_TYPES = {
    "production_failure",
    "review_finding",
    "false_positive",
    "skill_bypass",
    "observed_cost",
}
DECISIONS = {"keep", "change", "rollback"}


def fail(what: str, why: str, fix: str, code: int = 2) -> int:
    print(f"FAILED: {what} | WHY: {why} | FIX: {fix}")
    return code


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc


def load_signals(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {number} is not an object")
            rows.append(value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid signal ledger {path}: {exc}") from exc
    return rows


def source_key(signal: dict) -> str:
    project = str(signal.get("project") or "")
    session = str(signal.get("session") or signal.get("reviewId") or "")
    return f"{project}::{session}"


def validate_signal(signal: dict) -> str | None:
    for field in ("id", "class", "type", "evidence"):
        if not str(signal.get(field) or "").strip():
            return f"missing {field}"
    if signal.get("type") not in ALLOWED_EXTERNAL_TYPES:
        return f"non-external type {signal.get('type')!r}"
    if source_key(signal) == "::":
        return "missing project/session/review source identity"
    return None


def stable_proposal_id(signal_class: str) -> str:
    digest = hashlib.sha256(signal_class.encode("utf-8")).hexdigest()[:12]
    return f"LP-{digest}"


def validate_spec(spec: dict) -> str | None:
    for field in ("target", "hypothesis", "metric", "direction", "rollbackPlan"):
        if not str(spec.get(field) or "").strip():
            return f"missing proposal spec field {field}"
    if spec.get("direction") not in {"higher", "lower"}:
        return "direction must be higher or lower"
    threshold = spec.get("maxRegressionPercent")
    if not isinstance(threshold, (int, float)) or threshold < 0:
        return "maxRegressionPercent must be a non-negative number"
    for field in ("baselineCommand", "candidateCommand"):
        command = spec.get(field)
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            return f"{field} must be a non-empty argv string array"
    return None


def propose(signals_path: Path, specs_path: Path, out: Path, minimum: int) -> int:
    try:
        signals = load_signals(signals_path)
        specs = load_json(specs_path)
    except ValueError as exc:
        return fail("proposal input", str(exc), "repair the durable signal/spec JSON and retry")
    if not isinstance(specs, dict):
        return fail("proposal spec", "top level is not an object",
                    "map each signal class to an explicit proposal/experiment spec")

    valid: list[dict] = []
    rejected: list[dict] = []
    seen_ids: set[str] = set()
    for signal in signals:
        issue = validate_signal(signal)
        sid = str(signal.get("id") or "")
        if sid in seen_ids:
            issue = "duplicate signal id"
        seen_ids.add(sid)
        if issue:
            rejected.append({"id": sid, "reason": issue})
        else:
            valid.append(signal)

    groups: dict[str, list[dict]] = {}
    for signal in valid:
        groups.setdefault(str(signal["class"]), []).append(signal)

    proposals: list[dict] = []
    for signal_class, rows in sorted(groups.items()):
        distinct_sources = {source_key(row) for row in rows}
        if len(rows) < minimum or len(distinct_sources) < minimum:
            continue
        spec = specs.get(signal_class)
        if not isinstance(spec, dict):
            rejected.append({"class": signal_class, "reason": "repeated class has no proposal spec"})
            continue
        issue = validate_spec(spec)
        if issue:
            rejected.append({"class": signal_class, "reason": issue})
            continue
        proposals.append({
            "id": stable_proposal_id(signal_class),
            "signalClass": signal_class,
            "occurrences": len(rows),
            "distinctSources": len(distinct_sources),
            "evidence": [{
                "id": row["id"],
                "type": row["type"],
                "source": source_key(row),
                "evidence": row["evidence"],
            } for row in rows],
            "proposal": {
                "target": spec["target"],
                "hypothesis": spec["hypothesis"],
                "status": "proposed",
            },
            "experiment": {
                "metric": spec["metric"],
                "direction": spec["direction"],
                "maxRegressionPercent": spec["maxRegressionPercent"],
                "baselineCommand": spec["baselineCommand"],
                "candidateCommand": spec["candidateCommand"],
                "rollbackPlan": spec["rollbackPlan"],
                "status": "planned",
            },
            "humanDecision": {"decision": "pending", "actor": "", "reason": "", "at": ""},
            "verification": {"status": "pending", "at": "", "evidence": ""},
        })

    if not proposals:
        return fail(
            "learning promotion",
            f"no eligible repeated external class from distinct sources (minimum {minimum}); rejected={rejected}",
            "collect another durable external signal or add a complete human-authored proposal spec; never promote an internal metric",
            1,
        )
    artifact = {
        "version": 1,
        "generatedAt": now_iso(),
        "sourceLedger": str(signals_path),
        "status": "awaiting_experiment",
        "proposals": proposals,
        "rejectedSignals": rejected,
        "autoMethodologyWrites": [],
    }
    atomic_json(out, artifact)
    print(f"PROPOSED {len(proposals)} learning candidate(s); human decision remains pending")
    return 0


def proposal_by_id(artifact: dict, proposal_id: str) -> dict | None:
    for proposal in artifact.get("proposals", []):
        if proposal.get("id") == proposal_id:
            return proposal
    return None


def run_metric(command: list[str], cwd: Path, timeout: int) -> tuple[int, float | None, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, None, str(exc)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return result.returncode, None, output
    try:
        payload = json.loads((result.stdout or "").strip().splitlines()[-1])
        metric = payload["metric"]
        if not isinstance(metric, (int, float)):
            raise ValueError("metric is not numeric")
        return 0, float(metric), output
    except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return 1, None, output + f"\ninvalid metric JSON: {exc}"


def run_experiment(path: Path, proposal_id: str, workspace: Path, timeout: int) -> int:
    try:
        artifact = load_json(path)
    except ValueError as exc:
        return fail("experiment artifact", str(exc), "repair or regenerate the proposal artifact")
    proposal = proposal_by_id(artifact, proposal_id)
    if proposal is None:
        return fail("experiment target", f"proposal {proposal_id} not found", "use an id from artifact.proposals")
    experiment = proposal["experiment"]
    if experiment.get("status") == "observed":
        print(f"EXPERIMENT {proposal_id} already observed — no rerun")
        return 0
    rc_b, baseline, out_b = run_metric(experiment["baselineCommand"], workspace, timeout)
    if rc_b != 0 or baseline is None:
        return fail("baseline experiment", f"command exited {rc_b}: {out_b[-500:]}",
                    "repair the read-only baseline benchmark and retry")
    rc_c, candidate, out_c = run_metric(experiment["candidateCommand"], workspace, timeout)
    if rc_c != 0 or candidate is None:
        return fail("candidate experiment", f"command exited {rc_c}: {out_c[-500:]}",
                    "repair the candidate benchmark or roll back the candidate")
    threshold = float(experiment["maxRegressionPercent"]) / 100.0
    if experiment["direction"] == "higher":
        within = candidate >= baseline * (1.0 - threshold)
    else:
        within = candidate <= baseline * (1.0 + threshold)
    recommendation = "keep" if within else "rollback"
    experiment.update({
        "status": "observed",
        "observedAt": now_iso(),
        "baseline": baseline,
        "candidate": candidate,
        "recommendation": recommendation,
        "evidence": {
            "baselineExit": rc_b,
            "candidateExit": rc_c,
            "baselineOutputTail": out_b.strip()[-300:],
            "candidateOutputTail": out_c.strip()[-300:],
        },
    })
    artifact["status"] = "awaiting_human_decision"
    atomic_json(path, artifact)
    print(f"EXPERIMENT {proposal_id}: baseline={baseline:g} candidate={candidate:g} recommendation={recommendation}")
    return 0


def decide(path: Path, proposal_id: str, decision: str, actor_type: str,
           actor: str, reason: str, rollback_evidence: str) -> int:
    try:
        artifact = load_json(path)
    except ValueError as exc:
        return fail("decision artifact", str(exc), "repair or regenerate the proposal artifact")
    proposal = proposal_by_id(artifact, proposal_id)
    if proposal is None:
        return fail("decision target", f"proposal {proposal_id} not found", "use an id from artifact.proposals")
    if actor_type != "human" or not actor.strip():
        return fail("human decision gate", "actorType is not human or actor is empty",
                    "a named human must choose keep, change, or rollback")
    if decision not in DECISIONS or not reason.strip():
        return fail("human decision", "decision/reason is missing or invalid",
                    "record keep|change|rollback with a non-empty reason")
    experiment = proposal["experiment"]
    if experiment.get("status") != "observed":
        return fail("human decision", "experiment has no observed baseline/candidate evidence",
                    "run the bounded experiment before deciding")
    recommendation = experiment.get("recommendation")
    if recommendation == "rollback" and decision != "rollback":
        return fail("regression decision", "candidate exceeds the approved regression limit",
                    "record rollback with evidence; do not keep a regressed candidate")
    if decision == "rollback" and not rollback_evidence.strip():
        return fail("rollback evidence", "rollback was selected without evidence",
                    "record the revert/disable evidence that restores the baseline")
    proposal["humanDecision"] = {
        "decision": decision,
        "actor": actor.strip(),
        "actorType": "human",
        "reason": reason.strip(),
        "rollbackEvidence": rollback_evidence.strip(),
        "at": now_iso(),
    }
    artifact["status"] = "awaiting_verification"
    atomic_json(path, artifact)
    print(f"DECIDED {proposal_id}: {decision} by human {actor.strip()}")
    return 0


def verify(path: Path) -> int:
    try:
        artifact = load_json(path)
    except ValueError as exc:
        return fail("verification artifact", str(exc), "repair or regenerate the proposal artifact")
    failures: list[str] = []
    for proposal in artifact.get("proposals", []):
        experiment = proposal.get("experiment") or {}
        decision = proposal.get("humanDecision") or {}
        if experiment.get("status") != "observed":
            failures.append(f"{proposal.get('id')}: experiment pending")
            continue
        chosen = decision.get("decision")
        if decision.get("actorType") != "human" or chosen not in DECISIONS:
            failures.append(f"{proposal.get('id')}: human decision pending")
            continue
        if experiment.get("recommendation") == "rollback" and chosen != "rollback":
            failures.append(f"{proposal.get('id')}: regressed candidate was not rolled back")
            continue
        if chosen == "rollback" and not decision.get("rollbackEvidence"):
            failures.append(f"{proposal.get('id')}: rollback evidence missing")
            continue
        proposal["verification"] = {
            "status": "passed",
            "at": now_iso(),
            "evidence": (
                f"baseline={experiment['baseline']}; candidate={experiment['candidate']}; "
                f"recommendation={experiment['recommendation']}; humanDecision={chosen}"
            ),
        }
    if failures:
        return fail("learning-loop verification", "; ".join(failures),
                    "complete the experiment and explicit human decision/rollback evidence", 1)
    artifact["status"] = "verified"
    artifact["verifiedAt"] = now_iso()
    atomic_json(path, artifact)
    print(f"VERIFIED learning loop: {len(artifact.get('proposals', []))} proposal(s), no automatic methodology writes")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Human-gated evidence learning loop")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--signals", type=Path, required=True)
    p.add_argument("--specs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--min-occurrences", type=int, default=2)
    e = sub.add_parser("experiment")
    e.add_argument("--artifact", type=Path, required=True)
    e.add_argument("--proposal", required=True)
    e.add_argument("--workspace", type=Path, required=True)
    e.add_argument("--timeout", type=int, default=120)
    d = sub.add_parser("decide")
    d.add_argument("--artifact", type=Path, required=True)
    d.add_argument("--proposal", required=True)
    d.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    d.add_argument("--actor-type", required=True)
    d.add_argument("--actor", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--rollback-evidence", default="")
    v = sub.add_parser("verify")
    v.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "propose":
        if args.min_occurrences < 2:
            return fail("promotion threshold", "min-occurrences is below 2",
                        "require at least two durable signals from distinct sources")
        return propose(args.signals, args.specs, args.out, args.min_occurrences)
    if args.command == "experiment":
        return run_experiment(args.artifact, args.proposal, args.workspace, args.timeout)
    if args.command == "decide":
        return decide(args.artifact, args.proposal, args.decision, args.actor_type,
                      args.actor, args.reason, args.rollback_evidence)
    return verify(args.artifact)


if __name__ == "__main__":
    raise SystemExit(main())
