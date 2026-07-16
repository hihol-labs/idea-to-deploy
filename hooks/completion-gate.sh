#!/usr/bin/env python3
"""
PreToolUse hook на Bash — коммит-гейт «Врата завершения» (v1.51.0, пункты 1 и 2).

ЭКСТЕРНАЛИЗАЦИЯ СУЖДЕНИЯ О ЗАВЕРШЕНИИ (пункт 1). Перед каждым `git commit`,
затрагивающим исходный код, гейт выносит суждение НЕ из уверенности агента, а из
объективного леджера runtime-сигналов (.claude/completion/signals.jsonl, который
пишет completion-signals). Трёхслойный вердикт (пункт 2, L1→L2→L3 с блокировкой
перехода) считает completion_lib.compute_verdict. Итог:

  • слой в FAIL / тесты есть, но не прогнаны  -> ВЕТО: deny + exit 2 (коммит стоп)
  • нет runtime-сигнала, strict/high-risk      -> ВЕТО: deny + exit 2
  • нет runtime-сигнала, calibrated low-risk   -> ДЕГРАДАЦИЯ: advisory, коммит идёт
  • сигналы есть, слои не красные               -> пропуск (краткое подтверждение)

Политика берётся из `.itd/COMPLETION_POLICY.json`; calibrated mode делает
активные high-risk unit'ы strict, а low-risk no-signal оставляет advisory.
Ошибка транспорта в strict mode fail-closed, в calibrated low-risk — advisory.

Область (против шума): срабатывает ТОЛЬКО когда в staged-диффе есть файлы
исходного кода. Чистые docs/config/миграции без кода гейт не трогает.

Осознанный обход: 'COMPLETION_BYPASS: <причина>' (или 'SKILL_BYPASS: <причина>')
в description. Причина обязательна и пишется в `.itd-memory/events.jsonl`;
ошибка аудита запрещает обход. Kill switch требует
`ITD_COMPLETION_BYPASS_REASON` и проходит через тот же audit trail.

Читает JSON на stdin:
  {"session_id","cwd","tool_name":"Bash","tool_input":{"command","description"}}
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_SHELL_VALUE = r'(?:"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s;&|()]+)'
_GIT_EXECUTABLE = (
    r'(?:git(?:\.exe)?|"[^"\r\n]*[\\/]git(?:\.exe)?"|'
    r"'[^'\r\n]*[\\/]git(?:\.exe)?'|[^\s;&|()]+[\\/]git(?:\.exe)?)"
)
_GIT_GLOBAL_OPTION = (
    rf'(?:-[Cc]\s+{_SHELL_VALUE}|'
    rf'--(?:git-dir|work-tree|namespace|super-prefix|config-env)'
    rf'(?:={_SHELL_VALUE}|\s+{_SHELL_VALUE})|'
    r'--exec-path(?:=' + _SHELL_VALUE + r')?|'
    r'--(?:bare|no-pager|paginate|no-replace-objects|literal-pathspecs|'
    r'no-literal-pathspecs|glob-pathspecs|noglob-pathspecs|icase-pathspecs))'
)
_ENV_ASSIGNMENT = rf'[A-Za-z_][A-Za-z0-9_]*={_SHELL_VALUE}'
_ENV_OPTION = (
    rf'(?:-(?:u|C|S)\s+{_SHELL_VALUE}|'
    rf'--(?:unset|chdir|split-string)(?:={_SHELL_VALUE}|\s+{_SHELL_VALUE})|'
    r'-[i0v]|--(?:ignore-environment|null|debug|help|version))'
)
_SUDO_OPTION = (
    rf'(?:-(?:u|g|h|p|C|D|R|r|t|T)\s+{_SHELL_VALUE}|'
    rf'--(?:user|group|host|prompt|chdir|chroot|role|type|close-from)'
    rf'(?:={_SHELL_VALUE}|\s+{_SHELL_VALUE})|-[A-Za-z]+|'
    rf'--[A-Za-z-]+(?:={_SHELL_VALUE})?)'
)
_COMMAND_WRAPPER = (
    rf'(?:(?:command(?:\s+(?:-p|--))?|builtin|nohup)\s+|'
    rf'env(?:\s+(?:{_ENV_OPTION}|{_ENV_ASSIGNMENT}))*\s+|'
    rf'sudo(?:\s+{_SUDO_OPTION})*\s+)*'
)
GIT_COMMIT_RE = re.compile(
    rf'(^|&&|\|\||[;\r\n])\s*&?\s*{_COMMAND_WRAPPER}{_GIT_EXECUTABLE}'
    rf'(?:\s+{_GIT_GLOBAL_OPTION})*\s+commit(?=\s|$|[;&|])',
    re.I,
)
SOURCE_EXT_RE = re.compile(
    r"\.(py|js|jsx|ts|tsx|go|rb|java|rs|php|c|cc|cpp|cs|kt|kts|swift|scala|ex|exs|"
    r"vue|svelte|sql)$",
    re.I,
)
SOURCE_PATHSPECS = tuple(
    item
    for ext in ("py", "js", "jsx", "ts", "tsx", "go", "rb", "java", "rs",
                "php", "c", "cc", "cpp", "cs", "kt", "kts", "swift", "scala",
                "ex", "exs", "vue", "svelte", "sql")
    for item in (f":(glob)*.{ext}", f":(glob)**/*.{ext}")
)
BYPASS_MARKER_RE = re.compile(r"(COMPLETION_BYPASS|SKILL_BYPASS)\s*:", re.I)
BYPASS_REASON_RE = re.compile(
    r"(?:COMPLETION_BYPASS|SKILL_BYPASS)\s*:\s*(\S[^\r\n]*)", re.I)
DEFAULT_POLICY = {
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


def allow(context: str | None = None) -> int:
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if context:
        out["systemMessage"] = context
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


def deny(reason: str) -> int:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(reason)
    return 2


def staged_source(cwd: Path) -> list | None:
    """Пути файлов исходного кода в staged-диффе (git diff --cached), с cwd."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--no-renames"],
            cwd=str(cwd), capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return None
        return [ln.strip() for ln in res.stdout.splitlines()
                if ln.strip() and SOURCE_EXT_RE.search(ln.strip())]
    except Exception:
        return None


def project_root(cwd: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd),
        capture_output=True, text=True, timeout=5)
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError("git project root could not be resolved")
    return Path(result.stdout.strip()).resolve()


def verification_baseline_status(cwd: Path, policy: dict) -> tuple[bool, str]:
    """Bind the verifier to the last source-code checkpoint in git history."""
    relative = Path(str(policy.get("verificationContract") or ""))
    target = (cwd / relative).resolve(strict=False)
    target.relative_to(cwd.resolve())
    if not target.is_file():
        return False, f"verification contract is missing: {relative.as_posix()}"
    rel = relative.as_posix()
    try:
        last_source = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", *SOURCE_PATHSPECS],
            cwd=str(cwd), capture_output=True, text=True, timeout=20)
        commit = last_source.stdout.strip() if last_source.returncode == 0 else ""
        if not commit:
            return False, "no source-code checkpoint exists for the verification baseline"
        head_contract = subprocess.run(
            ["git", "show", f"HEAD:{rel}"], cwd=str(cwd), capture_output=True,
            timeout=20)
        source_contract = subprocess.run(
            ["git", "show", f"{commit}:{rel}"], cwd=str(cwd), capture_output=True,
            timeout=20)
        if head_contract.returncode != 0 or source_contract.returncode != 0:
            return False, "verification contract is not present in the approved source checkpoint"
        current = target.read_bytes()
        if current != head_contract.stdout:
            return False, "verification contract differs from HEAD (staged/working change)"
        if head_contract.stdout != source_contract.stdout:
            return False, "verification contract changed after the last source-code checkpoint"
        digest = hashlib.sha256(current).hexdigest()
        return True, f"verification contract baseline sha256:{digest}"
    except Exception as exc:
        return False, f"verification baseline could not be checked: {exc}"


def validate_policy(policy: dict) -> None:
    if policy.get("mode") not in {"calibrated", "strict"}:
        raise ValueError("completion policy mode must be calibrated|strict")
    allowed_risks = {"low", "medium", "high"}
    if policy.get("defaultRiskTier") not in allowed_risks:
        raise ValueError("defaultRiskTier must be low|medium|high")
    tiers = policy.get("strictRiskTiers")
    if not isinstance(tiers, list) or "high" not in tiers \
            or any(str(x).lower() not in allowed_risks for x in tiers):
        raise ValueError("strictRiskTiers must be a list containing high")
    layers = policy.get("runtimeLayers")
    if not isinstance(layers, list) or not layers \
            or any(type(x) is not int or x not in {2, 3} for x in layers):
        raise ValueError("runtimeLayers must be a non-empty list of 2/3")
    kinds = policy.get("runtimeKinds")
    if not isinstance(kinds, list) or not kinds \
            or any(not isinstance(x, str) or not x for x in kinds):
        raise ValueError("runtimeKinds must be a non-empty string list")
    if not isinstance(policy.get("signalProducer"), str) \
            or not policy.get("signalProducer"):
        raise ValueError("signalProducer must be non-empty")
    if policy.get("verificationBaseline") != "last-source-commit":
        raise ValueError("verificationBaseline must be last-source-commit")
    if policy.get("verificationContract") != ".itd/VERIFICATION_CONTRACT.json":
        raise ValueError(
            "verificationContract must be the canonical .itd/VERIFICATION_CONTRACT.json")
    max_lock_age = policy.get("sessionLockMaxAgeSeconds")
    if type(max_lock_age) is not int or not 1 <= max_lock_age <= 3600:
        raise ValueError("sessionLockMaxAgeSeconds must be an integer within 1..3600")
    for key in ("bypassAuditLedger", "runtimeSignalLedger", "verificationContract"):
        value = policy.get(key)
        if not isinstance(value, str) or not value or Path(value).is_absolute() \
                or ".." in Path(value).parts:
            raise ValueError(f"{key} must be a safe project-relative path")


def load_policy(cwd: Path) -> dict:
    policy = dict(DEFAULT_POLICY)
    path = cwd / ".itd" / "COMPLETION_POLICY.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("COMPLETION_POLICY root must be an object")
        policy.update(data)
    mode = os.environ.get("ITD_COMPLETION_POLICY", "").strip().lower()
    if mode:
        if mode not in {"calibrated", "strict"}:
            raise ValueError("ITD_COMPLETION_POLICY must be calibrated|strict")
        policy["mode"] = mode
    validate_policy(policy)
    return policy


def active_risk_tier(cwd: Path, policy: dict) -> str:
    def read(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"{path.name} is invalid JSON: {exc}")
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} root must be an object")
        return data

    state = read(cwd / ".itd-memory" / "STATE.json")
    unit = state.get("currentUnit") or {}
    if not isinstance(unit, dict):
        raise ValueError("STATE.currentUnit must be an object")
    if unit.get("riskTier"):
        risk = str(unit["riskTier"]).lower()
        if risk not in {"low", "medium", "high"}:
            raise ValueError("STATE currentUnit.riskTier is invalid")
        return risk
    goal = read(cwd / ".itd-memory" / "GOAL.json")
    current = str(goal.get("currentUnitId") or "")
    units = goal.get("units") or []
    if not isinstance(units, list):
        raise ValueError("GOAL.units must be a list")
    for candidate in units:
        if isinstance(candidate, dict) and candidate.get("id") == current:
            if candidate.get("riskTier"):
                risk = str(candidate["riskTier"]).lower()
                if risk not in {"low", "medium", "high"}:
                    raise ValueError("GOAL unit riskTier is invalid")
                return risk
            break
    return str(policy.get("defaultRiskTier") or "medium").lower()


def strict_required(policy: dict, risk_tier: str) -> bool:
    if str(policy.get("mode") or "").lower() == "strict":
        return True
    tiers = {str(x).lower() for x in (policy.get("strictRiskTiers") or [])}
    return risk_tier in tiers


def signal_schema_error(row: dict, policy: dict) -> str:
    required = ("ts", "kind", "layer", "command", "outcome", "evidence",
                "session", "producer")
    missing = [key for key in required if key not in row]
    if missing:
        return "runtime signal is missing fields: " + ", ".join(missing)
    try:
        datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
    except Exception:
        return "runtime signal timestamp is invalid"
    if str(row.get("producer")) != str(policy.get("signalProducer")):
        return "runtime signal producer provenance is invalid"
    layer = row.get("layer")
    if type(layer) is not int or layer not in {0, 1, 2, 3}:
        return "runtime signal layer is invalid"
    if layer in set(policy.get("runtimeLayers") or []):
        if not str(row.get("command") or "").strip():
            return "runtime signal command is empty"
        if not str(row.get("evidence") or "").strip():
            return "runtime signal evidence is empty"
        if str(row.get("kind") or "") not in set(policy.get("runtimeKinds") or []):
            return "runtime signal kind is not approved"
    return ""


def read_strict_signals(cwd: Path, session_id: str, policy: dict) -> list:
    relative = Path(str(policy["runtimeSignalLedger"]))
    target = (cwd / relative).resolve(strict=False)
    target.relative_to(cwd.resolve())
    if not target.is_file():
        return []
    rows: list[dict] = []
    for lineno, line in enumerate(
            target.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            raise ValueError(f"runtime ledger line {lineno} is malformed: {exc}")
        if not isinstance(row, dict):
            raise ValueError(f"runtime ledger line {lineno} is not an object")
        if str(row.get("session") or "") == session_id:
            error = signal_schema_error(row, policy)
            if error:
                raise ValueError(f"runtime ledger line {lineno}: {error}")
            rows.append(row)
    return rows


def runtime_evidence_status(signals: list, policy: dict) -> tuple[bool, str]:
    layers = {int(x) for x in (policy.get("runtimeLayers") or [2, 3])}
    relevant = []
    for row in signals:
        try:
            layer = int(row.get("layer", 0))
        except (TypeError, ValueError):
            continue
        if layer in layers:
            relevant.append(row)
    if not relevant:
        return False, "required L2/L3 runtime signal is missing"
    outcomes = {str(row.get("outcome") or "").lower() for row in relevant}
    if not outcomes or "" in outcomes or outcomes - {"pass", "fail"}:
        return False, "runtime signal outcome is ambiguous"
    if "fail" in outcomes:
        return False, "runtime signal contains a failure"
    return True, "runtime L2/L3 evidence present"


def _last_json_object(text: str) -> dict:
    for line in reversed((text or "").splitlines()):
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def rerun_strict_verification(cwd: Path, policy: dict) -> tuple[bool, str]:
    """Execute the declared verifier at the strict completion boundary.

    The PostToolUse ledger is useful telemetry but is workspace-writable and
    therefore cannot authorize a high-risk commit by itself.  Strict mode
    reruns the executable verification contract now and binds the decision to
    the real process result.  Missing/ambiguous/manual commands fail closed.
    """
    relative = Path(str(policy.get("verificationContract") or ""))
    target = (cwd / relative).resolve(strict=False)
    target.relative_to(cwd.resolve())
    if not target.is_file():
        return False, f"verification contract is missing: {relative.as_posix()}"
    try:
        contract = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"verification contract is unreadable: {exc}"
    if not isinstance(contract, dict):
        return False, "verification contract root is not an object"
    commands = contract.get("commands")
    if not isinstance(commands, list) or not commands:
        return False, "verification contract commands[] is empty"
    if len(commands) > 20:
        return False, "verification contract has more than 20 commands"

    # Whole-gate nesting: pre-verifier git/root/baseline work is bounded below
    # 90 seconds, this executable phase gets 720 seconds, Codex transport gets
    # 840, and host registrations get 900.
    deadline = time.monotonic() + 720
    allowed_parsers = {"exit_code_zero", "stdout_contains", "json_field_equals"}
    for index, spec in enumerate(commands):
        if not isinstance(spec, dict):
            return False, f"verification command {index + 1} is not an object"
        command = str(spec.get("command") or "").strip()
        command_id = str(spec.get("id") or f"command-{index + 1}")
        parser = str(spec.get("passFailParser") or "")
        if not command:
            return False, f"verification command {command_id} is empty"
        if parser not in allowed_parsers:
            return False, f"verification command {command_id} has unsupported parser {parser!r}"
        try:
            configured_timeout = int(spec.get("timeoutSeconds"))
        except Exception:
            return False, f"verification command {command_id} has invalid timeout"
        remaining = int(deadline - time.monotonic())
        if not 1 <= configured_timeout <= 600 or remaining < 1:
            return False, f"verification command {command_id} exceeds the strict boundary budget"
        try:
            completed = subprocess.run(
                command, cwd=str(cwd), shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=min(configured_timeout, remaining), env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            return False, f"verification command {command_id} timed out"
        except Exception as exc:
            return False, f"verification command {command_id} could not run: {exc}"
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        ok = completed.returncode == 0
        expected = spec.get("expectedOutput")
        if parser == "stdout_contains":
            ok = ok and bool(str(expected or "")) and str(expected) in completed.stdout
        elif parser == "json_field_equals":
            rule = expected if isinstance(expected, dict) else {}
            parsed = _last_json_object(completed.stdout)
            ok = (ok and bool(str(rule.get("field") or ""))
                  and parsed.get(str(rule.get("field"))) == rule.get("value"))
        if not ok:
            tail = " | ".join(line.strip() for line in output.splitlines()[-3:] if line.strip())
            return False, (f"verification command {command_id} failed"
                           + (f": {tail[:500]}" if tail else f" (exit {completed.returncode})"))
    return True, f"{len(commands)} verification command(s) reran successfully"


def completion_session_id(cwd: Path, payload: dict, policy: dict) -> str:
    direct = str(payload.get("session_id") or "").strip()
    if direct:
        return direct
    for name in ("ITD_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    lock = cwd / ".itd-memory" / ".active-session.lock"
    if lock.is_file():
        data = json.loads(lock.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            try:
                timestamp = float(data.get("timestamp"))
                age = time.time() - timestamp
            except (TypeError, ValueError):
                return ""
            max_age = int(policy.get("sessionLockMaxAgeSeconds") or 600)
            if age < -60 or age > max_age:
                return ""
            return str(data.get("session") or "").strip()
    return ""


def audit_bypass(cwd: Path, payload: dict, reason: str, paths: list,
                 policy: dict, source: str) -> tuple[bool, str]:
    try:
        relative = Path(str(policy.get("bypassAuditLedger")
                            or ".itd-memory/events.jsonl"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("bypassAuditLedger escapes project")
        target = (cwd / relative).resolve(strict=False)
        target.relative_to(cwd.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        event = {
            "id": f"evt-completion-bypass-{int(now * 1_000_000)}",
            "at": now,
            "actor": "human-bypass",
            "type": "completion_bypass",
            "name": source,
            "outcome": "bypass_allowed",
            "session": completion_session_id(cwd, payload, policy)[:120] or "unknown",
            "reason": reason[:500],
            "paths": paths[:50],
        }
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True, str(target)
    except Exception as exc:
        return False, str(exc)


def strict_deny(why: str, risk_tier: str) -> int:
    return deny(
        "[COMPLETION-GATE] Strict completion boundary blocked the source commit "
        f"(risk={risk_tier}). WHY: {why}. FIX: run the required runtime "
        "verification, or use COMPLETION_BYPASS: <reason> so the exception is "
        "durably audited."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        return strict_deny(f"hook payload is malformed: {exc}", "unknown")
    if not isinstance(payload, dict):
        return strict_deny("hook payload root is not an object", "unknown")
    if payload.get("tool_name") not in {"Bash", "PowerShell"}:
        return allow()

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return strict_deny("hook tool_input is not an object", "unknown")
    cmd = tool_input.get("command") or ""
    if not isinstance(cmd, str):
        return strict_deny("hook command is not a string", "unknown")
    if not GIT_COMMIT_RE.search(cmd):
        return allow()
    try:
        cwd = project_root(Path(payload.get("cwd") or os.getcwd()))
    except Exception as exc:
        return strict_deny(f"canonical project root is unavailable: {exc}", "unknown")
    try:
        policy = load_policy(cwd)
        risk_tier = active_risk_tier(cwd, policy)
        strict = strict_required(policy, risk_tier)
    except Exception as exc:
        return strict_deny(f"completion control state is invalid: {exc}", "unknown")

    try:
        # Область: только коммиты, где есть исходный код.
        source_paths = staged_source(cwd)
        if source_paths is None:
            return strict_deny("staged source scope could not be inspected", risk_tier) \
                if strict else allow("[COMPLETION-GATE] Scope inspection unavailable; low-risk advisory.")
        if not source_paths:
            return allow()

        description = str(tool_input.get("description") or "")
        marker = BYPASS_MARKER_RE.search(description)
        if marker:
            match = BYPASS_REASON_RE.search(description)
            if not match:
                return strict_deny("bypass marker has no reason", risk_tier)
            ok, audit = audit_bypass(
                cwd, payload, match.group(1).strip(), source_paths, policy,
                marker.group(1).upper())
            if not ok:
                return strict_deny(f"bypass audit write failed: {audit}", risk_tier)
            return allow(f"[COMPLETION-GATE] Explicit bypass audited in {audit}.")

        if os.environ.get("ITD_COMPLETION_GATE", "1") == "0":
            reason = os.environ.get("ITD_COMPLETION_BYPASS_REASON", "").strip()
            if not reason:
                return strict_deny("kill switch has no ITD_COMPLETION_BYPASS_REASON",
                                   risk_tier)
            ok, audit = audit_bypass(
                cwd, payload, reason, source_paths, policy, "ITD_COMPLETION_GATE=0")
            if not ok:
                return strict_deny(f"kill-switch audit write failed: {audit}", risk_tier)
            return allow(f"[COMPLETION-GATE] Kill-switch bypass audited in {audit}.")

        if strict:
            baseline_ok, baseline_reason = verification_baseline_status(cwd, policy)
            if not baseline_ok:
                return strict_deny(baseline_reason, risk_tier)

        try:
            import completion_lib as cl
        except Exception as exc:
            if strict:
                return strict_deny(f"completion transport unavailable: {exc}", risk_tier)
            return allow("[COMPLETION-GATE] Runtime transport unavailable; low-risk advisory.")

        session_id = completion_session_id(cwd, payload, policy)
        if not session_id:
            if strict:
                return strict_deny("current session id is ambiguous", risk_tier)
            return allow("[COMPLETION-GATE] Session attribution unavailable; low-risk advisory.")
        signals = (read_strict_signals(cwd, session_id, policy)
                   if strict else cl.read_signals(cwd, session_id))
        verdict = cl.compute_verdict(cwd, signals)
        cl.write_verdict(cwd, verdict)

        if verdict.get("blocked"):
            reason = (
                "[COMPLETION-GATE] Коммит заблокирован: завершение не подтверждено "
                "runtime-сигналами.\n\n" + verdict.get("reason", "") + "\n\n"
                "Слои завершения (дёшево→дорого): L1 статика → L2 тесты → L3 e2e/smoke. "
                "Переход к следующему слою — только после зелёного предыдущего.\n"
                "Суждение вынес независимый гейт из леджера .claude/completion/, а не "
                "оценка агента: «код написан» ≠ «работает».\n\n"
                "Действия:\n"
                "  1. Устрани причину, прогони проверку заново (она попадёт в леджер).\n"
                "  2. Осознанный обход: добавь 'COMPLETION_BYPASS: <причина>' в поле "
                "description Bash-вызова коммита.\n"
                "  (Отключить гейт целиком: ITD_COMPLETION_GATE=0.)"
            )
            return deny(reason)

        if strict:
            evidence_ok, evidence_reason = runtime_evidence_status(signals, policy)
            if not evidence_ok:
                return strict_deny(evidence_reason, risk_tier)
            rerun_ok, rerun_reason = rerun_strict_verification(cwd, policy)
            if not rerun_ok:
                return strict_deny(rerun_reason, risk_tier)

        if verdict.get("degraded"):
            msg = (
                "[COMPLETION-GATE] Коммит пропущен, но завершение НЕ подтверждено "
                "объективно: за сессию нет ни одного runtime-сигнала (сборка/тесты/"
                "smoke). Если это не тривиальное изменение — прогони проверки перед "
                "тем как считать сделанным. (best-effort деградация; вето появится, "
                "как только будут сигналы провала.)"
            )
            return allow(msg)

        # Зелёный путь. Advisory-хвост (retro-2026-07-08 P2) — подсказка про
        # негативные сценарии/branch coverage; никогда не влияет на решение.
        L = verdict.get("layers", {})
        summ = " · ".join(f"L{k}:{L[k]['status']}" for k in ("1", "2", "3") if k in L)
        adv = verdict.get("advisory") or ""
        return allow(
            f"[COMPLETION-GATE] Слои подтверждены сигналами ({summ}); "
            + ("strict verifier повторно выполнен. " if strict else "")
            + "Коммит разрешён."
            + (("\n" + adv) if adv else "")
        )
    except Exception as exc:
        if strict:
            return strict_deny(f"completion evaluation failed: {exc}", risk_tier)
        return allow("[COMPLETION-GATE] Evaluation failed; calibrated advisory.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        sys.exit(strict_deny(f"completion gate crashed: {exc}", "unknown"))
