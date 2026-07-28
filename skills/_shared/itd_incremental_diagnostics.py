#!/usr/bin/env python3
"""Run opt-in advisory diagnostics and append privacy-safe observed telemetry."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any


SAFE_ENV_KEYS = {
    "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR",
}
RESULT_KEYS = {
    "index", "exitCode", "timedOut", "durationMs",
    "stdoutSha256", "stderrSha256", "launchErrorSha256",
}
DIAGNOSTIC_STATE_PREFIX = pathlib.PurePosixPath(".itd-memory/diagnostics")


class DiagnosticError(ValueError):
    """Invalid diagnostic configuration or filesystem boundary."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def is_link_or_reparse(path: pathlib.Path) -> bool:
    if path.is_symlink():
        return True
    junction_probe = getattr(path, "is_junction", None)
    try:
        if callable(junction_probe) and junction_probe():
            return True
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except (FileNotFoundError, OSError):
        return False
    return bool(attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def canonical_relative(raw: object, label: str) -> pathlib.PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\0" in raw or ":" in raw:
        raise DiagnosticError(f"{label} must be a canonical portable relative path")
    relative = pathlib.PurePosixPath(raw)
    if (relative.is_absolute() or ".." in relative.parts
            or relative.as_posix() != raw or not relative.parts):
        raise DiagnosticError(f"{label} must stay inside the project root")
    return relative


def safe_project_path(root: pathlib.Path, raw: object, label: str,
                      *, require_file: bool = False) -> pathlib.Path:
    relative = canonical_relative(raw, label)
    candidate = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.exists() and is_link_or_reparse(cursor):
            raise DiagnosticError(f"{label} contains a symlink/reparse component")
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise DiagnosticError(f"{label} escapes the project root") from exc
    if require_file and not candidate.is_file():
        raise DiagnosticError(f"{label} is missing or is not a regular file")
    return candidate


def diagnostic_state_path(root: pathlib.Path, raw: object, label: str) -> pathlib.Path:
    relative = canonical_relative(raw, label)
    if (len(relative.parts) <= len(DIAGNOSTIC_STATE_PREFIX.parts)
            or relative.parts[:len(DIAGNOSTIC_STATE_PREFIX.parts)]
            != DIAGNOSTIC_STATE_PREFIX.parts):
        raise DiagnosticError(
            f"{label} must stay under .itd-memory/diagnostics/")
    return safe_project_path(root, relative.as_posix(), label)


def require_enabled_contract_location(root: pathlib.Path,
                                      contract_path: pathlib.Path) -> None:
    supplied = (contract_path if contract_path.is_absolute()
                else pathlib.Path.cwd() / contract_path)
    if is_link_or_reparse(supplied) or not supplied.is_file():
        raise DiagnosticError(
            "enabled diagnostic contract must be a regular non-link file")
    try:
        relative = supplied.resolve(strict=True).relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise DiagnosticError(
            "enabled diagnostic contract must be a project-local regular file") from exc
    cursor = root.resolve()
    for part in relative.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor):
            raise DiagnosticError(
                "enabled diagnostic contract contains a symlink/reparse component")
    if not supplied.is_file():
        raise DiagnosticError("enabled diagnostic contract is not a regular file")


def changed_input(root: pathlib.Path, raw: pathlib.Path) -> dict[str, str]:
    candidate = raw if raw.is_absolute() else root / raw
    lexical = pathlib.Path(os.path.abspath(candidate))
    try:
        lexical_relative = lexical.relative_to(root.resolve())
    except ValueError as exc:
        raise DiagnosticError(f"changed input escapes the project root: {raw}") from exc
    cursor = root.resolve()
    for part in lexical_relative.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor):
            raise DiagnosticError(
                f"changed input contains a symlink/reparse component: {raw}")
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise DiagnosticError(f"changed input escapes or is missing: {raw}") from exc
    cursor = root.resolve()
    for part in relative.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor):
            raise DiagnosticError(f"changed input contains a symlink/reparse component: {raw}")
    if not resolved.is_file():
        raise DiagnosticError(f"changed input is not a regular file: {raw}")
    return {"path": relative.as_posix(), "sha256": sha256_file(resolved)}


def load_contract(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"diagnostic contract is unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise DiagnosticError("diagnostic contract must be a version-1 object")
    if (value.get("advisory") is not True
            or value.get("completionEvidence") is not False
            or value.get("measurement") != "host-observed"):
        raise DiagnosticError(
            "diagnostics must remain advisory, host-observed, and non-acceptance")
    if not isinstance(value.get("enabled"), bool):
        raise DiagnosticError("diagnostic enabled flag must be boolean")
    for field, minimum, maximum in (
            ("timeoutSeconds", 0.01, 600),
            ("cooldownSeconds", 0, 86400),
            ("cacheTtlSeconds", 0, 604800)):
        number = value.get(field)
        if not isinstance(number, (int, float)) or isinstance(number, bool) \
                or not minimum <= float(number) <= maximum:
            raise DiagnosticError(f"{field} is outside its bounded range")
    return value, sha256_bytes(raw)


def commands_from(contract: dict[str, Any]) -> list[list[str]]:
    rows = contract.get("commands")
    if not isinstance(rows, list):
        raise DiagnosticError("commands must be an array")
    commands: list[list[str]] = []
    for row in rows:
        if (not isinstance(row, list) or not row
                or not all(isinstance(item, str) and item and "\0" not in item
                           for item in row)):
            raise DiagnosticError("each command must be an explicit nonempty argv array")
        commands.append(list(row))
    if contract["enabled"] and not commands:
        raise DiagnosticError("enabled diagnostics require at least one argv command")
    return commands


def validated_result(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value) <= RESULT_KEYS:
        raise DiagnosticError("diagnostic cache contains an unknown result field")
    if not isinstance(value.get("index"), int) or value["index"] < 0:
        raise DiagnosticError("diagnostic cache result index is invalid")
    if not isinstance(value.get("timedOut"), bool):
        raise DiagnosticError("diagnostic cache timedOut flag is invalid")
    if not isinstance(value.get("durationMs"), int) or value["durationMs"] < 0:
        raise DiagnosticError("diagnostic cache duration is invalid")
    exit_code = value.get("exitCode")
    if exit_code is not None and not isinstance(exit_code, int):
        raise DiagnosticError("diagnostic cache exit code is invalid")
    digest_fields = {"stdoutSha256", "stderrSha256", "launchErrorSha256"}
    for field in digest_fields & set(value):
        digest = value[field]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)):
            raise DiagnosticError(f"diagnostic cache {field} is invalid")
    return dict(value)


def load_cache(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "entries": {}, "lastExecutionEpoch": 0}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError(f"diagnostic cache is unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1 \
            or not isinstance(value.get("entries"), dict):
        raise DiagnosticError("diagnostic cache schema is invalid")
    last_execution = value.get("lastExecutionEpoch", 0)
    if (not isinstance(last_execution, (int, float))
            or isinstance(last_execution, bool)
            or not math.isfinite(float(last_execution))
            or float(last_execution) < 0):
        raise DiagnosticError("diagnostic cache lastExecutionEpoch is invalid")
    entries: dict[str, Any] = {}
    for key, entry in value["entries"].items():
        if (not isinstance(key, str) or len(key) != 64
                or any(character not in "0123456789abcdef" for character in key)
                or not isinstance(entry, dict)):
            raise DiagnosticError("diagnostic cache entry key/schema is invalid")
        recorded = entry.get("recordedAtEpoch")
        results = entry.get("results")
        command_count = entry.get("commandCount")
        if (not isinstance(recorded, (int, float))
                or isinstance(recorded, bool)
                or not math.isfinite(float(recorded))
                or float(recorded) < 0
                or not isinstance(results, list)
                or not isinstance(command_count, int)
                or isinstance(command_count, bool)
                or command_count <= 0):
            raise DiagnosticError("diagnostic cache entry timestamp/results are invalid")
        validated = [validated_result(row) for row in results]
        if (len(validated) > command_count
                or [row["index"] for row in validated] != list(range(len(validated)))):
            raise DiagnosticError(
                "diagnostic cache result indexes are not bound to its command count")
        entries[key] = {
            "recordedAtEpoch": float(recorded),
            "commandCount": command_count,
            "results": validated,
        }
    return {
        "version": 1,
        "entries": entries,
        "lastExecutionEpoch": float(last_execution),
    }


def write_cache(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = pathlib.Path(raw)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def append_record(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def cache_key(contract_hash: str, changed: list[dict[str, str]],
              commands: list[list[str]]) -> str:
    material = json.dumps({
        "contractSha256": contract_hash,
        "changed": changed,
        "commands": commands,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(material)


def command_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() in SAFE_ENV_KEYS
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, timeout=10, shell=False)
        except (OSError, subprocess.SubprocessError):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()


def result_payload(status: str, *, executed: bool, key: str,
                   duration_ms: int, results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": status,
        "advisory": True,
        "completionEvidence": False,
        "measurement": "host-observed",
        "commandExecuted": executed,
        "cacheKey": key,
        "durationMs": duration_ms,
        "results": results,
    }


def run_diagnostics(root: pathlib.Path, contract_path: pathlib.Path,
                    changed_paths: list[pathlib.Path]) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise DiagnosticError("project root is not a directory")
    started = time.monotonic()
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    supplied_contract = (contract_path if contract_path.is_absolute()
                         else pathlib.Path.cwd() / contract_path)
    contract, contract_hash = load_contract(supplied_contract)
    if contract["enabled"]:
        require_enabled_contract_location(root, supplied_contract)
    commands = commands_from(contract)
    changed = sorted(
        (changed_input(root, item) for item in changed_paths),
        key=lambda row: row["path"])
    if not changed:
        raise DiagnosticError("at least one changed file is required")
    telemetry = diagnostic_state_path(
        root, contract.get("telemetryPath"), "telemetryPath")
    cache_path = diagnostic_state_path(root, contract.get("cachePath"), "cachePath")
    if cache_path.resolve(strict=False) == telemetry.resolve(strict=False):
        raise DiagnosticError("cachePath and telemetryPath must be distinct")
    key = cache_key(contract_hash, changed, commands)
    cache = load_cache(cache_path)
    now = time.time()

    if not contract["enabled"]:
        payload = result_payload(
            "disabled", executed=False, key=key,
            duration_ms=max(0, round((time.monotonic() - started) * 1000)), results=[])
    else:
        entry = (cache.get("entries") or {}).get(key)
        age = now - float((entry or {}).get("recordedAtEpoch", 0) or 0)
        if entry and entry.get("commandCount") != len(commands):
            raise DiagnosticError(
                "diagnostic cache commandCount does not match the current profile")
        if entry and 0 <= age <= float(contract["cacheTtlSeconds"]):
            payload = result_payload(
                "cached", executed=False, key=key,
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                results=list(entry.get("results") or []))
        elif (float(contract["cooldownSeconds"]) > 0
              and 0 <= now - float(cache.get("lastExecutionEpoch", 0) or 0)
              < float(contract["cooldownSeconds"])):
            payload = result_payload(
                "cooldown", executed=False, key=key,
                duration_ms=max(0, round((time.monotonic() - started) * 1000)), results=[])
        else:
            results: list[dict[str, Any]] = []
            timed_out = False
            for index, argv in enumerate(commands):
                command_started = time.monotonic()
                try:
                    process_options: dict[str, Any] = {}
                    if os.name == "nt":
                        process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                    else:
                        process_options["start_new_session"] = True
                    process = subprocess.Popen(
                        argv, cwd=str(root), env=command_environment(),
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        shell=False, **process_options)
                    stdout, stderr = process.communicate(
                        timeout=float(contract["timeoutSeconds"]))
                    row = {
                        "index": index,
                        "exitCode": process.returncode,
                        "timedOut": False,
                        "durationMs": max(
                            0, round((time.monotonic() - command_started) * 1000)),
                        "stdoutSha256": sha256_bytes(stdout),
                        "stderrSha256": sha256_bytes(stderr),
                    }
                except subprocess.TimeoutExpired as exc:
                    timed_out = True
                    terminate_process_tree(process)
                    stdout, stderr = process.communicate()
                    row = {
                        "index": index,
                        "exitCode": None,
                        "timedOut": True,
                        "durationMs": max(
                            0, round((time.monotonic() - command_started) * 1000)),
                        "stdoutSha256": sha256_bytes(stdout or exc.stdout or b""),
                        "stderrSha256": sha256_bytes(stderr or exc.stderr or b""),
                    }
                except OSError as exc:
                    row = {
                        "index": index,
                        "exitCode": None,
                        "timedOut": False,
                        "launchErrorSha256": sha256_bytes(str(exc).encode("utf-8")),
                        "durationMs": max(
                            0, round((time.monotonic() - command_started) * 1000)),
                    }
                results.append(row)
                if timed_out:
                    break
            payload = result_payload(
                "timed_out" if timed_out else "completed",
                executed=True, key=key,
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                results=results)
            cache.setdefault("entries", {})[key] = {
                "recordedAtEpoch": now,
                "commandCount": len(commands),
                "results": results,
            }
            cache["lastExecutionEpoch"] = now
            write_cache(cache_path, cache)

    record = {
        "version": 1,
        "observedAt": observed_at,
        "measurement": "host-observed",
        "status": payload["status"],
        "advisory": True,
        "completionEvidence": False,
        "commandExecuted": payload["commandExecuted"],
        "durationMs": payload["durationMs"],
        "cacheKey": key,
        "changed": changed,
        "results": payload["results"],
    }
    append_record(telemetry, record)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run opt-in incremental diagnostics.")
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--root", type=pathlib.Path, required=True)
    run.add_argument("--contract", type=pathlib.Path, required=True)
    run.add_argument("--changed", type=pathlib.Path, action="append", required=True)
    args = parser.parse_args()
    try:
        result = run_diagnostics(args.root, args.contract, args.changed)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (DiagnosticError, OSError) as exc:
        print(json.dumps({
            "status": "invalid",
            "why": str(exc),
            "fix": "repair the project contract/path boundary; diagnostics stay disabled",
            "advisory": True,
            "completionEvidence": False,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
