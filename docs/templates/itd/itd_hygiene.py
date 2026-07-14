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
import json
import os
import re
import subprocess
import sys
from pathlib import Path


GRADES = {"A", "B", "C", "D", "F"}
WORST_FIRST = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
QUALITY_FIELDS = (
    "id", "grade", "verification", "agentUnderstandable", "testStability",
    "architectureBoundaries", "codeConventions", "reviewedAt", "evidence",
    "priorities",
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
    errors, modules = quality_report(root, args.quality_path, args.max_age_days)
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
    close.set_defaults(func=close_session)

    cleanup = sub.add_parser("cleanup", help="idempotently remove manifest-owned artifacts")
    cleanup.add_argument("--root", default=".")
    cleanup.add_argument("--manifest", default=".itd-memory/session-artifacts.json")
    cleanup.add_argument("--json", action="store_true")

    quality = sub.add_parser("quality", help="validate and rank module quality rows")
    quality.add_argument("--root", default=".")
    quality.add_argument("--quality-path", default=".itd/QUALITY.json")
    quality.add_argument("--max-age-days", type=int, default=None)
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
