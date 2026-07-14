#!/usr/bin/env python3
"""Deterministic anti-Goodhart 5/5 evaluator for bounded goal experiments.

No input is a quiet no-op. Pass --input explicitly; a non-5/5 evaluation exits
1 with actionable WHY/FIX lines. Invalid evidence exits 2. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

MIN_PAIRS = 5
MIN_RECALL = 0.95
MIN_PRECISION = 0.90
MIN_RELATIVE_QUALITY_LIFT = 0.20
MAX_TIME_RATIO = 1.50
MAX_HIGH_RISK_TIME_RATIO = 2.00
MAX_TOKEN_RATIO = 1.50
MIN_REPETITION_REDUCTION = 0.50
MAX_CONTEXT_GROWTH = 0.10
MAX_CHECKPOINT_BYTES = 4096
MIN_QUIZ_SCORE = 0.80


class EvidenceError(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise EvidenceError(f"{label} unreadable: {exc}") from exc
    need(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def epoch(value: object, label: str) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception as exc:
        raise EvidenceError(f"{label} must be ISO-8601") from exc


def positive_number(value: object, label: str) -> float:
    need(type(value) in (int, float) and value > 0, f"{label} must be positive")
    return float(value)


def hex_id(value: object, lengths: tuple[int, ...], label: str) -> str:
    text = str(value or "").lower()
    need(len(text) in lengths and all(char in "0123456789abcdef" for char in text),
         f"{label} must be a hexadecimal digest of length {lengths}")
    return text


def arm(pair: dict, name: str, index: int) -> dict:
    value = pair.get(name)
    need(isinstance(value, dict), f"pairs[{index}].{name} must be an object")
    for field in ("commit", "tree", "promptSha256", "environmentSha256",
                  "startedAt", "wallSeconds", "inputTokens", "findingIds",
                  "infrastructureErrors"):
        need(field in value, f"pairs[{index}].{name}.{field} is required")
    positive_number(value["wallSeconds"], f"pairs[{index}].{name}.wallSeconds")
    positive_number(value["inputTokens"], f"pairs[{index}].{name}.inputTokens")
    hex_id(value["commit"], (40, 64), f"pairs[{index}].{name}.commit")
    hex_id(value["tree"], (40, 64), f"pairs[{index}].{name}.tree")
    hex_id(value["promptSha256"], (64,), f"pairs[{index}].{name}.promptSha256")
    hex_id(value["environmentSha256"], (64,),
           f"pairs[{index}].{name}.environmentSha256")
    need(isinstance(value["findingIds"], list),
         f"pairs[{index}].{name}.findingIds must be an array")
    need(isinstance(value["infrastructureErrors"], list),
         f"pairs[{index}].{name}.infrastructureErrors must be an array")
    epoch(value["startedAt"], f"pairs[{index}].{name}.startedAt")
    return value


def quality_counts(pairs: list[dict], oracle: dict, name: str) -> dict:
    tasks = oracle.get("tasks")
    need(isinstance(tasks, list) and tasks, "oracle.tasks must be a non-empty array")
    truth: dict[str, dict[str, str]] = {}
    for index, task in enumerate(tasks):
        need(isinstance(task, dict) and str(task.get("id") or ""),
             f"oracle.tasks[{index}] requires id")
        findings = task.get("findings")
        need(isinstance(findings, list) and findings,
             f"oracle.tasks[{index}].findings must be non-empty")
        mapped: dict[str, str] = {}
        for finding in findings:
            need(isinstance(finding, dict) and str(finding.get("id") or ""),
                 f"oracle task {task['id']} has malformed finding")
            severity = str(finding.get("severity") or "")
            need(severity in ("critical", "important", "minor"),
                 f"oracle task {task['id']} has invalid severity")
            mapped[str(finding["id"])] = severity
        truth[str(task["id"])] = mapped

    tp = fp = fn = 0
    missed_critical: list[str] = []
    for index, pair in enumerate(pairs):
        task_id = str(pair.get("id") or "")
        need(task_id in truth, f"pairs[{index}].id has no oracle task")
        predicted = {str(item) for item in pair[name]["findingIds"]}
        expected = set(truth[task_id])
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        missed_critical.extend(
            f"{task_id}:{finding_id}" for finding_id in expected - predicted
            if truth[task_id][finding_id] == "critical")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1, "missedCritical": missed_critical}


def evaluate(data: dict, input_path: Path) -> dict:
    need(data.get("version") == 1, "version must be 1")
    oracle_ref = data.get("oracle")
    need(isinstance(oracle_ref, dict), "oracle reference is required")
    oracle_path = Path(str(oracle_ref.get("path") or ""))
    if not oracle_path.is_absolute():
        oracle_path = (input_path.parent / oracle_path).resolve()
    need(oracle_path.is_file(), f"oracle file not found: {oracle_path}")
    expected_hash = str(oracle_ref.get("sha256") or "").lower()
    need(len(expected_hash) == 64 and sha256(oracle_path) == expected_hash,
         "oracle sha256 does not match the frozen artifact")
    oracle = load_json(oracle_path, "oracle")
    sealed_at = epoch(oracle.get("sealedAt"), "oracle.sealedAt")

    pairs = data.get("pairs")
    need(isinstance(pairs, list), "pairs must be an array")
    parsed: list[dict] = []
    parity = True
    infrastructure_clean = True
    starts: list[float] = []
    ids: set[str] = set()
    orders: set[str] = set()
    for index, pair in enumerate(pairs):
        need(isinstance(pair, dict), f"pairs[{index}] must be an object")
        pair_id = str(pair.get("id") or "")
        need(pair_id and pair_id not in ids, f"pairs[{index}].id must be unique")
        ids.add(pair_id)
        risk = str(pair.get("riskTier") or "")
        need(risk in ("low", "medium", "high"),
             f"pairs[{index}].riskTier must be low|medium|high")
        order = str(pair.get("order") or "")
        need(order in ("manual_first", "loop_first"),
             f"pairs[{index}].order must be manual_first|loop_first")
        orders.add(order)
        manual = arm(pair, "manual", index)
        loop = arm(pair, "loop", index)
        starts.extend([epoch(manual["startedAt"], "manual.startedAt"),
                       epoch(loop["startedAt"], "loop.startedAt")])
        parity = parity and all(
            manual[field] == loop[field]
            for field in ("commit", "tree", "promptSha256", "environmentSha256"))
        infrastructure_clean = infrastructure_clean and not (
            manual["infrastructureErrors"] or loop["infrastructureErrors"])
        parsed.append({**pair, "manual": manual, "loop": loop})

    manual_quality = quality_counts(parsed, oracle, "manual") if parsed else {}
    loop_quality = quality_counts(parsed, oracle, "loop") if parsed else {}
    oracle_ids = {str(task.get("id") or "") for task in oracle.get("tasks", [])
                  if isinstance(task, dict)}
    manual_f1 = float(manual_quality.get("f1", 0.0))
    loop_f1 = float(loop_quality.get("f1", 0.0))
    quality_lift = ((loop_f1 - manual_f1) / manual_f1
                    if manual_f1 > 0 else (1.0 if loop_f1 > 0 else 0.0))
    quality_pass = bool(parsed) and all((
        loop_quality["recall"] >= MIN_RECALL,
        loop_quality["precision"] >= MIN_PRECISION,
        quality_lift >= MIN_RELATIVE_QUALITY_LIFT,
        not loop_quality["missedCritical"],
    ))

    time_ratios = [p["loop"]["wallSeconds"] / p["manual"]["wallSeconds"]
                   for p in parsed]
    token_ratios = [p["loop"]["inputTokens"] / p["manual"]["inputTokens"]
                    for p in parsed]
    high_risk_ratios = [ratio for pair, ratio in zip(parsed, time_ratios)
                        if pair["riskTier"] == "high"]
    median_time = statistics.median(time_ratios) if time_ratios else float("inf")
    median_tokens = statistics.median(token_ratios) if token_ratios else float("inf")
    efficiency_pass = (median_time <= MAX_TIME_RATIO
                       and median_tokens <= MAX_TOKEN_RATIO
                       and (not high_risk_ratios
                            or max(high_risk_ratios) <= MAX_HIGH_RISK_TIME_RATIO))

    memory = data.get("memory")
    need(isinstance(memory, dict), "memory metrics are required")
    without = positive_number(memory.get("repetitionsWithout"),
                              "memory.repetitionsWithout")
    with_memory = memory.get("repetitionsWith")
    need(type(with_memory) in (int, float) and with_memory >= 0,
         "memory.repetitionsWith must be non-negative")
    repetition_reduction = 1 - float(with_memory) / without
    context = memory.get("contextTokensByRound")
    need(isinstance(context, list) and len(context) >= 2,
         "memory.contextTokensByRound needs at least two rounds")
    values = [positive_number(value, "memory.contextTokensByRound[]")
              for value in context]
    context_growth = max(values) / values[0] - 1
    checkpoint_bytes = memory.get("maxCheckpointBytesObserved")
    need(type(checkpoint_bytes) is int and checkpoint_bytes >= 0,
         "memory.maxCheckpointBytesObserved must be non-negative integer")
    memory_pass = (repetition_reduction >= MIN_REPETITION_REDUCTION
                   and context_growth <= MAX_CONTEXT_GROWTH
                   and checkpoint_bytes <= MAX_CHECKPOINT_BYTES
                   and memory.get("controlIsolated") is True
                   and memory.get("stateReadViolations") == 0)

    quiz = data.get("quiz")
    need(isinstance(quiz, dict), "quiz metrics are required")
    immediate = float(quiz.get("immediateScore", -1))
    delayed = float(quiz.get("delayed24hScore", -1))
    immediate_at = epoch(quiz.get("immediateAt"), "quiz.immediateAt")
    delayed_at = epoch(quiz.get("delayedAt"), "quiz.delayedAt")
    critical_unknown = quiz.get("criticalUnknownCount")
    surrender = data.get("cognitiveSurrenderCount")
    need(type(critical_unknown) is int and critical_unknown >= 0,
         "quiz.criticalUnknownCount must be non-negative integer")
    need(type(surrender) is int and surrender >= 0,
         "cognitiveSurrenderCount must be non-negative integer")
    understanding_pass = (immediate >= MIN_QUIZ_SCORE
                          and delayed >= MIN_QUIZ_SCORE
                          and critical_unknown == 0 and surrender == 0
                          and delayed_at - immediate_at >= 86400
                          and (not starts or immediate_at >= max(starts)))

    budgets = data.get("budgets")
    need(isinstance(budgets, dict), "budgets evidence is required")
    budget_path = Path(str(budgets.get("evidencePath") or ""))
    if not budget_path.is_absolute():
        budget_path = (input_path.parent / budget_path).resolve()
    budget_hash = str(budgets.get("evidenceSha256") or "").lower()
    budget_evidence_valid = (budget_path.is_file() and len(budget_hash) == 64
                             and sha256(budget_path) == budget_hash)
    integrity_pass = all((
        len(parsed) >= MIN_PAIRS,
        ids == oracle_ids,
        orders == {"manual_first", "loop_first"},
        parity,
        infrastructure_clean,
        bool(starts) and sealed_at <= min(starts),
        budgets.get("stopTestsPassed") is True,
        budget_evidence_valid,
        budgets.get("extraRoundsAfterDod") == 0,
    ))

    gates = {"quality": quality_pass, "efficiency": efficiency_pass,
             "memory": memory_pass, "understanding": understanding_pass,
             "integrity": integrity_pass}
    score = sum(1 for passed in gates.values() if passed)
    return {
        "status": "FIVE_STAR" if score == 5 else "NOT_FIVE_STAR",
        "score": score,
        "outOf": 5,
        "gates": gates,
        "metrics": {
            "validPairs": len(parsed), "environmentParity": parity,
            "infrastructureClean": infrastructure_clean,
            "oracleTaskCoverage": ids == oracle_ids,
            "counterbalancedOrder": orders == {"manual_first", "loop_first"},
            "oracleFrozenBeforeRuns": bool(starts) and sealed_at <= min(starts),
            "budgetEvidenceValid": budget_evidence_valid,
            "loopPrecision": round(float(loop_quality.get("precision", 0)), 4),
            "loopRecall": round(float(loop_quality.get("recall", 0)), 4),
            "relativeQualityLift": round(quality_lift, 4),
            "missedCritical": loop_quality.get("missedCritical", []),
            "medianTimeRatio": round(median_time, 4),
            "medianTokenRatio": round(median_tokens, 4),
            "maxHighRiskTimeRatio": round(max(high_risk_ratios), 4)
            if high_risk_ratios else 0.0,
            "repetitionReduction": round(repetition_reduction, 4),
            "contextGrowth": round(context_growth, 4),
            "maxCheckpointBytesObserved": checkpoint_bytes,
            "immediateQuiz": immediate, "delayed24hQuiz": delayed,
            "cognitiveSurrenderCount": surrender,
        },
    }


def actionable(path: Path, result: dict) -> list[str]:
    fixes = {
        "quality": "freeze a complete oracle; reach recall>=95%, precision>=90%, lift>=20%, critical misses=0",
        "efficiency": "route checker adaptively; reach median time/tokens<=1.5x and high-risk time<=2x",
        "memory": "store only Done/Evidence/Status/Open risks/Next; cut repeats>=50%, growth<=10%, checkpoint<=4096B",
        "understanding": "run immediate and 24h blind quizzes>=80%; resolve all deferred/unknown critical items",
        "integrity": "collect >=5 parity-matched, infrastructure-clean pairs; seal oracle first and prove typed stops",
    }
    return [f"{path}: $.gates.{gate} WHY gate failed; FIX {fixes[gate]}"
            for gate, passed in result["gates"].items() if not passed]


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic bounded-goal 5/5 gate")
    parser.add_argument("--input", type=Path, default=None,
                        help="evaluation JSON; omitted = quiet no-op")
    parser.add_argument("--json", action="store_true",
                        help="print the deterministic result on success/failure")
    args = parser.parse_args()
    if args.input is None:
        return 0
    try:
        data = load_json(args.input, "evaluation")
        result = evaluate(data, args.input.resolve())
    except EvidenceError as exc:
        print(f"{args.input}: $ WHY invalid evidence: {exc}; FIX repair the sealed input")
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["score"] != 5:
        for line in actionable(args.input, result):
            print(line)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
