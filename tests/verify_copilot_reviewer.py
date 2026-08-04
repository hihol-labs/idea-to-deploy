#!/usr/bin/env python3
"""GPG-003 regression oracle for the GitHub Copilot Free keyless adapter."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "skills/_shared/itd_free_reviewer_producer.py"


def load_producer():
    spec = importlib.util.spec_from_file_location("itd_copilot_review", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("mandatory keyless producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_report() -> dict:
    return {"verdict": "PASSED", "findings": [], "unverified": []}


def stream(
    prompt: str, *, model: str = "gpt-5-mini", content: str | None = None,
) -> bytes:
    session = "00000000-0000-4000-8000-000000000032"
    rows = [
        {"type": "session.skills_loaded", "data": {"skills": [
            {"name": "builtin", "source": "builtin"},
        ]}},
        {"type": "session.auto_mode_resolved", "data": {
            "chosenModel": model,
            "availableModels": ["claude-haiku-4.5", "gpt-5-mini"],
            "fallback": False,
            "stickyOverride": False,
        }},
        {"type": "session.tools_updated", "data": {"model": model}},
        {"type": "user.message", "data": {"content": prompt}},
        {"type": "model.call_start", "data": {"model": model}},
        {"type": "assistant.message", "data": {
            "model": model,
            "content": (
                json.dumps(clean_report(), separators=(",", ":"))
                if content is None else content
            ),
            "toolRequests": [],
        }},
        {"type": "result", "sessionId": session, "exitCode": 0, "usage": {
            "premiumRequests": 0.33,
            "codeChanges": {
                "linesAdded": 0, "linesRemoved": 0, "filesModified": [],
            },
        }},
    ]
    return b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"


def main() -> int:
    producer = load_producer()
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(message)

    check(producer.MANDATORY_REVIEW_ROUTE == (
        "openai-subscription",
        "anthropic-subscription",
        "github-copilot-user",
    ), "unavailable Google route remains mandatory")
    check(producer.COPILOT_ALLOWED_AUTO_MODELS == (
        "claude-haiku-4.5", "gpt-5-mini",
    ), "Copilot Free observed-model allowlist drifted")
    check(producer.COPILOT_MAX_PREMIUM_REQUESTS_PER_CALL == 1.0,
          "Copilot Free per-call quota bound drifted")

    with tempfile.TemporaryDirectory(prefix="itd-copilot-command-") as raw:
        workspace = Path(raw)
        command = producer.copilot_command(
            executable="copilot", workspace=workspace,
            log_dir=workspace / "logs", model="auto",
        )
    for flag in producer.COPILOT_REQUIRED_CLI_FLAGS:
        check(any(value == flag or value.startswith(flag + "=") for value in command),
              f"Copilot isolation omits {flag}")
    check("-p" not in command and "--prompt" not in command,
          "Copilot review packet leaks into argv")
    check(not any(flag in command for flag in (
        "--allow-all", "--allow-all-tools", "--allow-all-paths",
        "--allow-all-urls", "--yolo",
    )), "Copilot adapter grants dangerous permissions")
    check(command[command.index("--model") + 1] == "auto",
          "Copilot Free route is not forced to auto")
    check(command[command.index("--max-ai-credits") + 1] == "30",
          "Copilot session cost bound drifted")
    check(command[command.index("--output-format") + 1] == "json",
          "Copilot runtime telemetry is absent")
    check("--available-tools=" in command,
          "Copilot model tool surface is not empty")

    producer.assert_copilot_cli_contract(subprocess.CompletedProcess(
        command, 0,
        stdout=(" ".join(producer.COPILOT_REQUIRED_CLI_FLAGS)).encode(),
        stderr=b"",
    ))
    try:
        producer.assert_copilot_cli_contract(subprocess.CompletedProcess(
            command, 0, stdout=b"--model --output-format", stderr=b"",
        ))
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "incompatible Copilot CLI was not fail-closed")
    else:
        raise AssertionError("incompatible Copilot CLI passed argument smoke")

    prompt = "exact review packet — stdin only\n"
    events = stream(prompt)
    report, observed_session, observed_model = producer._copilot_stream_report(
        events, prompt.encode()
    )
    check(report == clean_report(), "Copilot closed report was not parsed")
    check(observed_session == "00000000-0000-4000-8000-000000000032",
          "Copilot runtime session was not bound")
    check(observed_model == "gpt-5-mini",
          "Copilot runtime model was not bound")

    mutations = (
        (events.replace(b'"toolRequests": []',
                        b'"toolRequests": [{"name":"read"}]'), "tool call"),
        (events.replace(b'"source": "builtin"', b'"source": "user"'),
         "inherited skill"),
        (events.replace(b'"model": "gpt-5-mini"',
                        b'"model": "claude-haiku-4.5"', 1),
         "changed model"),
        (stream(prompt, model="gpt-5.4"), "unauthorized model"),
        (events.replace(b'"gpt-5-mini"], "fallback": false',
                        b'"gpt-5.4"], "fallback": false'),
         "changed entitlement"),
        (stream("substituted prompt"), "changed stdin"),
        (events.replace(b'"premiumRequests": 0.33', b'"premiumRequests": 1.01'),
         "over-quota request"),
        (events.replace(b'"filesModified": []', b'"filesModified": ["x"]'),
         "workspace change"),
        (events.replace(b"00000000-0000-4000-8000-000000000032", b"bad-session"),
         "invalid session"),
        (stream(prompt, content='```json\n{"verdict":"PASSED",'
                                '"findings":[],"unverified":[]}\n```'),
         "Markdown-wrapped report"),
        (stream(prompt, content='Result: {"verdict":"PASSED",'
                                '"findings":[],"unverified":[]}'),
         "prose-prefixed report"),
        (b"not-json\n", "malformed stream"),
    )
    for altered, label in mutations:
        try:
            producer._copilot_stream_report(altered, prompt.encode())
        except producer.FreeReviewError as exc:
            check(exc.status == "UNVERIFIED",
                  f"Copilot {label} did not fail closed")
        else:
            raise AssertionError(f"Copilot {label} was accepted")

    with tempfile.TemporaryDirectory(prefix="itd-copilot-transport-test-") as raw:
        fixture = Path(raw)
        binary = fixture / ("copilot.exe" if os.name == "nt" else "copilot")
        binary_content = b"pinned Copilot runtime\n"
        binary.write_bytes(binary_content)
        if os.name != "nt":
            binary.chmod(0o500)
        observed_calls: list[tuple[list[str], bytes, dict[str, str]]] = []

        def fake_run(call, **kwargs):
            if call[-1] == "--help":
                help_text = " ".join(producer.COPILOT_REQUIRED_CLI_FLAGS).encode()
                return subprocess.CompletedProcess(call, 0, help_text, b"")
            observed_calls.append((list(call), kwargs["input"], kwargs["env"]))
            return subprocess.CompletedProcess(call, 0, stream(prompt), b"")

        original_trusted = producer.trusted_executable
        original_run = producer.subprocess.run
        try:
            producer.trusted_executable = lambda *_args: (
                binary, "a" * 64, binary_content,
            )
            producer.subprocess.run = fake_run
            actual_report, actual_session, actual_model = producer.run_copilot_review(
                prompt, executable=str(binary), model="auto",
                source_env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": str(fixture / "user-home"),
                    "USERPROFILE": str(fixture / "user-home"),
                    "GH_TOKEN": "[REDACTED]",
                },
                expected_executable_sha256="a" * 64,
                expected_proxy_sha256=producer.sha256_bytes(b"\n"),
            )
        finally:
            producer.trusted_executable = original_trusted
            producer.subprocess.run = original_run
        check(actual_report == clean_report() and actual_session and
              actual_model == "gpt-5-mini",
              "Copilot subprocess result lost runtime provenance")
        check(len(observed_calls) == 1 and observed_calls[0][1] == prompt.encode(),
              "Copilot did not receive exact prompt bytes on stdin")
        actual_command, _stdin, actual_env = observed_calls[0]
        check("-p" not in actual_command and "--prompt" not in actual_command,
              "Copilot subprocess put the packet in argv")
        check("GH_TOKEN" not in actual_env and
              actual_env.get("COPILOT_HOME") and actual_env.get("CI") == "1",
              "Copilot transport environment inherited a secret or lost isolation")
        workspace = Path(actual_command[actual_command.index("-C") + 1])
        log_dir = Path(actual_command[actual_command.index("--log-dir") + 1])
        check(actual_command == producer.copilot_command(
            executable=actual_command[0], workspace=workspace,
            log_dir=log_dir, model="auto",
        ), "Copilot subprocess argv drifted from the pinned contract")
        check(producer.canonical_model_identity(
            "github-copilot-user", "gpt-5-mini"
        ) == ("openai", "gpt-5-mini"),
              "Copilot underlying OpenAI model family was hidden")
        check(producer.canonical_model_identity(
            "github-copilot-user", "claude-haiku-4.5"
        ) == ("anthropic", "haiku"),
              "Copilot underlying Anthropic model family was hidden")

    print(json.dumps({
        "status": "PASSED", "checks": checks,
        "route": list(producer.MANDATORY_REVIEW_ROUTE), "paidApiCalls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
