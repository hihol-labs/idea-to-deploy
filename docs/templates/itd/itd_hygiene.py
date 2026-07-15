#!/usr/bin/env python3
"""Vendor-neutral session hygiene, quality, and harness-ablation runner.

The script is copied into adopted projects as ``.itd/itd_hygiene.py``.  It is
an explicit boundary, not a Stop hook: ordinary turns stay soft, while
``close`` returns non-zero unless verification AND clean-state checks pass.

Cleanup is intentionally capability-poor.  It only handles paths declared in
the session artifact manifest, refuses tracked paths, never recursively
deletes a directory, and treats an already-absent artifact as success.  That
makes repeated cleanup safe and idempotent without hiding user work.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


GRADES = {"A", "B", "C", "D", "F"}
WORST_FIRST = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
QUALITY_FIELDS = (
    "id", "grade", "verification", "agentUnderstandable", "testStability",
    "architectureBoundaries", "codeConventions", "reviewedAt", "evidence",
    "priorities",
)
QUALITY_DIMENSIONS = (
    "verification", "agentUnderstandable", "testStability",
    "architectureBoundaries", "codeConventions",
)
GRADE_POINTS = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
SOURCE_PATHSPECS = tuple(
    item
    for ext in ("py", "js", "jsx", "ts", "tsx", "go", "rb", "java", "rs",
                "php", "c", "cc", "cpp", "cs", "kt", "kts", "swift", "scala",
                "ex", "exs", "vue", "svelte", "sql")
    for item in (f":(glob)*.{ext}", f":(glob)**/*.{ext}")
)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{path}: missing")
    except Exception as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be an object")
    return data


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def problem(path: str, why: str, fix: str) -> str:
    return f"{path}: WHY: {why} | FIX: {fix}"


DEFAULT_COMPLETION_POLICY = {
    "mode": "calibrated",
    "defaultRiskTier": "medium",
    "strictRiskTiers": ["high"],
    "runtimeSignalLedger": ".claude/completion/signals.jsonl",
    "verificationContract": ".itd/VERIFICATION_CONTRACT.json",
    "verificationBaseline": "last-source-commit",
    "bypassAuditLedger": ".itd-memory/events.jsonl",
    "runtimeLayers": [2, 3],
    "runtimeKinds": ["test_run", "app_start"],
    "signalProducer": "itd-completion-signals",
    "sessionLockMaxAgeSeconds": 600,
}


def validate_completion_policy(policy: dict) -> str:
    if policy.get("mode") not in {"calibrated", "strict"}:
        return "mode must be calibrated|strict"
    allowed_risks = {"low", "medium", "high"}
    if policy.get("defaultRiskTier") not in allowed_risks:
        return "defaultRiskTier must be low|medium|high"
    tiers = policy.get("strictRiskTiers")
    if not isinstance(tiers, list) or "high" not in tiers \
            or any(str(x).lower() not in allowed_risks for x in tiers):
        return "strictRiskTiers must be a list containing high"
    layers = policy.get("runtimeLayers")
    if not isinstance(layers, list) or not layers \
            or any(type(x) is not int or x not in {2, 3} for x in layers):
        return "runtimeLayers must be a non-empty list of 2/3"
    kinds = policy.get("runtimeKinds")
    if not isinstance(kinds, list) or not kinds \
            or any(not isinstance(x, str) or not x for x in kinds):
        return "runtimeKinds must be a non-empty string list"
    if not isinstance(policy.get("signalProducer"), str) \
            or not policy.get("signalProducer"):
        return "signalProducer must be non-empty"
    if policy.get("verificationBaseline") != "last-source-commit":
        return "verificationBaseline must be last-source-commit"
    if policy.get("verificationContract") != ".itd/VERIFICATION_CONTRACT.json":
        return ("verificationContract must be the canonical "
                ".itd/VERIFICATION_CONTRACT.json")
    max_lock_age = policy.get("sessionLockMaxAgeSeconds")
    if type(max_lock_age) is not int or not 1 <= max_lock_age <= 3600:
        return "sessionLockMaxAgeSeconds must be an integer within 1..3600"
    for key in ("runtimeSignalLedger", "bypassAuditLedger", "verificationContract"):
        value = policy.get(key)
        if not isinstance(value, str) or not value or Path(value).is_absolute() \
                or ".." in Path(value).parts:
            return f"{key} must be a safe project-relative path"
    return ""


def completion_policy(root: Path, contract: dict) -> tuple[dict, list[str]]:
    policy = dict(DEFAULT_COMPLETION_POLICY)
    relative = str(contract.get("completionPolicy") or "")
    if not relative:
        invalid = validate_completion_policy(policy)
        return policy, ([problem("completionPolicy", invalid,
                                 "repair completion policy defaults")] if invalid else [])
    errors: list[str] = []
    target = resolve_repo_path(root, relative, "completionPolicy", errors)
    if target is None:
        return policy, errors
    try:
        policy.update(load_json(target))
    except ValueError as exc:
        errors.append(problem(relative, str(exc), "repair COMPLETION_POLICY.json"))
    invalid = validate_completion_policy(policy)
    if invalid:
        errors.append(problem(relative, invalid, "repair COMPLETION_POLICY.json"))
    close_verifier = str(contract.get("verificationContract") or "")
    policy_verifier = str(policy.get("verificationContract") or "")
    if close_verifier and close_verifier != policy_verifier:
        errors.append(problem(
            "verificationContract",
            "SESSION_EXIT_CONTRACT verifier does not match the completion policy verifier",
            "point both contracts to .itd/VERIFICATION_CONTRACT.json"))
    return policy, errors


def active_risk_tier(root: Path, policy: dict) -> str:
    def read(path: Path) -> dict:
        if not path.exists():
            return {}
        return load_json(path)

    state = read(root / ".itd-memory" / "STATE.json")
    current = state.get("currentUnit") or {}
    if not isinstance(current, dict):
        raise ValueError("STATE.currentUnit must be an object")
    if current.get("riskTier"):
        risk = str(current["riskTier"]).lower()
        if risk not in {"low", "medium", "high"}:
            raise ValueError("STATE currentUnit.riskTier is invalid")
        return risk
    goal = read(root / ".itd-memory" / "GOAL.json")
    current_id = str(goal.get("currentUnitId") or "")
    units = goal.get("units") or []
    if not isinstance(units, list):
        raise ValueError("GOAL.units must be a list")
    for unit in units:
        if isinstance(unit, dict) and unit.get("id") == current_id:
            if unit.get("riskTier"):
                risk = str(unit["riskTier"]).lower()
                if risk not in {"low", "medium", "high"}:
                    raise ValueError("GOAL unit riskTier is invalid")
                return risk
            break
    return str(policy.get("defaultRiskTier") or "medium").lower()


def strict_completion(policy: dict, risk_tier: str) -> bool:
    if str(policy.get("mode") or "").lower() == "strict":
        return True
    tiers = {str(x).lower() for x in (policy.get("strictRiskTiers") or [])}
    return risk_tier in tiers


def completion_session_id(root: Path, policy: dict | None = None) -> str:
    for name in ("ITD_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        lock = load_json(root / ".itd-memory" / ".active-session.lock")
        timestamp = float(lock.get("timestamp"))
        age = time.time() - timestamp
        max_age = int((policy or DEFAULT_COMPLETION_POLICY).get(
            "sessionLockMaxAgeSeconds") or 600)
        if age < -60 or age > max_age:
            return ""
        return str(lock.get("session") or "").strip()
    except (TypeError, ValueError):
        return ""


def audit_completion_bypass(root: Path, policy: dict, reason: str,
                            boundary: str) -> str | None:
    errors: list[str] = []
    relative = str(policy.get("bypassAuditLedger") or ".itd-memory/events.jsonl")
    target = resolve_repo_path(root, relative, "bypassAuditLedger", errors)
    if target is None or errors:
        return errors[0] if errors else "invalid bypass audit path"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now(dt.timezone.utc)
        event = {
            "id": f"evt-completion-bypass-{int(now.timestamp() * 1_000_000)}",
            "at": now.isoformat(),
            "actor": "human-bypass",
            "type": "completion_bypass",
            "name": boundary,
            "decision": "allowed",
            "session": completion_session_id(root, policy) or "unknown",
            "reason": reason[:500],
        }
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return None
    except Exception as exc:
        return str(exc)


def verification_baseline_error(root: Path, policy: dict) -> str:
    relative = Path(str(policy.get("verificationContract") or ""))
    target = (root / relative).resolve(strict=False)
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return "verification contract escapes the repository"
    if not target.is_file():
        return f"verification contract is missing: {relative.as_posix()}"
    rel = relative.as_posix()
    try:
        last_source = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", *SOURCE_PATHSPECS],
            cwd=str(root), capture_output=True, text=True, timeout=20)
        commit = last_source.stdout.strip() if last_source.returncode == 0 else ""
        if not commit:
            return "no source-code checkpoint exists for the verification baseline"
        head_contract = subprocess.run(
            ["git", "show", f"HEAD:{rel}"], cwd=str(root), capture_output=True,
            timeout=20)
        source_contract = subprocess.run(
            ["git", "show", f"{commit}:{rel}"], cwd=str(root), capture_output=True,
            timeout=20)
        if head_contract.returncode != 0 or source_contract.returncode != 0:
            return "verification contract is not present in the approved source checkpoint"
        current = target.read_bytes()
        if current != head_contract.stdout:
            return "verification contract differs from HEAD (working change)"
        if head_contract.stdout != source_contract.stdout:
            return "verification contract changed after the last source-code checkpoint"
        hashlib.sha256(current).hexdigest()  # force a complete deterministic read
        return ""
    except Exception as exc:
        return f"verification baseline could not be checked: {exc}"


def strict_runtime_completion_errors(root: Path, contract: dict,
                                     bypass_reason: str = "") -> list[str]:
    policy, errors = completion_policy(root, contract)
    if errors:
        return errors
    try:
        risk_tier = active_risk_tier(root, policy)
    except ValueError as exc:
        return [problem("completion risk state", str(exc),
                        "repair STATE/GOAL before explicit close")]
    if not strict_completion(policy, risk_tier):
        return []
    if bypass_reason.strip():
        audit_error = audit_completion_bypass(
            root, policy, bypass_reason.strip(), "explicit_close")
        if audit_error:
            return [problem("completion bypass", f"audit write failed ({audit_error})",
                            "repair the audit ledger; bypasses must be durable")]
        return []

    baseline_error = verification_baseline_error(root, policy)
    if baseline_error:
        return [problem(str(policy.get("verificationContract") or "verificationContract"),
                        baseline_error,
                        "restore the last source-checkpoint contract or use an audited human bypass")]

    session_id = completion_session_id(root, policy)
    if not session_id:
        return [problem("runtime completion", "current session id is ambiguous",
                        "set ITD_SESSION_ID or write .itd-memory/.active-session.lock")]
    ledger_errors: list[str] = []
    ledger_rel = str(policy.get("runtimeSignalLedger")
                     or ".claude/completion/signals.jsonl")
    ledger = resolve_repo_path(root, ledger_rel, "runtimeSignalLedger", ledger_errors)
    if ledger is None or ledger_errors:
        return ledger_errors
    if not ledger.is_file():
        return [problem(ledger_rel, "required runtime signal ledger is missing",
                        "run the required tests/build/smoke in this session")]
    rows: list[dict] = []
    try:
        for lineno, line in enumerate(
                ledger.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                return [problem(ledger_rel,
                                f"runtime ledger line {lineno} is malformed ({exc})",
                                "repair it and rerun verification")]
            if not isinstance(row, dict):
                return [problem(ledger_rel,
                                f"runtime ledger line {lineno} is not an object",
                                "repair it and rerun verification")]
            if str(row.get("session") or "") == session_id:
                rows.append(row)
    except Exception as exc:
        return [problem(ledger_rel, f"runtime ledger unreadable ({exc})",
                        "repair the ledger and rerun verification")]
    layers = {int(x) for x in (policy.get("runtimeLayers") or [2, 3])}
    relevant = []
    for index, row in enumerate(rows, 1):
        required = ("ts", "kind", "layer", "command", "outcome", "evidence",
                    "session", "producer")
        missing = [key for key in required if key not in row]
        if missing:
            return [problem(ledger_rel,
                            "runtime signal is missing fields: " + ", ".join(missing),
                            "rerun verification through completion-signals")]
        try:
            dt.datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
        except Exception:
            return [problem(ledger_rel, "runtime signal timestamp is invalid",
                            "rerun verification through completion-signals")]
        if str(row.get("producer")) != str(policy.get("signalProducer")):
            return [problem(ledger_rel, "runtime signal producer provenance is invalid",
                            "rerun verification through completion-signals")]
        layer = row.get("layer")
        if type(layer) is not int or layer not in {0, 1, 2, 3}:
            return [problem(ledger_rel, "runtime signal layer is invalid",
                            "rerun verification through completion-signals")]
        if layer in layers:
            if not str(row.get("command") or "").strip() \
                    or not str(row.get("evidence") or "").strip():
                return [problem(ledger_rel,
                                "runtime command/evidence is empty",
                                "rerun verification through completion-signals")]
            if str(row.get("kind") or "") not in set(
                    policy.get("runtimeKinds") or []):
                return [problem(ledger_rel, "runtime signal kind is not approved",
                                "run an approved test or startup probe")]
            relevant.append(row)
    if not relevant:
        return [problem(ledger_rel, "required L2/L3 runtime evidence is missing",
                        "run the required tests/build/smoke in this session")]
    outcomes = {str(row.get("outcome") or "").lower() for row in relevant}
    if not outcomes or "" in outcomes or outcomes - {"pass", "fail"}:
        return [problem(ledger_rel, "runtime evidence outcome is ambiguous",
                        "rerun verification so every outcome is pass/fail")]
    if "fail" in outcomes:
        return [problem(ledger_rel, "runtime evidence contains a failure",
                        "fix the failure and rerun verification")]
    return []


def inside(root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve())
        return True
    except Exception:
        return False


def resolve_repo_path(root: Path, raw: str, label: str, errors: list[str]) -> Path | None:
    p = Path(str(raw or ""))
    if not raw:
        errors.append(problem(label, "path is empty", "configure a repo-relative path"))
        return None
    if p.is_absolute() or ".." in p.parts:
        errors.append(problem(label, "path escapes the repository",
                              "use a relative path without '..'"))
        return None
    target = (root / p).resolve(strict=False)
    if not inside(root, target):
        errors.append(problem(label, "resolved path escapes the repository",
                              "use a path inside the project root"))
        return None
    return target


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def is_tracked(root: Path, rel: str) -> bool:
    return git(root, "ls-files", "--error-unmatch", "--", rel).returncode == 0


def cleanup_manifest(root: Path, manifest_rel: str) -> tuple[list[str], int]:
    errors: list[str] = []
    manifest = resolve_repo_path(root, manifest_rel, "cleanupManifest", errors)
    if errors or manifest is None:
        return errors, 0
    if not manifest.exists():
        return [], 0
    try:
        data = load_json(manifest)
    except ValueError as exc:
        return [problem(str(manifest), str(exc), "repair or remove the manifest")], 0
    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list):
        return [problem(str(manifest), "artifacts must be an array",
                        "write {\"version\":1,\"artifacts\":[]}")], 0

    removed = 0
    for index, item in enumerate(artifacts):
        label = f"{manifest}:artifacts[{index}]"
        if not isinstance(item, dict):
            errors.append(problem(label, "entry is not an object", "remove the invalid entry"))
            continue
        rel = str(item.get("path") or "")
        if item.get("createdBySession") is not True:
            errors.append(problem(label, "ownership is not explicit",
                                  "set createdBySession=true only for session-created artifacts"))
            continue
        target = resolve_repo_path(root, rel, label, errors)
        if target is None:
            continue
        if is_tracked(root, rel):
            errors.append(problem(rel, "tracked paths are never cleanup targets",
                                  "remove it from the manifest; use an explicit reviewed change"))
            continue
        if not target.exists() and not target.is_symlink():
            continue  # idempotent repeat
        try:
            if target.is_symlink() or target.is_file():
                target.unlink()
                removed += 1
            elif target.is_dir():
                target.rmdir()  # empty only; recursive deletion is forbidden
                removed += 1
            else:
                errors.append(problem(rel, "unsupported artifact type",
                                      "remove it manually after inspection"))
        except OSError as exc:
            errors.append(problem(rel, f"safe cleanup refused ({exc})",
                                  "empty the directory or inspect the artifact manually"))
    return errors, removed


def run_command(root: Path, spec: dict, extra_env: dict[str, str] | None = None) -> dict:
    command = str(spec.get("command") or "").strip()
    cid = str(spec.get("id") or "command")
    timeout = int(spec.get("timeoutSeconds") or 300)
    if not command:
        return {"id": cid, "ok": False, "metric": 0.0,
                "error": problem(cid, "command is empty", "configure an executable command")}
    env = os.environ.copy()
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    try:
        proc = subprocess.run(command, cwd=str(root), shell=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"id": cid, "ok": False, "metric": 0.0,
                "error": problem(cid, f"timed out after {timeout}s",
                                 "fix the command or increase timeoutSeconds")}
    except Exception as exc:
        return {"id": cid, "ok": False, "metric": 0.0,
                "error": problem(cid, f"could not execute ({exc})", "fix the command")}

    parser = str(spec.get("passFailParser") or spec.get("metricParser")
                 or "exit_code_zero")
    expected = spec.get("expectedOutput")
    ok = proc.returncode == 0
    metric: float | None = 1.0 if ok else 0.0
    if parser == "stdout_contains":
        ok = ok and str(expected or "") in proc.stdout
        metric = 1.0 if ok else 0.0
    elif parser == "json_field_equals":
        rule = expected if isinstance(expected, dict) else {}
        parsed = parse_last_json(proc.stdout)
        ok = ok and parsed.get(str(rule.get("field") or "")) == rule.get("value")
        metric = 1.0 if ok else 0.0
    elif parser == "json_number":
        parsed = parse_last_json(proc.stdout)
        field = str(spec.get("metricField") or "score")
        try:
            metric = float(parsed[field])
        except Exception:
            ok = False
            metric = None
    elif parser == "manual_evidence":
        ok = False
        metric = None
    elif parser != "exit_code_zero":
        ok = False
        metric = None

    tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-3:])
    result = {"id": cid, "ok": bool(ok), "returncode": proc.returncode,
              "metric": metric}
    if not ok:
        result["error"] = problem(cid, tail or f"exit {proc.returncode}",
                                  "run the command directly, fix the failure, then retry")
    return result


def parse_last_json(text: str) -> dict:
    for line in reversed((text or "").splitlines()):
        try:
            data = json.loads(line)
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


def quality_report(root: Path, ledger_rel: str, max_age_override: int | None = None,
                   today: dt.date | None = None) -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    ledger = resolve_repo_path(root, ledger_rel, "qualityLedger", errors)
    if errors or ledger is None:
        return errors, []
    try:
        data = load_json(ledger)
    except ValueError as exc:
        return [problem(str(ledger), str(exc), "create and fill the quality ledger")], []
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        return [problem(str(ledger), "no module quality rows",
                        "add at least one evidence-backed module row")], []
    max_age = int(max_age_override or data.get("maxAgeDays") or 30)
    now = today or dt.date.today()
    seen: set[str] = set()
    valid: list[dict] = []
    for index, module in enumerate(modules):
        label = f"{ledger}:modules[{index}]"
        if not isinstance(module, dict):
            errors.append(problem(label, "row is not an object", "replace it with a module row"))
            continue
        missing = [field for field in QUALITY_FIELDS if field not in module]
        if missing:
            errors.append(problem(label, "missing fields: " + ", ".join(missing),
                                  "fill every quality dimension"))
            continue
        mid = str(module.get("id") or "")
        if not mid or mid in seen:
            errors.append(problem(label, "module id is empty or duplicated", "use a unique id"))
            continue
        seen.add(mid)
        grade = str(module.get("grade") or "").upper()
        if grade not in GRADES:
            errors.append(problem(mid, f"unknown grade {grade!r}", "use A, B, C, D, or F"))
            continue
        try:
            reviewed = dt.date.fromisoformat(str(module.get("reviewedAt") or ""))
        except Exception:
            errors.append(problem(mid, "reviewedAt is not ISO date", "use YYYY-MM-DD"))
            continue
        age = (now - reviewed).days
        if age > max_age:
            errors.append(problem(mid, f"quality row is stale ({age}d > {max_age}d)",
                                  "re-review the module with fresh evidence"))
        evidence = module.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(problem(mid, "evidence is empty", "attach existing repo paths"))
        else:
            for raw in evidence:
                ep = resolve_repo_path(root, str(raw), f"{mid}.evidence", errors)
                if ep is not None and not ep.exists():
                    errors.append(problem(str(raw), "evidence path does not exist",
                                          "fix the path or collect the evidence"))
        valid.append(module)
    valid.sort(key=lambda row: (WORST_FIRST.get(str(row.get("grade")), -1),
                                str(row.get("id"))))
    return errors, valid


def objective_quality_report(root: Path, scorecard_rel: str,
                             today: dt.date | None = None) -> tuple[list[str], dict]:
    errors: list[str] = []
    scorecard_path = resolve_repo_path(root, scorecard_rel, "scorecard", errors)
    if errors or scorecard_path is None:
        return errors, {}
    try:
        config = load_json(scorecard_path)
    except ValueError as exc:
        return [problem(scorecard_rel, str(exc), "repair the objective scorecard")], {}

    now = today or dt.date.today()
    ledger_rel = str(config.get("qualityLedger") or "")
    ledger_errors, ledger_modules = quality_report(root, ledger_rel, today=now)
    errors.extend(ledger_errors)
    declared = {str(row.get("id")): str(row.get("grade") or "").upper()
                for row in ledger_modules}

    thresholds = config.get("gradeThresholds")
    parsed_thresholds: dict[str, float] = {}
    if not isinstance(thresholds, dict) or set(thresholds) != GRADES:
        errors.append(problem("gradeThresholds", "must define exactly A, B, C, D, F",
                              "configure numeric thresholds for every grade"))
    else:
        try:
            parsed_thresholds = {grade: float(thresholds[grade]) for grade in GRADES}
        except Exception:
            errors.append(problem("gradeThresholds", "thresholds must be numeric",
                                  "use values from 0 to 100"))
        if parsed_thresholds and not (
                100 >= parsed_thresholds["A"] > parsed_thresholds["B"]
                > parsed_thresholds["C"] > parsed_thresholds["D"]
                > parsed_thresholds["F"] >= 0):
            errors.append(problem("gradeThresholds", "thresholds are not strictly descending",
                                  "configure A > B > C > D > F within 0..100"))

    raw_probes = config.get("probes")
    probe_specs: dict[str, dict] = {}
    if not isinstance(raw_probes, list) or not raw_probes:
        errors.append(problem("probes", "no objective probes configured",
                              "add executable evidence probes"))
    else:
        for index, spec in enumerate(raw_probes):
            label = f"probes[{index}]"
            if not isinstance(spec, dict):
                errors.append(problem(label, "probe is not an object", "replace the probe"))
                continue
            pid = str(spec.get("id") or "")
            if not pid or pid in probe_specs:
                errors.append(problem(label, "probe id is empty or duplicated",
                                      "use a unique stable id"))
                continue
            if not str(spec.get("command") or "").strip():
                errors.append(problem(pid, "probe command is empty", "configure a command"))
                continue
            try:
                attempts = int(spec.get("attempts") or 1)
            except Exception:
                attempts = 0
            if not 1 <= attempts <= 5:
                errors.append(problem(pid, "attempts must be within 1..5",
                                      "use repeated probes only for stability evidence"))
                continue
            probe_specs[pid] = spec

    probe_results: dict[str, dict] = {}

    def measure_probe(pid: str) -> dict | None:
        if pid in probe_results:
            return probe_results[pid]
        spec = probe_specs.get(pid)
        if spec is None:
            errors.append(problem(pid, "referenced probe does not exist",
                                  "add it to scorecard.probes"))
            return None
        attempts = int(spec.get("attempts") or 1)
        try:
            scale = float(spec.get("metricScale") or 1.0)
        except Exception:
            scale = 0.0
        if scale <= 0:
            errors.append(problem(pid, "metricScale must be positive", "use a value > 0"))
            return None
        rows = []
        scores = []
        for attempt in range(1, attempts + 1):
            result = run_command(root, spec)
            metric = result.get("metric")
            try:
                normalized = max(0.0, min(1.0, float(metric) / scale))
            except Exception:
                normalized = 0.0
            if not result.get("ok"):
                normalized = 0.0
            scores.append(normalized)
            rows.append({
                "attempt": attempt,
                "ok": bool(result.get("ok")),
                "returncode": result.get("returncode"),
                "metric": metric,
                "score": round(normalized * 100, 2),
                "error": result.get("error"),
            })
        measured = {
            "id": pid,
            "score": round((sum(scores) / len(scores)) * 100, 2),
            "attempts": rows,
        }
        probe_results[pid] = measured
        return measured

    raw_modules = config.get("modules")
    scored_modules = []
    if not isinstance(raw_modules, list) or not raw_modules:
        errors.append(problem("modules", "no scorecard modules configured",
                              "map quality modules to the five dimensions"))
    else:
        seen: set[str] = set()
        for index, module in enumerate(raw_modules):
            label = f"modules[{index}]"
            if not isinstance(module, dict):
                errors.append(problem(label, "module is not an object", "replace the row"))
                continue
            mid = str(module.get("id") or "")
            if not mid or mid in seen:
                errors.append(problem(label, "module id is empty or duplicated",
                                      "use a unique id matching QUALITY.json"))
                continue
            seen.add(mid)
            dimensions = module.get("dimensions")
            if not isinstance(dimensions, dict) or set(dimensions) != set(QUALITY_DIMENSIONS):
                errors.append(problem(mid, "scorecard must define exactly five quality dimensions",
                                      "configure " + ", ".join(QUALITY_DIMENSIONS)))
                continue
            dimension_rows = {}
            total_weight = 0.0
            weighted_score = 0.0
            valid_module = True
            for dimension in QUALITY_DIMENSIONS:
                rule = dimensions.get(dimension)
                if not isinstance(rule, dict):
                    errors.append(problem(f"{mid}.{dimension}", "dimension is not an object",
                                          "configure weight and probes"))
                    valid_module = False
                    continue
                try:
                    weight = float(rule.get("weight"))
                except Exception:
                    weight = -1.0
                refs = rule.get("probes")
                if weight < 0 or not isinstance(refs, list) or not refs:
                    errors.append(problem(f"{mid}.{dimension}", "invalid weight or empty probes",
                                          "use a non-negative weight and at least one probe"))
                    valid_module = False
                    continue
                measurements = [measure_probe(str(pid)) for pid in refs]
                if any(item is None for item in measurements):
                    valid_module = False
                    continue
                score = sum(item["score"] for item in measurements if item) / len(measurements)
                total_weight += weight
                weighted_score += score * weight / 100.0
                dimension_rows[dimension] = {
                    "weight": weight,
                    "score": round(score, 2),
                    "probes": [str(pid) for pid in refs],
                }
            if not valid_module:
                continue
            if abs(total_weight - 100.0) > 0.001:
                errors.append(problem(mid, f"dimension weights total {total_weight:g}, not 100",
                                      "make the five weights sum to 100"))
                continue
            score = round(weighted_score, 2)
            computed = "F"
            for grade in ("A", "B", "C", "D", "F"):
                if parsed_thresholds and score >= parsed_thresholds[grade]:
                    computed = grade
                    break
            declared_grade = declared.get(mid)
            if declared_grade is None:
                errors.append(problem(mid, "module is absent from the quality ledger",
                                      "add the same id to QUALITY.json"))
            overstated = bool(declared_grade in GRADE_POINTS
                              and GRADE_POINTS[declared_grade] > GRADE_POINTS[computed])
            try:
                minimum = float(module.get("minimumScore") or 0.0)
            except Exception:
                errors.append(problem(mid, "minimumScore must be numeric",
                                      "use a value from 0 to 100"))
                minimum = 0.0
            below_minimum = score < minimum
            if below_minimum:
                errors.append(problem(mid, f"computed score {score:g} is below minimum {minimum:g}",
                                      "repair failing probes before promotion"))
            if overstated and config.get("failOnOverstatedGrade") is True:
                errors.append(problem(mid,
                                      f"declared grade {declared_grade} exceeds computed {computed}",
                                      "lower the declared grade or repair the objective evidence"))
            scored_modules.append({
                "id": mid,
                "score": score,
                "computedGrade": computed,
                "declaredGrade": declared_grade,
                "minimumScore": minimum,
                "belowMinimum": below_minimum,
                "overstatedGrade": overstated,
                "dimensions": dimension_rows,
            })

    scored_modules.sort(key=lambda row: (row.get("score", -1), row.get("id", "")))
    report = {
        "version": 1,
        "kind": "objective-quality-score",
        "date": now.isoformat(),
        "scorecard": scorecard_rel,
        "qualityLedger": ledger_rel,
        "status": "failed" if errors else "passed",
        "modules": scored_modules,
        "probes": probe_results,
        "errors": list(dict.fromkeys(errors)),
    }
    return report["errors"], report


def debug_scan(root: Path, config: dict) -> list[str]:
    if config.get("enabled") is False:
        reason = str(config.get("disabledReason") or "").strip()
        return [] if reason else [problem("debugScan", "disabled without rationale",
                                          "set disabledReason or enable the scan")]
    paths = config.get("paths")
    patterns = config.get("patterns")
    if not isinstance(paths, list) or not paths:
        return [problem("debugScan.paths", "no scan scope configured",
                        "list source/test directories or explicitly disable with a reason")]
    if not isinstance(patterns, list) or not patterns:
        return [problem("debugScan.patterns", "no debug patterns configured",
                        "configure console/debugger/TODO patterns")]
    try:
        regexes = [re.compile(str(raw)) for raw in patterns]
    except re.error as exc:
        return [problem("debugScan.patterns", f"invalid regex ({exc})", "fix the pattern")]
    excludes = [str(x) for x in (config.get("excludeGlobs") or [])]
    errors: list[str] = []
    for raw in paths:
        target = resolve_repo_path(root, str(raw), "debugScan.paths", errors)
        if target is None:
            continue
        if not target.exists():
            errors.append(problem(str(raw), "debug scan path is missing", "fix the configured path"))
            continue
        files = [target] if target.is_file() else target.rglob("*")
        for file in files:
            if not file.is_file() or file.is_symlink():
                continue
            rel = file.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in excludes):
                continue
            try:
                if file.stat().st_size > 1_000_000:
                    continue
                text = file.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if any(rx.search(line) for rx in regexes):
                    errors.append(problem(f"{rel}:{lineno}", "debug marker remains",
                                          "remove it or add a narrowly justified excludeGlob"))
    return errors


def close_session(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    errors: list[str] = []
    try:
        contract = load_json(root / args.contract)
    except ValueError as exc:
        print(problem(args.contract, str(exc), "fill SESSION_EXIT_CONTRACT.json"))
        return 1

    errors.extend(strict_runtime_completion_errors(
        root, contract, str(args.completion_bypass_reason or "")))

    manifest = str(contract.get("cleanupManifest") or "")
    cleanup_errors, _ = cleanup_manifest(root, manifest)
    errors.extend(cleanup_errors)

    required = contract.get("requiredStateFiles")
    if not isinstance(required, list) or not required:
        errors.append(problem("requiredStateFiles", "no durable state is required",
                              "list the feature/unit state files that must exist"))
    else:
        for raw in required:
            target = resolve_repo_path(root, str(raw), "requiredStateFiles", errors)
            if target is not None and not target.exists():
                errors.append(problem(str(raw), "required state file is missing",
                                      "update the feature/unit state before closing"))

    verification_rel = str(contract.get("verificationContract") or "")
    verification_path = resolve_repo_path(root, verification_rel,
                                          "verificationContract", errors)
    commands: list[dict] = []
    if verification_path is not None:
        try:
            verification = load_json(verification_path)
            raw_commands = verification.get("commands")
            if not isinstance(raw_commands, list) or not raw_commands:
                errors.append(problem(verification_rel, "commands[] is empty",
                                      "configure executable verification commands"))
            else:
                commands = [c for c in raw_commands if isinstance(c, dict)]
        except ValueError as exc:
            errors.append(problem(verification_rel, str(exc), "repair the verification contract"))
    for spec in commands:
        result = run_command(root, spec)
        if not result["ok"]:
            errors.append(result["error"])

    startup = str(contract.get("startupProbeCommand") or "").strip()
    if not startup:
        errors.append(problem("startupProbeCommand", "standard startup path is not proved",
                              "configure a finite startup/smoke probe"))
    else:
        result = run_command(root, {"id": "startup-probe", "command": startup,
                                    "timeoutSeconds": contract.get("startupTimeoutSeconds", 120),
                                    "passFailParser": "exit_code_zero"})
        if not result["ok"]:
            errors.append(result["error"])

    errors.extend(debug_scan(root, contract.get("debugScan") or {}))
    quality_rel = str(contract.get("qualityLedger") or "")
    quality_errors, _ = quality_report(
        root, quality_rel, int(contract.get("qualityMaxAgeDays") or 30))
    errors.extend(quality_errors)

    # Verification/startup may recreate temporary outputs.  A second pass is
    # deliberate reference-count cleanup; missing paths remain a no-op.
    cleanup_errors, _ = cleanup_manifest(root, manifest)
    errors.extend(cleanup_errors)

    if contract.get("requireCleanGit") is not True:
        errors.append(problem("requireCleanGit", "clean state is not mandatory",
                              "set requireCleanGit=true"))
    else:
        status = git(root, "status", "--porcelain", "--untracked-files=all")
        if status.returncode != 0:
            errors.append(problem("git status", "could not inspect working tree",
                                  "run git status manually"))
        elif status.stdout.strip():
            changed = ", ".join(line[3:].strip() for line in status.stdout.splitlines()[:8])
            errors.append(problem("git status", f"working tree is dirty ({changed})",
                                  "commit intended work or remove only session-owned artifacts"))

    if errors:
        print("\n".join(dict.fromkeys(errors)))
        return 1
    return 0


def show_quality(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    if args.scorecard:
        errors, report = objective_quality_report(root, args.scorecard, today)
        if not report:
            report = {
                "version": 1,
                "kind": "objective-quality-score",
                "date": today.isoformat(),
                "scorecard": args.scorecard,
                "status": "failed",
                "modules": [],
                "probes": {},
                "errors": errors,
            }
        if args.record:
            atomic_json(record_path(root, "quality-score", today), report)
        if args.json:
            print(json.dumps(report or {"status": "failed", "errors": errors},
                             ensure_ascii=False, indent=2))
        else:
            for module in report.get("modules", []):
                print(f"{module['computedGrade']}  {module['id']}  {module['score']:g}")
            if errors:
                print("\n".join(errors), file=sys.stderr)
        return 1 if errors else 0

    errors, modules = quality_report(root, args.quality_path, args.max_age_days, today)
    if args.json:
        print(json.dumps({"ok": not errors, "modulesWorstFirst": modules,
                          "errors": errors}, ensure_ascii=False, indent=2))
    else:
        for module in modules:
            priorities = module.get("priorities") or []
            suffix = f" — {priorities[0]}" if priorities else ""
            print(f"{module['grade']}  {module['id']}{suffix}")
        if errors:
            print("\n".join(errors), file=sys.stderr)
    return 1 if errors else 0


def record_path(root: Path, kind: str, today: dt.date, component: str = "") -> Path:
    suffix = f"-{component}" if component else ""
    return root / ".itd-memory" / "hygiene" / f"{kind}-{today.isoformat()}{suffix}.json"


def periodic(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    errors: list[str] = []
    try:
        contract = load_json(root / args.contract)
    except ValueError as exc:
        print(problem(args.contract, str(exc), "fill SESSION_EXIT_CONTRACT.json"))
        return 1

    if args.mode == "weekly":
        cleanup_errors, removed = cleanup_manifest(
            root, str(contract.get("cleanupManifest") or ""))
        errors.extend(cleanup_errors)
        quality_errors, modules = quality_report(
            root, str(contract.get("qualityLedger") or ""),
            int(contract.get("qualityMaxAgeDays") or 30), today)
        errors.extend(quality_errors)
        specs = (contract.get("periodic") or {}).get("weeklyCommands")
        if not isinstance(specs, list) or not specs:
            errors.append(problem("periodic.weeklyCommands", "weekly full-scan is empty",
                                  "configure structural and benchmark drift checks"))
        results = []
        for spec in specs or []:
            if not isinstance(spec, dict):
                continue
            result = run_command(root, spec)
            results.append({k: result.get(k) for k in ("id", "ok", "returncode")})
            if not result["ok"]:
                errors.append(result["error"])
        record = {"version": 1, "kind": "weekly", "date": today.isoformat(),
                  "removedArtifacts": removed,
                  "lowestQualityModule": modules[0]["id"] if modules else None,
                  "commands": results, "status": "failed" if errors else "passed"}
        if args.record:
            atomic_json(record_path(root, "weekly", today), record)
    else:
        try:
            config = load_json(root / args.ablation_contract)
        except ValueError as exc:
            print(problem(args.ablation_contract, str(exc), "fill HARNESS_ABLATION.json"))
            return 1
        candidates = [c for c in (config.get("candidates") or []) if isinstance(c, dict)]
        candidate = next((c for c in candidates if c.get("id") == args.component), None)
        if candidate is None:
            errors.append(problem(args.component or "component", "ablation candidate not found",
                                  "choose an id from HARNESS_ABLATION.json"))
            results = []
            recommendation = "blocked"
        else:
            specs = candidate.get("benchmarkCommands")
            if not isinstance(specs, list) or not specs:
                errors.append(problem(args.component, "benchmarkCommands is empty",
                                      "configure a fixed benchmark before disabling the component"))
                specs = []
            disabled_env = candidate.get("disableEnv")
            if not isinstance(disabled_env, dict) or not disabled_env:
                errors.append(problem(args.component, "disableEnv is empty",
                                      "use an existing reversible kill switch"))
                disabled_env = {}
            results = []
            regression = False
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                baseline = run_command(root, spec)
                disabled = run_command(root, spec, disabled_env)
                higher = spec.get("higherIsBetter", True) is not False
                tolerance = float(spec.get("maxRegression") or 0.0)
                bm = baseline.get("metric")
                dm = disabled.get("metric")
                if not baseline["ok"]:
                    errors.append(problem(str(spec.get("id") or "benchmark"),
                                          "baseline benchmark failed",
                                          "repair the benchmark before ablation"))
                    regressed = True
                elif not disabled["ok"] or dm is None or bm is None:
                    regressed = True
                elif higher:
                    regressed = dm < bm - tolerance
                else:
                    regressed = dm > bm + tolerance
                regression = regression or regressed
                results.append({"id": spec.get("id"),
                                "baseline": {"ok": baseline["ok"], "metric": bm},
                                "disabled": {"ok": disabled["ok"], "metric": dm},
                                "regressed": regressed})
            recommendation = "restore" if regression or errors else "candidate_for_removal"
        record = {"version": 1, "kind": "monthly-ablation",
                  "date": today.isoformat(), "component": args.component,
                  "results": results, "recommendation": recommendation,
                  "humanDecision": "pending"}
        if args.record:
            atomic_json(record_path(root, "ablation", today, args.component or "unknown"),
                        record)
        if recommendation == "restore":
            errors.append(problem(args.component, "disabled benchmark regressed",
                                  "restore the component or design a lighter replacement"))

    if errors:
        print("\n".join(dict.fromkeys(errors)))
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    close = sub.add_parser("close", help="verify explicit session-close contract")
    close.add_argument("--root", default=".")
    close.add_argument("--contract", default=".itd/SESSION_EXIT_CONTRACT.json")
    close.add_argument(
        "--completion-bypass-reason", default="",
        help="explicit human reason; strict completion bypass is durably audited")
    close.set_defaults(func=close_session)

    cleanup = sub.add_parser("cleanup", help="idempotently remove manifest-owned artifacts")
    cleanup.add_argument("--root", default=".")
    cleanup.add_argument("--manifest", default=".itd-memory/session-artifacts.json")
    cleanup.add_argument("--json", action="store_true")

    quality = sub.add_parser("quality", help="validate and rank module quality rows")
    quality.add_argument("--root", default=".")
    quality.add_argument("--quality-path", default=".itd/QUALITY.json")
    quality.add_argument("--max-age-days", type=int, default=None)
    quality.add_argument("--scorecard", default="")
    quality.add_argument("--today", default="")
    quality.add_argument("--record", action="store_true")
    quality.add_argument("--json", action="store_true")
    quality.set_defaults(func=show_quality)

    cycle = sub.add_parser("periodic", help="run weekly hygiene or monthly ablation")
    cycle.add_argument("--root", default=".")
    cycle.add_argument("--mode", choices=("weekly", "monthly"), required=True)
    cycle.add_argument("--component", default="")
    cycle.add_argument("--contract", default=".itd/SESSION_EXIT_CONTRACT.json")
    cycle.add_argument("--ablation-contract", default=".itd/HARNESS_ABLATION.json")
    cycle.add_argument("--today", default="")
    cycle.add_argument("--record", action="store_true")
    cycle.set_defaults(func=periodic)
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = build_parser().parse_args()
    if args.command == "cleanup":
        errors, removed = cleanup_manifest(Path(args.root).resolve(), args.manifest)
        if args.json:
            print(json.dumps({"ok": not errors, "removed": removed, "errors": errors},
                             ensure_ascii=False))
        elif errors:
            print("\n".join(errors))
        return 1 if errors else 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
