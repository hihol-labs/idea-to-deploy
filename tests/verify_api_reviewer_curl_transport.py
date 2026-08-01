#!/usr/bin/env python3
"""Prove curl transport keeps the API key out of argv and request files."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "skills" / "_shared" / "itd_external_reviewer.py"
POLICY = ROOT / "skills" / "_shared" / "EXTERNAL_REVIEW_POLICY.json"
SCHEMA = ROOT / "skills" / "_shared" / "EXTERNAL_REVIEW_VERDICT_SCHEMA.json"
spec = importlib.util.spec_from_file_location("itd_curl_reviewer_test", MODULE)
assert spec and spec.loader
reviewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reviewer
spec.loader.exec_module(reviewer)


def main() -> int:
    policy = reviewer.policy_from(POLICY)
    schema = reviewer.read_json(SCHEMA)
    provider = policy["providers"][0]
    fixture_key = "sk-proj-" + "A" * 40
    response = {
        "id": "resp_curl_fixture",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {"verdict": "PASSED", "findings": [], "unverified": []}
                        ),
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }
    calls: list[tuple[list[str], bytes | None, dict[str, str]]] = []
    api_attempts = 0

    def fake_run(command, **kwargs):
        calls.append((list(command), kwargs.get("input"), dict(kwargs.get("env") or {})))
        assert command == [
            "/trusted/system/curl",
            "--disable",
            "--version",
        ]
        return subprocess.CompletedProcess(
            command, 0, stdout=b"curl 8.5.0 (fixture)\n", stderr=b""
        )

    def fake_bounded(command, request_body, child_env, response_limit, timeout):
        nonlocal api_attempts
        calls.append((list(command), request_body, dict(child_env)))
        api_attempts += 1
        if api_attempts == 1:
            return subprocess.CompletedProcess(
                command, 35, stdout=b"", stderr=b"TLS handshake failed"
            )
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(response).encode("utf-8"), stderr=b""
        )

    original_run = reviewer.subprocess.run
    original_bounded = reviewer.run_curl_bounded
    original_resolver = reviewer.trusted_curl_executable
    original_key = os.environ.get("OPENAI_API_KEY")
    original_path = os.environ.get("PATH")
    try:
        reviewer.subprocess.run = fake_run
        reviewer.run_curl_bounded = fake_bounded
        reviewer.trusted_curl_executable = lambda: "/trusted/system/curl"
        os.environ["OPENAI_API_KEY"] = fixture_key
        os.environ["PATH"] = "/attacker-controlled"
        value, telemetry = reviewer.call_openai_curl(
            provider, "bounded prompt", schema, policy, "OPENAI_API_KEY"
        )
    finally:
        reviewer.subprocess.run = original_run
        reviewer.run_curl_bounded = original_bounded
        reviewer.trusted_curl_executable = original_resolver
        if original_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original_key
        if original_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original_path

    assert value["id"] == "resp_curl_fixture"
    assert telemetry["transport"] == "curl"
    assert telemetry["attempts"] == 1
    assert telemetry["preRequestConnectAttempts"] == 2
    assert len(calls) == 3
    command, request_body, child_env = calls[2]
    assert fixture_key not in "\0".join(command)
    assert command[:2] == ["/trusted/system/curl", "--disable"]
    assert fixture_key not in (request_body or b"").decode("utf-8")
    assert child_env["OPENAI_API_KEY"] == fixture_key
    assert "PATH" not in child_env
    assert "--variable" in command and "%OPENAI_API_KEY" in command
    assert "--expand-header" in command
    assert not any(
        "temp" in item.lower() and fixture_key in item for item in command
    )
    bounded = reviewer.run_curl_bounded(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'x'*10)",
        ],
        b"request",
        os.environ.copy(),
        10,
        5,
    )
    assert bounded.stdout == b"x" * 10
    try:
        reviewer.run_curl_bounded(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'x'*11)",
            ],
            b"request",
            os.environ.copy(),
            10,
            5,
        )
    except reviewer.ReviewError as exc:
        assert exc.status == "UNVERIFIED"
    else:
        raise AssertionError("oversized streaming response was accepted")
    print(json.dumps({"checks": 14, "status": "PASSED"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
