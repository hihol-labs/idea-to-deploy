#!/usr/bin/env python3
"""Exact-context review cache and verdict-aware risk-budget paydown.

The cache is reusable only while every frozen context key still matches. A
recorded failure deliberately replaces an older success for the same review
kind, so stale green evidence cannot survive a newer BLOCKED/UNVERIFIED result.
No arguments is a quiet no-op; the module is also importable by hook adapters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


INSTALL_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = INSTALL_ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
REVIEW_SKILL = INSTALL_ROOT / "skills" / "review" / "SKILL.md"
STANDARD_RUBRIC = INSTALL_ROOT / "skills" / "review" / "references" / "review-checklist.md"
META_RUBRIC = INSTALL_ROOT / "skills" / "review" / "references" / "meta-review-checklist.md"
KEY_FIELDS = (
    "repository", "baseCommit", "reviewedTree", "diffHash",
    "scopeContractHash", "acceptanceContractHash", "rubricHash",
    "methodologyVersion", "riskTier",
)
VERDICTS = {"PASSED", "PASSED_WITH_WARNINGS", "BLOCKED", "UNVERIFIED", "FAILED"}
KINDS = {"general", "security"}
RISK_TIERS = {"low", "medium", "high", "unknown"}


class CacheError(ValueError):
    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def load_policy() -> tuple[dict[str, Any], str]:
    try:
        raw = POLICY_PATH.read_bytes()
        policy = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CacheError(
            f"review cache policy is unavailable: {exc}",
            "Restore WORKING_DEADLINE_POLICY.json before reusing review evidence.",
        ) from exc
    cache = policy.get("reviewCache") or {}
    risk = policy.get("riskBudget") or {}
    if (policy.get("id") != "working-deadline-v1"
            or set(cache.get("keyFields") or []) != set(KEY_FIELDS)
            or cache.get("acceptedVerdicts") != ["PASSED"]
            or cache.get("warningVerdictRequiresDurableWarnings") is not True
            or cache.get("blockedOrUnverifiedSatisfiesGate") is not False
            or cache.get("invalidateOnKeyChange") is not True
            or risk.get("resetRequiresSuccessfulBoundVerdict") is not True
            or risk.get("reviewResets") != ["general-change-risk"]
            or risk.get("securityReviewResets") != ["security-change-risk"]
            or risk.get("generalReviewMayResetSecurity") is not False
            or risk.get("countOnlyPostGateDelta") is not True):
        raise CacheError(
            "review-cache or risk-budget policy is malformed or weakened",
            "Restore the frozen working-deadline policy; do not infer a permissive cache.",
        )
    return policy, sha256_bytes(raw)


def git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True,
        text=not binary, timeout=10,
    )
    if result.returncode != 0:
        error = result.stderr if not binary else result.stderr.decode("utf-8", "replace")
        raise CacheError(
            f"git {' '.join(args)} failed: {str(error).strip()}",
            "Repair the repository/index and rerun review against an exact candidate.",
        )
    return result.stdout


def repository_root(root: Path | str) -> Path:
    candidate = Path(root).resolve()
    value = str(git(candidate, "rev-parse", "--show-toplevel")).strip()
    if not value:
        raise CacheError("git repository root is empty", "Run review inside the target repository.")
    return Path(value).resolve()


def methodology_version() -> str:
    for manifest in (
            INSTALL_ROOT / ".claude-plugin" / "plugin.json",
            INSTALL_ROOT / ".codex-plugin" / "plugin.json"):
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except Exception:
            value = None
        if isinstance(value, str) and value:
            return value
    try:
        text = REVIEW_SKILL.read_text(encoding="utf-8")
        match = re.search(r"(?m)^\s*version:\s*([^\s]+)\s*$", text)
    except Exception:
        match = None
    if match:
        return "review-skill:" + match.group(1)
    raise CacheError(
        "methodology version cannot be resolved",
        "Restore the plugin manifest or review skill metadata before caching evidence.",
    )


def methodology_target(root: Path) -> bool:
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    return (manifest.get("name") == "idea-to-deploy"
            and (root / "skills").is_dir()
            and (root / "hooks" / "check-skills.sh").is_file())


def rubric_hash(root: Path) -> str:
    rubric = META_RUBRIC if methodology_target(root) else STANDARD_RUBRIC
    if not rubric.is_file():
        raise CacheError(
            f"review rubric is missing: {rubric}",
            "Restore the applicable binary rubric before recording review evidence.",
        )
    return sha256_file(rubric)


def detected_risk_tier(root: Path) -> str:
    goal_path = root / ".itd-memory" / "GOAL.json"
    try:
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        units = [unit for unit in goal.get("units", []) if isinstance(unit, dict)]
        current_id = str(goal.get("currentUnitId") or "")
        unit = next((item for item in units if item.get("id") == current_id), None)
        if unit is None:
            unit = next((item for item in units
                         if item.get("status") in {"in_progress", "recovery_required"}), None)
        risk = str((unit or {}).get("riskTier") or "").lower()
        if risk in RISK_TIERS - {"unknown"}:
            return risk
    except Exception:
        pass
    try:
        state = json.loads((root / ".itd-memory" / "STATE.json").read_text(encoding="utf-8"))
        risk = str(((state.get("currentUnit") or {}).get("riskTier")) or "").lower()
        if risk in RISK_TIERS - {"unknown"}:
            return risk
    except Exception:
        pass
    return "unknown"


def build_context(root: Path | str, risk_tier: str | None = None) -> dict[str, str]:
    repo = repository_root(root)
    risk = str(risk_tier or detected_risk_tier(repo)).lower()
    if risk not in RISK_TIERS:
        raise CacheError(
            f"invalid risk tier: {risk!r}",
            "Use low, medium, high, or an explicitly unresolved unknown tier.",
        )
    base = str(git(repo, "rev-parse", "HEAD")).strip()
    tree = str(git(repo, "write-tree")).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", base or "") \
            or not re.fullmatch(r"[0-9a-f]{40}", tree or ""):
        raise CacheError(
            "base commit or reviewed tree is not an exact Git object id",
            "Repair the Git repository and rerun review on the frozen staged candidate.",
        )
    diff = git(repo, "diff", "--cached", "--binary", "--full-index",
               "--no-ext-diff", base, "--", binary=True)
    assert isinstance(diff, bytes)
    return {
        "repository": repo.as_posix(),
        "baseCommit": base,
        "reviewedTree": tree,
        "diffHash": sha256_bytes(diff),
        "scopeContractHash": sha256_file(repo / ".itd" / "SCOPE_LOCK.md"),
        "acceptanceContractHash": sha256_file(
            repo / ".itd" / "ACCEPTANCE_CONTRACT.json"),
        "rubricHash": rubric_hash(repo),
        "methodologyVersion": methodology_version(),
        "riskTier": risk,
    }


def cache_path(root: Path | str) -> Path:
    repo = repository_root(root)
    memory = repo / ".itd-memory"
    if memory.is_dir():
        return memory / "review-cache.json"
    git_dir = str(git(repo, "rev-parse", "--git-dir")).strip()
    path = Path(git_dir)
    if not path.is_absolute():
        path = repo / path
    return path.resolve() / "itd-review-cache.json"


def load_cache(root: Path | str) -> dict[str, Any]:
    path = cache_path(root)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "records": {}}
    if not isinstance(value, dict) or value.get("version") != 1 \
            or not isinstance(value.get("records"), dict):
        return {"version": 1, "records": {}}
    return value


def valid_warning(value: Any) -> bool:
    return (isinstance(value, dict)
            and isinstance(value.get("summary"), str) and bool(value["summary"].strip())
            and isinstance(value.get("file"), str) and bool(value["file"].strip()))


def verdict_accepted(verdict: str, warnings: list[dict[str, Any]]) -> bool:
    if verdict == "PASSED":
        return True
    return verdict == "PASSED_WITH_WARNINGS" and bool(warnings) \
        and all(valid_warning(item) for item in warnings)


def record_matches(record: dict[str, Any], context: dict[str, str],
                   expected_kind: str = "general") -> bool:
    try:
        _, policy_digest = load_policy()
    except CacheError:
        return False
    if not isinstance(record, dict) or record.get("policySha256") != policy_digest:
        return False
    verdict = str(record.get("verdict") or "").upper()
    warnings = record.get("durableWarnings") or []
    return (record.get("accepted") is True
            and record.get("kind") == expected_kind
            and verdict_accepted(verdict, warnings)
            and record.get("context") == context)


def risk_state_path(session: str | None = None) -> Path:
    sid = session or os.environ.get("CLAUDE_SESSION_ID") or f"pid{os.getppid()}"
    return Path(tempfile.gettempdir()) / f"claude-risk-{sid}.json"


def read_risk_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    security = float(state.get("security_score", 0.0) or 0.0)
    total = float(state.get("risk_score", 0.0) or 0.0)
    general = float(state.get("general_score", max(0.0, total - security)) or 0.0)
    state.update({
        "general_score": round(max(0.0, general), 2),
        "security_score": round(max(0.0, security), 2),
        "risk_score": round(max(0.0, general) + max(0.0, security), 2),
        "last_escalation_score": round(
            float(state.get("last_escalation_score", 0.0) or 0.0), 2),
        "escalations": int(state.get("escalations", 0) or 0),
    })
    return state


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def pay_down_risk(kind: str, session: str | None, gate_id: str) -> None:
    path = risk_state_path(session)
    state = read_risk_state(path)
    bucket = "general_score" if kind == "general" else "security_score"
    state[bucket] = 0.0
    state["risk_score"] = round(
        float(state.get("general_score", 0.0))
        + float(state.get("security_score", 0.0)), 2)
    # A successful gate starts a new delta window without erasing the other
    # bucket. Anchoring at the complete residual score prevents pre-gate risk
    # from being counted again when the old escalation baseline lagged behind
    # the current total.
    state["last_escalation_score"] = state["risk_score"]
    state["paid_down_at"] = time.time()
    state["last_gate_kind"] = kind
    state["last_gate_id"] = gate_id
    write_json_atomic(path, state)


def record_review(root: Path | str, *, verdict: str, kind: str = "general",
                  warnings: list[dict[str, Any]] | None = None,
                  risk_tier: str | None = None,
                  session: str | None = None) -> tuple[bool, dict[str, Any]]:
    _, policy_digest = load_policy()
    normalized_verdict = str(verdict or "").strip().upper()
    normalized_kind = str(kind or "").strip().lower()
    if normalized_verdict not in VERDICTS:
        raise CacheError(
            f"unsupported verdict: {normalized_verdict!r}",
            "Use PASSED, PASSED_WITH_WARNINGS, BLOCKED, UNVERIFIED, or FAILED.",
        )
    if normalized_kind not in KINDS:
        raise CacheError(
            f"unsupported review kind: {normalized_kind!r}",
            "Use general for /review or security for /security-audit.",
        )
    warning_list = list(warnings or [])
    context = build_context(root, risk_tier)
    accepted = verdict_accepted(normalized_verdict, warning_list)
    recorded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gate_material = json.dumps({
        "context": context, "verdict": normalized_verdict,
        "kind": normalized_kind, "warnings": warning_list,
        "recordedAt": recorded_at,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    record = {
        "context": context,
        "verdict": normalized_verdict,
        "kind": normalized_kind,
        "durableWarnings": warning_list,
        "accepted": accepted,
        "recordedAt": recorded_at,
        "gateId": sha256_bytes(gate_material),
        "policySha256": policy_digest,
    }
    cache = load_cache(root)
    cache["records"][normalized_kind] = record
    write_json_atomic(cache_path(root), cache)
    if accepted:
        pay_down_risk(normalized_kind, session, record["gateId"])
    return accepted, record


def cache_allows(root: Path | str, risk_tier: str | None = None,
                 kind: str = "general") -> bool:
    try:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind not in KINDS:
            return False
        cache = load_cache(root)
        record = (cache.get("records") or {}).get(normalized_kind)
        return record_matches(
            record, build_context(root, risk_tier), normalized_kind)
    except Exception:
        return False


def fail(why: str, fix: str) -> int:
    print(json.dumps({"status": "FAIL", "why": why, "fix": fix},
                     ensure_ascii=False, sort_keys=True))
    return 1


def warning_args(values: list[str]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for value in values:
        file_name, separator, summary = value.rpartition(": ")
        if separator and file_name.strip() and summary.strip():
            warnings.append({"file": file_name.strip(), "summary": summary.strip()})
    return warnings


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        return 0
    parser = argparse.ArgumentParser(description="Exact-context review cache")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "check", "context"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", type=Path, default=Path.cwd())
        cmd.add_argument("--risk-tier", choices=sorted(RISK_TIERS))
        if name in {"record", "check"}:
            cmd.add_argument("--kind", choices=sorted(KINDS), default="general")
        if name == "record":
            cmd.add_argument("--verdict", required=True)
            cmd.add_argument("--warning", action="append", default=[])
            cmd.add_argument("--session")
    args = parser.parse_args(args_list)
    try:
        if args.command == "context":
            print(json.dumps(build_context(args.root, args.risk_tier),
                             ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "check":
            if cache_allows(args.root, args.risk_tier, args.kind):
                return 0
            return fail(
                f"no successful {args.kind} review cache matches the exact current context",
                "Run the matching review for the current base/tree/diff/contracts/rubric/version/risk tier.",
            )
        accepted, record = record_review(
            args.root, verdict=args.verdict, kind=args.kind,
            warnings=warning_args(args.warning), risk_tier=args.risk_tier,
            session=args.session)
        if accepted:
            return 0
        return fail(
            f"verdict {record['verdict']} does not satisfy the reusable review gate",
            "Resolve blocking findings and record a successful bound verdict; warnings must be durable.",
        )
    except CacheError as exc:
        return fail(exc.why, exc.fix)
    except Exception as exc:
        return fail(
            f"unexpected review-cache error: {exc}",
            "Inspect the repository context and retry; do not reuse unverifiable evidence.",
        )


if __name__ == "__main__":
    raise SystemExit(main())
