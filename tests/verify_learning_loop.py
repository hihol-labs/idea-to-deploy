#!/usr/bin/env python3
"""Positive and adversarial proof for the human-gated learning loop."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "retro" / "scripts" / "itd_learning_loop.py"
CORPUS = ROOT / "benchmarks" / "learning-loop" / "CORPUS.json"
CORPUS_SHA = ROOT / "benchmarks" / "learning-loop" / "CORPUS.sha256"
PY = sys.executable or "python3"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def repo_digest() -> str:
    digest = hashlib.sha256()
    for top in (ROOT / "skills", ROOT / "hooks", ROOT / "docs"):
        for path in sorted(p for p in top.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def metric_command(value: float) -> list[str]:
    code = f"import json; print(json.dumps({{'metric': {value!r}}}))"
    return [PY, "-c", code]


def specs_from(corpus: dict) -> dict:
    specs = {}
    for signal_class, experiment in corpus["experiments"].items():
        specs[signal_class] = {
            "target": f"hooks/{signal_class}.policy",
            "hypothesis": f"The candidate reduces recurrence of {signal_class}.",
            "metric": "external_pass_ratio",
            "direction": experiment["direction"],
            "maxRegressionPercent": experiment["maxRegressionPercent"],
            "baselineCommand": metric_command(experiment["baseline"]),
            "candidateCommand": metric_command(experiment["candidate"]),
            "rollbackPlan": "Disable the candidate and rerun the sealed baseline benchmark.",
        }
    return specs


def write_inputs(root: Path, signals: list[dict], specs: dict) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    signal_path = root / "signals.jsonl"
    signal_path.write_text("\n".join(json.dumps(row) for row in signals) + "\n", encoding="utf-8")
    specs_path = root / "specs.json"
    specs_path.write_text(json.dumps(specs, indent=2) + "\n", encoding="utf-8")
    return signal_path, specs_path


def main() -> int:
    raw = CORPUS.read_bytes()
    expected = CORPUS_SHA.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(raw).hexdigest()
    check("learning corpus seal matches", actual == expected,
          f"expected={expected} actual={actual}")
    corpus = json.loads(raw)
    before = repo_digest()

    with tempfile.TemporaryDirectory(prefix="itd-learning-loop-") as td:
        root = Path(td)
        signals, specs = write_inputs(root, corpus["signals"], specs_from(corpus))
        artifact = root / "learning-proposals.json"
        rc, out = run([
            PY, str(RUNNER), "propose", "--signals", str(signals), "--specs", str(specs),
            "--out", str(artifact), "--min-occurrences", str(corpus["thresholds"]["minOccurrences"]),
        ], root)
        check("repeated external classes become proposals", rc == 0, out[-800:])
        data = json.loads(artifact.read_text(encoding="utf-8"))
        check("exact proposal count", len(data["proposals"]) == corpus["thresholds"]["expectedProposals"],
              str([p["signalClass"] for p in data["proposals"]]))
        classes = {p["signalClass"] for p in data["proposals"]}
        check("internal self-metric cannot trigger promotion", "raise-vcr" not in classes)
        check("single signal remains a note", "one-off-warning" not in classes)
        check("every proposal cites two distinct sources",
              all(p["distinctSources"] >= corpus["thresholds"]["minDistinctSources"]
                  for p in data["proposals"]))

        rc, out = run([PY, str(RUNNER), "verify", "--artifact", str(artifact)], root)
        check("verification fails before experiment/decision",
              rc != 0 and "WHY:" in out and "FIX:" in out, out[-600:])

        by_class = {p["signalClass"]: p["id"] for p in data["proposals"]}
        for signal_class, proposal_id in by_class.items():
            rc, out = run([
                PY, str(RUNNER), "experiment", "--artifact", str(artifact),
                "--proposal", proposal_id, "--workspace", str(root),
            ], root)
            check(f"real experiment executes: {signal_class}", rc == 0, out[-600:])

        regressed = by_class["manual-path-repair"]
        rc, out = run([
            PY, str(RUNNER), "decide", "--artifact", str(artifact), "--proposal", regressed,
            "--decision", "keep", "--actor-type", "model", "--actor", "agent",
            "--reason", "self-approved",
        ], root)
        check("model cannot make promotion decision", rc != 0 and "WHY:" in out and "FIX:" in out,
              out[-500:])
        rc, out = run([
            PY, str(RUNNER), "decide", "--artifact", str(artifact), "--proposal", regressed,
            "--decision", "keep", "--actor-type", "human", "--actor", "auditor",
            "--reason", "keep despite regression",
        ], root)
        check("human cannot keep a regressed candidate without rollback",
              rc != 0 and "WHY:" in out and "FIX:" in out, out[-500:])

        kept = by_class["missing-actionable-denial"]
        rc, out = run([
            PY, str(RUNNER), "decide", "--artifact", str(artifact), "--proposal", kept,
            "--decision", "keep", "--actor-type", "human", "--actor", "auditor",
            "--reason", "candidate meets the sealed external metric",
        ], root)
        check("human keep decision records", rc == 0, out[-500:])
        rc, out = run([
            PY, str(RUNNER), "decide", "--artifact", str(artifact), "--proposal", regressed,
            "--decision", "rollback", "--actor-type", "human", "--actor", "auditor",
            "--reason", "candidate regressed the external metric",
            "--rollback-evidence", "fixture://candidate-disabled-and-baseline-restored",
        ], root)
        check("human rollback decision records", rc == 0, out[-500:])
        rc, out = run([PY, str(RUNNER), "verify", "--artifact", str(artifact)], root)
        check("complete learning loop verifies", rc == 0 and "VERIFIED learning loop" in out, out[-600:])
        final = json.loads(artifact.read_text(encoding="utf-8"))
        decisions = {p["signalClass"]: p["humanDecision"]["decision"] for p in final["proposals"]}
        check("keep and rollback paths both covered",
              decisions == {"manual-path-repair": "rollback", "missing-actionable-denial": "keep"},
              str(decisions))
        check("runner records zero automatic methodology writes",
              len(final["autoMethodologyWrites"]) <= corpus["thresholds"]["maxAutomaticMethodologyWrites"])

        # Adversarial: repetition must come from distinct sources.
        duplicate_source = [
            {"id": "d1", "class": "duplicate-source", "type": "review_finding",
             "project": "one", "reviewId": "same", "evidence": "review://one/a"},
            {"id": "d2", "class": "duplicate-source", "type": "review_finding",
             "project": "one", "reviewId": "same", "evidence": "review://one/b"},
        ]
        dup_specs = {"duplicate-source": next(iter(specs_from(corpus).values()))}
        dup_signals, dup_spec_path = write_inputs(root / "duplicate", duplicate_source, dup_specs)
        dup_artifact = root / "duplicate" / "artifact.json"
        rc, out = run([
            PY, str(RUNNER), "propose", "--signals", str(dup_signals),
            "--specs", str(dup_spec_path), "--out", str(dup_artifact),
        ], root)
        check("same-source duplicates do not count as repetition",
              rc != 0 and not dup_artifact.exists() and "WHY:" in out and "FIX:" in out, out[-500:])
        rc, out = run([
            PY, str(RUNNER), "propose", "--signals", str(signals), "--specs", str(specs),
            "--out", str(root / "weak.json"), "--min-occurrences", "1",
        ], root)
        check("promotion threshold cannot be weakened below two",
              rc != 0 and "WHY:" in out and "FIX:" in out, out[-500:])

    after = repo_digest()
    check("learning runner never edits methodology", before == after,
          f"before={before} after={after}")
    print("METRICS " + json.dumps({
        "proposals": corpus["thresholds"]["expectedProposals"],
        "humanDecisions": 2,
        "rollbackPaths": 1,
        "automaticMethodologyWrites": 0,
        "adversarialGuards": 5,
    }, sort_keys=True))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS — evidence-backed learning loop is human-gated and reversible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
