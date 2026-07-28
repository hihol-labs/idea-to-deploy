#!/usr/bin/env python3
"""Behavioral and mutation verification for incremental diagnostics."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "_shared" / "itd_incremental_diagnostics.py"
TEMPLATE = ROOT / "docs" / "templates" / "itd" / "INCREMENTAL_DIAGNOSTICS_CONTRACT.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def invoke(root: pathlib.Path, contract: pathlib.Path, changed: pathlib.Path
           ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "run", "--root", str(root),
         "--contract", str(contract), "--changed", str(changed)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30)


def write_contract(path: pathlib.Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> int:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    require(template["enabled"] is False
            and template["advisory"] is True
            and template["completionEvidence"] is False
            and template["measurement"] == "host-observed",
            "template must remain default-off, advisory, and non-acceptance")
    cases = 0
    with tempfile.TemporaryDirectory(prefix="itd-diagnostic-unit-") as raw:
        fixture = pathlib.Path(raw)
        changed = fixture / "changed.py"
        changed.write_text("value = 1\n", encoding="utf-8")
        contract_path = fixture / "diagnostics.json"
        write_contract(contract_path, template)

        disabled = invoke(fixture, contract_path, changed)
        require(disabled.returncode == 0, disabled.stderr)
        disabled_value = json.loads(disabled.stdout)
        require(disabled_value["status"] == "disabled"
                and disabled_value["commandExecuted"] is False,
                "default-off run must execute no command")
        telemetry = fixture / ".itd-memory" / "diagnostics" / "telemetry.jsonl"
        first_telemetry = telemetry.read_bytes()
        require(len(first_telemetry.splitlines()) == 1, "disabled run must append telemetry")
        cases += 1

        probe = fixture / "probe.py"
        probe.write_text(
            "import json, pathlib, sys\n"
            "p=pathlib.Path('calls.json')\n"
            "rows=json.loads(p.read_text()) if p.exists() else []\n"
            "rows.append(sys.argv[1:])\n"
            "p.write_text(json.dumps(rows))\n",
            encoding="utf-8")
        enabled = dict(template)
        enabled.update({
            "enabled": True,
            "cooldownSeconds": 60,
            "commands": [[sys.executable, str(probe),
                          "literal;touch", "SHOULD_NOT_EXIST"]],
        })
        write_contract(contract_path, enabled)
        completed = invoke(fixture, contract_path, changed)
        require(completed.returncode == 0, completed.stderr)
        completed_value = json.loads(completed.stdout)
        require(completed_value["status"] == "completed"
                and completed_value["advisory"] is True
                and completed_value["completionEvidence"] is False,
                "enabled result must remain advisory")
        require(json.loads((fixture / "calls.json").read_text()) ==
                [["literal;touch", "SHOULD_NOT_EXIST"]]
                and not (fixture / "SHOULD_NOT_EXIST").exists(),
                "argv must execute without shell interpolation")
        cases += 1

        cached = invoke(fixture, contract_path, changed)
        require(cached.returncode == 0 and json.loads(cached.stdout)["status"] == "cached",
                "identical content must use the cache before cooldown")
        require(len(json.loads((fixture / "calls.json").read_text())) == 1,
                "cache hit must not execute the command")
        require(telemetry.read_bytes().startswith(first_telemetry)
                and len(telemetry.read_bytes().splitlines()) == 3,
                "telemetry must be append-only across disabled/run/cache")
        cases += 1

        changed.write_text("value = 2\n", encoding="utf-8")
        cooldown = invoke(fixture, contract_path, changed)
        require(cooldown.returncode == 0
                and json.loads(cooldown.stdout)["status"] == "cooldown",
                "changed cache key within cooldown must not execute")
        require(len(json.loads((fixture / "calls.json").read_text())) == 1,
                "cooldown must suppress execution")
        cases += 1

        failure = dict(enabled)
        failure.update({
            "cooldownSeconds": 0,
            "commands": [[sys.executable, "-c",
                          "import sys;print('PRIVATE');sys.exit(7)"]],
        })
        write_contract(contract_path, failure)
        failed_command = invoke(fixture, contract_path, changed)
        failure_value = json.loads(failed_command.stdout)
        require(failed_command.returncode == 0
                and failure_value["status"] == "completed"
                and failure_value["results"][0]["exitCode"] == 7,
                "diagnostic command failure must be observed but advisory")
        require("PRIVATE" not in failed_command.stdout
                and b"PRIVATE" not in telemetry.read_bytes(),
                "raw diagnostic output must not enter result or telemetry")
        cases += 1

        timeout_contract = dict(failure)
        timeout_contract.update({
            "timeoutSeconds": 0.05,
            "commands": [[sys.executable, "-c", "import time;time.sleep(2)"]],
        })
        write_contract(contract_path, timeout_contract)
        timed = invoke(fixture, contract_path, changed)
        timed_value = json.loads(timed.stdout)
        require(timed.returncode == 0 and timed_value["status"] == "timed_out"
                and timed_value["results"][0]["timedOut"] is True,
                "timeout must be bounded and advisory")
        cases += 1

        child_code = (
            "import pathlib,time;"
            "time.sleep(.4);"
            "pathlib.Path('CHILD_SURVIVED').write_text('unsafe')")
        parent_code = (
            "import subprocess,sys,time;"
            f"subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
            "time.sleep(5)")
        tree_timeout = dict(timeout_contract)
        tree_timeout["commands"] = [[sys.executable, "-c", parent_code]]
        write_contract(contract_path, tree_timeout)
        killed_tree = invoke(fixture, contract_path, changed)
        time.sleep(0.7)
        require(killed_tree.returncode == 0
                and json.loads(killed_tree.stdout)["status"] == "timed_out"
                and not (fixture / "CHILD_SURVIVED").exists(),
                "timeout must terminate and reap the full diagnostic process tree")
        cases += 1

        outside = pathlib.Path(raw).parent / ("outside-" + pathlib.Path(raw).name)
        outside.write_text("outside\n", encoding="utf-8")
        escaped = invoke(fixture, contract_path, outside)
        require(escaped.returncode != 0
                and json.loads(escaped.stdout)["status"] == "invalid",
                "out-of-root changed input must fail closed")
        outside.unlink()
        cases += 1

        malformed = dict(template)
        malformed.update({"enabled": True, "commands": ["python -c pass"]})
        write_contract(contract_path, malformed)
        invalid_command = invoke(fixture, contract_path, changed)
        require(invalid_command.returncode != 0,
                "shell-string command must fail closed")
        cases += 1

        weakened = dict(template)
        weakened["completionEvidence"] = True
        write_contract(contract_path, weakened)
        invalid_authority = invoke(fixture, contract_path, changed)
        require(invalid_authority.returncode != 0,
                "diagnostics cannot become completion evidence")
        cases += 1

        outside_cache = dict(enabled)
        outside_cache.update({
            "cooldownSeconds": 0,
            "cachePath": "important.txt",
            "commands": [[sys.executable, "-c", "pass"]],
        })
        important = fixture / "important.txt"
        important.write_text("preserve\n", encoding="utf-8")
        write_contract(contract_path, outside_cache)
        denied_cache_path = invoke(fixture, contract_path, changed)
        require(denied_cache_path.returncode != 0
                and important.read_text(encoding="utf-8") == "preserve\n",
                "cache writes must stay under .itd-memory/diagnostics")
        cases += 1

        tampered = fixture / ".itd-memory" / "diagnostics" / "cache.json"
        tampered.parent.mkdir(parents=True, exist_ok=True)
        tampered.write_text(json.dumps({
            "version": 1,
            "lastExecutionEpoch": time.time(),
            "entries": {
                "a" * 64: {
                    "recordedAtEpoch": time.time(),
                    "commandCount": 1,
                    "results": [{"index": 0, "stdout": "PRIVATE-CACHE-PAYLOAD"}],
                }
            },
        }), encoding="utf-8")
        safe_again = dict(enabled)
        safe_again.update({"cooldownSeconds": 0})
        write_contract(contract_path, safe_again)
        poisoned_cache = invoke(fixture, contract_path, changed)
        require(poisoned_cache.returncode != 0
                and "PRIVATE-CACHE-PAYLOAD" not in poisoned_cache.stdout
                and b"PRIVATE-CACHE-PAYLOAD" not in telemetry.read_bytes(),
                "tampered cache must fail closed without entering telemetry")
        cases += 1

        tampered.write_bytes(b"\xff\xfeinvalid")
        invalid_cache_encoding = invoke(fixture, contract_path, changed)
        require(invalid_cache_encoding.returncode != 0,
                "non-UTF-8 cache must fail closed")
        cases += 1
        tampered.unlink()

        same_state_path = dict(safe_again)
        same_state_path["telemetryPath"] = same_state_path["cachePath"]
        write_contract(contract_path, same_state_path)
        colliding_state = invoke(fixture, contract_path, changed)
        require(colliding_state.returncode != 0,
                "cache and append-only telemetry paths must be distinct")
        cases += 1

        tampered.write_text(json.dumps({
            "version": 1,
            "lastExecutionEpoch": time.time(),
            "entries": {
                "b" * 64: {
                    "recordedAtEpoch": time.time(),
                    "commandCount": 1,
                    "results": [{
                        "index": 999,
                        "exitCode": 0,
                        "timedOut": False,
                        "durationMs": 1,
                        "stdoutSha256": "0" * 64,
                        "stderrSha256": "0" * 64,
                    }],
                }
            },
        }), encoding="utf-8")
        write_contract(contract_path, safe_again)
        forged_index = invoke(fixture, contract_path, changed)
        require(forged_index.returncode != 0,
                "cached result indexes must bind to the configured command count")
        tampered.unlink()
        cases += 1

        write_contract(contract_path, safe_again)
        primed = invoke(fixture, contract_path, changed)
        require(primed.returncode == 0
                and json.loads(primed.stdout)["status"] == "completed",
                "cache-binding fixture must prime successfully")
        cache_value = json.loads(tampered.read_text(encoding="utf-8"))
        current_key = json.loads(primed.stdout)["cacheKey"]
        original_row = cache_value["entries"][current_key]["results"][0]
        second_row = dict(original_row)
        second_row["index"] = 1
        cache_value["entries"][current_key]["commandCount"] = 2
        cache_value["entries"][current_key]["results"] = [original_row, second_row]
        tampered.write_text(json.dumps(cache_value), encoding="utf-8")
        mismatched_profile = invoke(fixture, contract_path, changed)
        require(mismatched_profile.returncode != 0,
                "cache commandCount must equal the current argv profile")
        tampered.unlink()
        cases += 1

        external_contract = pathlib.Path(raw).parent / (
            "external-contract-" + pathlib.Path(raw).name + ".json")
        write_contract(external_contract, safe_again)
        external_enabled = invoke(fixture, external_contract, changed)
        require(external_enabled.returncode != 0,
                "enabled contract must be a project-local regular file")
        external_contract.unlink()
        cases += 1

        write_contract(contract_path, safe_again)
        contract_link = fixture / "contract-link.json"
        try:
            os.symlink(contract_path.name, contract_link)
        except (OSError, NotImplementedError):
            pass
        else:
            linked_contract = invoke(fixture, contract_link, changed)
            require(linked_contract.returncode != 0,
                    "enabled contract symlink must fail closed before resolve")
            contract_link.unlink()
            cases += 1

        changed_link = fixture / "changed-link.py"
        try:
            os.symlink(changed.name, changed_link)
        except (OSError, NotImplementedError):
            pass
        else:
            write_contract(contract_path, safe_again)
            linked_changed = invoke(fixture, contract_path, changed_link)
            require(linked_changed.returncode != 0,
                    "changed-input symlink must fail closed before resolve")
            changed_link.unlink()
            cases += 1

        contract_path.write_bytes(b"\xff\xfeinvalid")
        invalid_contract_encoding = invoke(fixture, contract_path, changed)
        require(invalid_contract_encoding.returncode == 2
                and json.loads(invalid_contract_encoding.stdout)["status"] == "invalid",
                "non-UTF-8 contract must return structured WHY/FIX")
        cases += 1

        records = [
            json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()
        ]
        require(records and all(
            row["measurement"] == "host-observed"
            and row["advisory"] is True
            and row["completionEvidence"] is False
            and isinstance(row["durationMs"], int)
            and "stdout" not in row and "stderr" not in row
            for row in records),
            "telemetry records must remain observed, advisory, and privacy-safe")
        require(all(set(result) <= {
            "index", "exitCode", "timedOut", "durationMs",
            "stdoutSha256", "stderrSha256", "launchErrorSha256"}
            for row in records for result in row["results"]),
            "telemetry result schema must reject raw output fields")
        cases += 1

    print(json.dumps({
        "status": "PASSED",
        "cases": cases,
        "defaultOn": template["enabled"],
        "completionEvidence": template["completionEvidence"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
