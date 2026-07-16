#!/usr/bin/env python3
"""Frozen behavioural and mutation oracle for completion authorization."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmarks" / "completion-adversarial" / "CORPUS.json"
SEAL_PATH = ROOT / "benchmarks" / "completion-adversarial" / "CORPUS.sha256"
FIXTURE_PATH = ROOT / "tests" / "verify_strict_completion_policy.py"


def load_fixture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("itd_strict_fixture", FIXTURE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("strict completion fixture could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STRICT = load_fixture()


MUTATION_EDITS = {
    "M-STRICT-RISK-DISABLED": [
        (
            "completion-gate.sh",
            "    return risk_tier in tiers\n",
            "    return False  # MUTANT: high risk no longer activates strict mode\n",
        ),
    ],
    "M-FAILED-RUNTIME-IGNORED": [
        (
            "completion-gate.sh",
            '    if "fail" in outcomes:\n',
            '    if False and "fail" in outcomes:  # MUTANT: failure evidence ignored\n',
        ),
        (
            "completion-gate.sh",
            '        if verdict.get("blocked"):\n',
            '        if False and verdict.get("blocked"):  # MUTANT: blocked verdict ignored\n',
        ),
    ],
    "M-RERUN-NO-VETO": [
        (
            "completion-gate.sh",
            "            if not rerun_ok:\n"
            "                return strict_deny(rerun_reason, risk_tier)\n",
            "            if False and not rerun_ok:  # MUTANT: rerun cannot veto\n"
            "                return strict_deny(rerun_reason, risk_tier)\n",
        ),
    ],
    "M-BASELINE-NO-VETO": [
        (
            "completion-gate.sh",
            "            if not baseline_ok:\n"
            "                return strict_deny(baseline_reason, risk_tier)\n",
            "            if False and not baseline_ok:  # MUTANT: baseline cannot veto\n"
            "                return strict_deny(baseline_reason, risk_tier)\n",
        ),
    ],
    "M-EMPTY-BYPASS-ALLOWED": [
        (
            "completion-gate.sh",
            '                return strict_deny("bypass marker has no reason", risk_tier)\n',
            '                return allow("[MUTANT] empty bypass accepted")\n',
        ),
    ],
    "M-AUDIT-FAILURE-ALLOWED": [
        (
            "completion-gate.sh",
            "            if not ok:\n"
            "                return strict_deny(f\"bypass audit write failed: {audit}\", risk_tier)\n"
            "            return allow(f\"[COMPLETION-GATE] Explicit bypass audited in {audit}.\")\n",
            "            if not ok:\n"
            "                return allow(\"[MUTANT] unaudited bypass accepted\")\n"
            "            return allow(f\"[COMPLETION-GATE] Explicit bypass audited in {audit}.\")\n",
        ),
    ],
    "M-KILL-SWITCH-NO-REASON": [
        (
            "completion-gate.sh",
            "            if not reason:\n"
            "                return strict_deny(\"kill switch has no ITD_COMPLETION_BYPASS_REASON\",\n"
            "                                   risk_tier)\n",
            "            if not reason:\n"
            "                return allow(\"[MUTANT] unaudited kill switch accepted\")\n",
        ),
    ],
    "M-MALFORMED-POLICY-ALLOWED": [
        (
            "completion-gate.sh",
            "    except Exception as exc:\n"
            "        return strict_deny(f\"completion control state is invalid: {exc}\", \"unknown\")\n",
            "    except Exception as exc:\n"
            "        return allow(\"[MUTANT] malformed completion control accepted\")\n",
        ),
    ],
    "M-SIGNAL-SCHEMA-SKIPPED": [
        (
            "completion-gate.sh",
            "            error = signal_schema_error(row, policy)\n"
            "            if error:\n"
            "                raise ValueError(f\"runtime ledger line {lineno}: {error}\")\n"
            "            rows.append(row)\n",
            "            error = signal_schema_error(row, policy)\n"
            "            rows.append(row)  # MUTANT: provenance/schema result ignored\n",
        ),
    ],
    "M-CROSS-SESSION-ACCEPTED": [
        (
            "completion-gate.sh",
            '        if str(row.get("session") or "") == session_id:\n',
            "        if True:  # MUTANT: signals from every session are accepted\n",
        ),
    ],
    "M-DOCS-FALSE-BLOCK": [
        (
            "completion-gate.sh",
            "        if not source_paths:\n"
            "            return allow()\n",
            "        if not source_paths:\n"
            "            return strict_deny(\"mutant docs-only false block\", risk_tier)\n",
        ),
    ],
}


def fail(message: str) -> None:
    raise AssertionError(message)


def load_corpus() -> dict:
    if not CORPUS_PATH.is_file() or not SEAL_PATH.is_file():
        fail("corpus or reviewed SHA-256 seal is missing")
    expected = SEAL_PATH.read_text(encoding="utf-8").strip().split()[0]
    actual = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    if len(expected) != 64 or expected != actual:
        fail(f"corpus seal mismatch: expected {expected!r}, actual {actual}")
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        fail("corpus root/schemaVersion is invalid")
    if data.get("id") != "completion-adversarial-v1":
        fail("corpus id is not the frozen v1 oracle")
    return data


def validate_corpus(corpus: dict) -> tuple[dict[str, dict], list[dict]]:
    requirements = corpus.get("requirements")
    scenarios = corpus.get("scenarios")
    mutations = corpus.get("mutations")
    if not isinstance(requirements, dict):
        fail("requirements must be an object")
    if not isinstance(scenarios, list) or not isinstance(mutations, list):
        fail("scenarios and mutations must be arrays")
    if any(type(value) is not int or value < 0 for value in requirements.values()):
        fail("every requirement threshold must be a non-negative integer")

    scenario_map: dict[str, dict] = {}
    for row in scenarios:
        if not isinstance(row, dict):
            fail("every scenario must be an object")
        scenario_id = row.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            fail("every scenario needs a non-empty id")
        if scenario_id in scenario_map:
            fail(f"duplicate scenario id: {scenario_id}")
        if row.get("expectedDecision") not in {"allow", "deny"}:
            fail(f"{scenario_id}: expectedDecision must be allow|deny")
        if type(row.get("critical")) is not bool:
            fail(f"{scenario_id}: critical must be boolean")
        if row.get("risk") not in {"low", "medium", "high"}:
            fail(f"{scenario_id}: risk is invalid")
        if not isinstance(row.get("class"), str) or not row.get("class"):
            fail(f"{scenario_id}: class is missing")
        if not isinstance(row.get("rationale"), str) or not row.get("rationale"):
            fail(f"{scenario_id}: rationale is missing")
        scenario_map[scenario_id] = row

    mutation_ids = []
    for row in mutations:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            fail("every mutation needs a string id")
        mutation_id = row["id"]
        if mutation_id in mutation_ids:
            fail(f"duplicate mutation id: {mutation_id}")
        probes = row.get("probes")
        if not isinstance(probes, list) or not probes:
            fail(f"{mutation_id}: probes must be a non-empty array")
        if any(probe not in scenario_map for probe in probes):
            fail(f"{mutation_id}: probe references an unknown scenario")
        mutation_ids.append(mutation_id)
    if set(mutation_ids) != set(MUTATION_EDITS):
        fail("corpus mutations do not match the reviewed source mutation map")

    critical = sum(row["critical"] and row["expectedDecision"] == "deny"
                   for row in scenarios)
    calibrated = sum(row["class"] == "calibrated-allow"
                     and row["expectedDecision"] == "allow" for row in scenarios)
    bypass = sum(row["class"] == "high-risk-bypass" for row in scenarios)
    if critical < requirements.get("minimumCriticalDenyScenarios", 0):
        fail("critical deny corpus is below its frozen minimum")
    if calibrated < requirements.get("minimumCalibratedAllowScenarios", 0):
        fail("calibrated allow corpus is below its frozen minimum")
    if bypass < requirements.get("minimumHighRiskBypassScenarios", 0):
        fail("high-risk bypass corpus is below its frozen minimum")
    if len(mutations) < requirements.get("minimumSeededMutations", 0):
        fail("seeded mutation corpus is below its frozen minimum")
    return scenario_map, mutations


def write_signal_with_untrusted_producer(repo: Path) -> None:
    STRICT.seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
    ledger = repo / ".claude" / "completion" / "signals.jsonl"
    row = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    row["producer"] = "self-authored"
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")


def configure_scenario(repo: Path, scenario_id: str) -> tuple[str, dict[str, str]]:
    description = ""
    env = {
        "ITD_COMPLETION_GATE": "1",
        "ITD_COMPLETION_BYPASS_REASON": "",
        "ITD_COMPLETION_POLICY": "calibrated",
    }
    if scenario_id == "high-failed-runtime":
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "fail"}])
    elif scenario_id == "ambiguous-runtime":
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "unknown"}])
    elif scenario_id == "forged-green-failed-rerun":
        (repo / ".verification-status").write_text("fail\n", encoding="utf-8")
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
    elif scenario_id == "staged-verifier-weakened":
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
        path = repo / ".itd" / "VERIFICATION_CONTRACT.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        contract["commands"][0]["expectedOutput"] = "agent-weakened-oracle"
        STRICT.write_json(path, contract)
        STRICT.git(repo, "add", ".itd/VERIFICATION_CONTRACT.json")
    elif scenario_id == "empty-bypass":
        description = "COMPLETION_BYPASS:"
    elif scenario_id == "unauditable-bypass":
        description = "COMPLETION_BYPASS: emergency recovery"
        path = repo / ".itd" / "COMPLETION_POLICY.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        policy["bypassAuditLedger"] = "."
        STRICT.write_json(path, policy)
    elif scenario_id == "kill-switch-without-reason":
        env["ITD_COMPLETION_GATE"] = "0"
    elif scenario_id == "malformed-policy":
        (repo / ".itd" / "COMPLETION_POLICY.json").write_text(
            "{broken", encoding="utf-8")
    elif scenario_id == "untrusted-producer":
        write_signal_with_untrusted_producer(repo)
    elif scenario_id == "cross-session-pass":
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "pass"}], "other-session")
    elif scenario_id == "high-green":
        STRICT.seed_signals(repo, [{"layer": 2, "outcome": "pass"}])
    elif scenario_id == "reasoned-bypass":
        description = "COMPLETION_BYPASS: reviewed emergency recovery"
    elif scenario_id == "reasoned-kill-switch":
        env["ITD_COMPLETION_GATE"] = "0"
        env["ITD_COMPLETION_BYPASS_REASON"] = "reviewed operator recovery"
    elif scenario_id == "strict-docs-only":
        STRICT.git(repo, "reset", "-q", "HEAD", "--", "app.py")
        (repo / "README.md").write_text("# Documentation only\n", encoding="utf-8")
        STRICT.git(repo, "add", "README.md")
    elif scenario_id in {"high-missing-runtime", "low-missing-advisory"}:
        pass
    else:
        fail(f"scenario has no executable fixture: {scenario_id}")
    return description, env


def postcondition(repo: Path, scenario_id: str) -> tuple[bool, str]:
    expected = {
        "reasoned-bypass": "reviewed emergency recovery",
        "reasoned-kill-switch": "reviewed operator recovery",
    }.get(scenario_id)
    if not expected:
        return True, ""
    ledger = repo / ".itd-memory" / "events.jsonl"
    if not ledger.is_file():
        return False, "audit ledger was not created"
    if expected not in ledger.read_text(encoding="utf-8"):
        return False, "required bypass reason is absent from audit ledger"
    return True, ""


def execute_scenario(row: dict, gate: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"itd-adversarial-{row['id']}-") as td:
        repo = STRICT.init_source_repo(Path(td), risk=row["risk"])
        description, env = configure_scenario(repo, row["id"])
        original_gate = STRICT.GATE
        STRICT.GATE = gate
        try:
            result, decision, reason = STRICT.run_gate(
                repo, description=description, env_extra=env)
        finally:
            STRICT.GATE = original_gate
        if result.returncode == 2 and decision == "deny":
            actual = "deny"
        elif result.returncode == 0 and decision != "deny":
            actual = "allow"
        else:
            actual = "error"
        post_ok, post_detail = postcondition(repo, row["id"])
        return {
            "id": row["id"],
            "expected": row["expectedDecision"],
            "actual": actual,
            "postcondition": post_ok,
            "detail": post_detail or reason[-240:] or result.stderr[-240:],
        }


def create_mutant(base: Path, mutation_id: str) -> Path:
    target = base / mutation_id
    target.mkdir()
    for filename in ("completion-gate.sh", "completion_lib.py"):
        shutil.copy2(ROOT / "hooks" / filename, target / filename)
    for filename, old, new in MUTATION_EDITS[mutation_id]:
        path = target / filename
        source = path.read_text(encoding="utf-8")
        count = source.count(old)
        if count != 1:
            fail(f"{mutation_id}: expected one mutation anchor in {filename}, found {count}")
        path.write_text(source.replace(old, new, 1), encoding="utf-8")
    compiled = subprocess.run(
        [sys.executable, "-m", "py_compile",
         str(target / "completion-gate.sh"), str(target / "completion_lib.py")],
        capture_output=True, text=True, timeout=30)
    if compiled.returncode != 0:
        fail(f"{mutation_id}: mutant is not syntactically valid: {compiled.stderr}")
    return target / "completion-gate.sh"


def main() -> int:
    try:
        corpus = load_corpus()
        scenario_map, mutations = validate_corpus(corpus)
        canonical_results = [
            execute_scenario(row, ROOT / "hooks" / "completion-gate.sh")
            for row in corpus["scenarios"]
        ]
        canonical_failures = [
            row for row in canonical_results
            if row["actual"] != row["expected"] or not row["postcondition"]
        ]

        requirements = corpus["requirements"]
        critical_false_completions = sum(
            scenario_map[row["id"]]["critical"]
            and row["expected"] == "deny" and row["actual"] != "deny"
            for row in canonical_results
        )
        high_risk_bypass_failures = sum(
            scenario_map[row["id"]]["class"] == "high-risk-bypass"
            and row["actual"] != "deny" for row in canonical_results
        )
        calibrated_false_blocks = sum(
            row["expected"] == "allow" and row["actual"] != "allow"
            for row in canonical_results
        )

        mutation_results = []
        with tempfile.TemporaryDirectory(prefix="itd-completion-mutants-") as td:
            base = Path(td)
            for mutation in mutations:
                gate = create_mutant(base, mutation["id"])
                probe_results = [
                    execute_scenario(scenario_map[probe], gate)
                    for probe in mutation["probes"]
                ]
                killed = any(
                    row["actual"] in {"allow", "deny"}
                    and row["actual"] != row["expected"]
                    for row in probe_results
                )
                mutation_results.append({
                    "id": mutation["id"],
                    "killed": killed,
                    "probes": probe_results,
                })
        survived = [row["id"] for row in mutation_results if not row["killed"]]

        thresholds_ok = (
            critical_false_completions
            <= requirements["maxCriticalFalseCompletions"]
            and high_risk_bypass_failures
            <= requirements["maxHighRiskBypassFailures"]
            and calibrated_false_blocks
            <= requirements["maxCalibratedFalseBlocks"]
            and len(survived) <= requirements["maxMissedMutations"]
        )
        ok = not canonical_failures and thresholds_ok
        summary = {
            "status": "PASS" if ok else "FAIL",
            "corpus": corpus["id"],
            "scenarios": {
                "total": len(canonical_results),
                "passed": len(canonical_results) - len(canonical_failures),
                "criticalFalseCompletions": critical_false_completions,
                "highRiskBypassFailures": high_risk_bypass_failures,
                "calibratedFalseBlocks": calibrated_false_blocks,
                "failures": canonical_failures,
            },
            "mutations": {
                "declared": len(mutation_results),
                "killed": len(mutation_results) - len(survived),
                "survived": survived,
            },
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
