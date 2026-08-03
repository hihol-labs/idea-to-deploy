#!/usr/bin/env python3
"""GPG-003 oracle for one mandatory ordered keyless review workflow."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "skills/_shared/itd_free_reviewer_producer.py"
REVIEW = ROOT / "skills/review/SKILL.md"
CROSS = ROOT / "skills/cross-review/SKILL.md"
LOOP_DOC = ROOT / "docs/VERIFICATION_LOOP.md"
LOOP_SOURCE = ROOT / "skills/_shared/itd_verification_loop.py"
GATE_SOURCE = ROOT / "skills/_shared/itd_gate_control.py"
BROKER_DEPLOY = ROOT / "services/review_broker/deploy/README.md"


def load_producer():
    spec = importlib.util.spec_from_file_location("itd_keyless_review", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("mandatory keyless producer cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_report() -> dict:
    return {"verdict": "PASSED", "findings": [], "unverified": []}


def reviewer(provider: str, model: str, session: str) -> dict:
    return {
        "provider": provider,
        "model": model,
        "session": session,
        "transportExecutableSha256": "a" * 64,
    }


def main() -> int:
    producer = load_producer()
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(message)

    expected_route = (
        "openai-subscription",
        "anthropic-subscription",
        "gemini-user",
    )
    check(
        producer.MANDATORY_REVIEW_ROUTE == expected_route,
        "mandatory provider order drifted",
    )
    check(
        producer._target({
            "repository": "hihol-labs/fixture",
            "pullRequest": None,
            "expectedHeadSha": None,
        })["pullRequest"] is None,
        "initial pre-PR route still requires existing PR coordinates",
    )
    check(
        producer.select_openai_reviewer_model(
            "gpt-5.6-sol", "gpt-5.6-terra"
        ) == "gpt-5.6-terra",
        "different configured OpenAI model was changed",
    )
    check(
        producer.select_openai_reviewer_model(
            "gpt-5.6-terra", "gpt-5.6-terra"
        ) == "gpt-5.6-sol",
        "Terra maker was not routed to a different OpenAI model",
    )

    maker = {"provider": "openai", "model": "gpt-5.6-sol", "session": "maker"}
    calls: list[str] = []

    def success(name: str, model: str):
        def run(_prompt: str):
            calls.append(name)
            return clean_report(), reviewer(name, model, f"fresh-{name}")
        return run

    def unavailable(name: str):
        def run(_prompt: str):
            calls.append(name)
            raise producer.FreeReviewError("UNAVAILABLE", f"{name} unavailable")
        return run

    adapters = {
        "openai-subscription": success("openai-subscription", "gpt-5.6-terra"),
        "anthropic-subscription": success("anthropic-subscription", "claude-opus"),
        "gemini-user": success("gemini-user", "gemini-2.5-pro"),
    }
    result = producer.route_keyless_review(
        "exact prompt", maker=maker, adapters=adapters
    )
    check(calls == ["openai-subscription"], "primary success did not stop routing")
    check(result["reviewer"]["provider"] == "openai-subscription",
          "primary provenance was lost")
    check(result["attempts"] == [
        {"provider": "openai-subscription", "status": "PASSED"}
    ], "primary attempt ledger is not closed")

    calls.clear()
    adapters["openai-subscription"] = unavailable("openai-subscription")
    result = producer.route_keyless_review(
        "exact prompt", maker=maker, adapters=adapters
    )
    check(calls == ["openai-subscription", "anthropic-subscription"],
          "Anthropic was not the first fallback")
    check(result["reviewer"]["provider"] == "anthropic-subscription",
          "Anthropic fallback provenance was lost")

    calls.clear()
    adapters["anthropic-subscription"] = unavailable("anthropic-subscription")
    result = producer.route_keyless_review(
        "exact prompt", maker=maker, adapters=adapters
    )
    check(calls == list(expected_route), "Gemini was not the last fallback")
    check(result["reviewer"]["provider"] == "gemini-user",
          "Gemini fallback provenance was lost")

    calls.clear()
    adapters["gemini-user"] = unavailable("gemini-user")
    try:
        producer.route_keyless_review("exact prompt", maker=maker, adapters=adapters)
    except producer.FreeReviewError as exc:
        check(exc.status == "UNAVAILABLE", "all-unavailable status drifted")
        check(all(name in exc.reason for name in expected_route),
              "all-unavailable reason omits attempted providers")
    else:
        raise AssertionError("all-unavailable route returned success")
    check(calls == list(expected_route), "all-unavailable route order drifted")

    for terminal_status in ("BLOCKED", "UNVERIFIED"):
        calls.clear()

        def terminal(_prompt: str, status=terminal_status):
            calls.append("openai-subscription")
            raise producer.FreeReviewError(status, "terminal review outcome")

        terminal_adapters = dict(adapters)
        terminal_adapters["openai-subscription"] = terminal
        try:
            producer.route_keyless_review(
                "exact prompt", maker=maker, adapters=terminal_adapters
            )
        except producer.FreeReviewError as exc:
            check(exc.status == terminal_status,
                  f"{terminal_status} was reclassified")
        else:
            raise AssertionError(f"{terminal_status} fell through to another provider")
        check(calls == ["openai-subscription"],
              f"{terminal_status} incorrectly advanced the route")

    blocked_report = {
        "verdict": "BLOCKED",
        "findings": [{
            "severity": "important", "confidence": "high",
            "category": "fixture", "file": "fixture.py", "line": 1,
            "summary": "Persist this actionable finding.",
        }],
        "unverified": [],
    }

    def blocked_result(_prompt: str):
        return blocked_report, reviewer(
            "openai-subscription", "gpt-5.6-terra", "fresh-blocked"
        )

    diagnostic_adapters = dict(adapters)
    diagnostic_adapters["openai-subscription"] = blocked_result
    try:
        producer.route_keyless_review(
            "exact prompt", maker=maker, adapters=diagnostic_adapters
        )
    except producer.FreeReviewError as exc:
        check(exc.status == "BLOCKED", "negative report status drifted")
        check(
            exc.evidence is not None
            and exc.evidence.get("report") == blocked_report,
            "negative reviewer findings were discarded",
        )
        check(
            exc.evidence is not None
            and exc.evidence.get("attempts") == [{
                "provider": "openai-subscription", "status": "PASSED",
            }],
            "negative reviewer route provenance was discarded",
        )
        with tempfile.TemporaryDirectory(prefix="keyless-diagnostic-") as raw:
            prompt_path = Path(raw) / "prompt.md"
            report_path = Path(raw) / "report.json"
            detail = producer.persist_review_diagnostic(
                prompt="exact prompt", prompt_output=prompt_path,
                report_output=report_path, error=exc,
            )
            check(
                detail is not None
                and prompt_path.read_bytes() == b"exact prompt",
                "negative review prompt was not persisted byte-exactly",
            )
            check(
                json.loads(report_path.read_text(encoding="utf-8"))
                == blocked_report,
                "negative reviewer findings were not persisted",
            )
    else:
        raise AssertionError("negative reviewer report returned a route pass")

    same_model_adapters = dict(adapters)
    same_model_adapters["openai-subscription"] = success(
        "openai-subscription", maker["model"]
    )
    calls.clear()
    try:
        producer.route_keyless_review(
            "exact prompt", maker=maker, adapters=same_model_adapters
        )
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED", "same-model result was not unverified")
    else:
        raise AssertionError("same-model reviewer was accepted")
    check(calls == ["openai-subscription"],
          "same-model identity failure incorrectly advanced the route")

    claude = producer.claude_command(
        executable="claude", model="opus", schema_json="{}"
    )
    for flag in (
        "--safe-mode", "--no-session-persistence", "--strict-mcp-config",
        "--disable-slash-commands", "--json-schema", "--output-format",
        "--tools", "--setting-sources", "--mcp-config", "--print",
    ):
        check(flag in claude, f"Claude isolation omits {flag}")
    check(claude[claude.index("--tools") + 1] == "",
          "Claude tools are not disabled")
    check(claude[claude.index("--mcp-config") + 1]
          == '{"mcpServers":{}}', "Claude empty MCP config is malformed")

    gemini = producer.gemini_command(
        executable="gemini", model="gemini-2.5-pro",
        policy_file=Path("deny-all.toml"), session="00000000-0000-4000-8000-000000000001",
    )
    check("--policy" in gemini and "--approval-mode" in gemini,
          "Gemini deny policy/plan mode is absent")
    check(gemini[gemini.index("--approval-mode") + 1] == "plan",
          "Gemini is not in plan mode")
    check("--output-format" in gemini
          and gemini[gemini.index("--output-format") + 1] == "stream-json",
          "Gemini tool/session telemetry is absent")
    producer.assert_gemini_cli_contract(producer.subprocess.CompletedProcess(
        gemini, 0,
        stdout=(" ".join(producer.GEMINI_REQUIRED_CLI_FLAGS)).encode(),
        stderr=b"",
    ))
    try:
        producer.assert_gemini_cli_contract(producer.subprocess.CompletedProcess(
            gemini, 0, stdout=b"--policy --session-id", stderr=b"",
        ))
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "incompatible Gemini CLI was not fail-closed")
    else:
        raise AssertionError("incompatible Gemini CLI passed argument smoke")

    unknown_cli = producer.subprocess.CompletedProcess(
        ["reviewer"], 2, stdout=b"", stderr=b"unknown option --policy"
    )
    try:
        producer.raise_cli_failure(unknown_cli, "fixture reviewer")
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "unknown post-launch CLI defect was classified unavailable")
    else:
        raise AssertionError("unknown post-launch CLI defect was accepted")
    unavailable_cli = producer.subprocess.CompletedProcess(
        ["reviewer"], 1, stdout=b"", stderr=b"API Error: 401 unauthorized"
    )
    try:
        producer.raise_cli_failure(unavailable_cli, "fixture reviewer")
    except producer.FreeReviewError as exc:
        check(exc.status == "UNAVAILABLE",
              "positive auth failure was not classified unavailable")
    else:
        raise AssertionError("positive auth failure was accepted")

    calls.clear()

    def unknown_cli_adapter(_prompt: str):
        calls.append("openai-subscription")
        producer.raise_cli_failure(unknown_cli, "fixture reviewer")

    no_fallback = dict(adapters)
    no_fallback["openai-subscription"] = unknown_cli_adapter
    try:
        producer.route_keyless_review(
            "exact prompt", maker=maker, adapters=no_fallback
        )
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "unknown post-launch CLI defect did not stop the route")
    else:
        raise AssertionError("unknown post-launch CLI defect fell through")
    check(calls == ["openai-subscription"],
          "unknown post-launch CLI defect advanced to a fallback")
    gemini_session = "00000000-0000-4000-8000-000000000001"
    gemini_events = b"\n".join([
        json.dumps({
            "type": "init", "session_id": gemini_session,
            "model": "gemini-2.5-pro",
        }).encode(),
        json.dumps({
            "type": "message", "role": "assistant",
            "content": json.dumps(clean_report()), "delta": True,
        }).encode(),
        json.dumps({"type": "result", "status": "success"}).encode(),
    ]) + b"\n"
    gemini_report, gemini_model = producer._gemini_stream_report(
        gemini_events, gemini_session, "gemini-2.5-pro"
    )
    check(gemini_report == clean_report()
          and gemini_model == "gemini-2.5-pro",
          "Gemini documented stream/model shape was not accepted")
    try:
        producer._gemini_stream_report(
            gemini_events, "foreign-session", "gemini-2.5-pro"
        )
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "foreign Gemini session status drifted")
    else:
        raise AssertionError("foreign Gemini session was accepted")
    try:
        producer._gemini_stream_report(
            gemini_events, gemini_session, "gemini-maker-model"
        )
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "foreign Gemini model telemetry was not terminal")
    else:
        raise AssertionError("foreign Gemini model telemetry was accepted")

    check(
        producer._claude_observed_model({
            "modelUsage": {"claude-opus-4-20250514": {}},
        }, "opus") == "claude-opus-4-20250514",
        "Claude runtime model alias was not observed",
    )
    try:
        producer._claude_observed_model({
            "modelUsage": {"claude-sonnet-4-20250514": {}},
        }, "opus")
    except producer.FreeReviewError as exc:
        check(exc.status == "UNVERIFIED",
              "foreign Claude model telemetry was not terminal")
    else:
        raise AssertionError("foreign Claude model telemetry was accepted")

    hostile_env = {
        "PATH": "/bin",
        "HOME": "/tmp/home",
        "OPENAI_API_KEY": "[REDACTED]",
        "ANTHROPIC_API_KEY": "[REDACTED]",
        "GEMINI_API_KEY": "[REDACTED]",
        "GOOGLE_API_KEY": "[REDACTED]",
        "HTTP_PROXY": "http://proxy.invalid:8080",
        "HTTPS_PROXY": "http://proxy.invalid:8080",
    }
    child = producer.reviewer_environment(hostile_env)
    check(not any("API_KEY" in name for name in child),
          "provider API key reached reviewer environment")

    with tempfile.TemporaryDirectory(prefix="itd-codex-native-test-") as raw:
        fixture = Path(raw)
        bin_dir = fixture / "bin"
        bin_dir.mkdir()
        launcher = bin_dir / ("codex.cmd" if os.name == "nt" else "codex")
        launcher.write_text("@exit /b 0\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n")
        if os.name != "nt":
            launcher.chmod(0o700)
        package = (
            fixture / ".npm-global" / "lib" / "node_modules" / "@openai"
            / "codex-fixture" / "vendor" / "fixture" / "bin"
        )
        package.mkdir(parents=True)
        native = package / ("codex.exe" if os.name == "nt" else "codex")
        shutil.copyfile(sys.executable, native)
        if os.name != "nt":
            native.chmod(0o500)
        native_sha = producer.sha256_bytes(native.read_bytes())
        home_name = "USERPROFILE" if os.name == "nt" else "HOME"
        original_home = os.environ.get(home_name)
        os.environ[home_name] = str(fixture)
        try:
            resolved, actual, _content = producer.trusted_executable(
                "codex", native_sha, str(bin_dir)
            )
        finally:
            if original_home is None:
                os.environ.pop(home_name, None)
            else:
                os.environ[home_name] = original_home
        check(resolved == native.resolve() and actual == native_sha,
              "standard npm Codex native payload was not resolved")

    with tempfile.TemporaryDirectory(prefix="itd-claude-native-test-") as raw:
        fixture = Path(raw)
        bin_dir = fixture / "bin"
        bin_dir.mkdir()
        launcher = bin_dir / ("claude.cmd" if os.name == "nt" else "claude")
        launcher.write_text("@exit /b 0\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n")
        if os.name != "nt":
            launcher.chmod(0o700)
        package = (
            fixture / ".npm-global" / "lib" / "node_modules"
            / "@anthropic-ai" / "claude-code" / "bin"
        )
        package.mkdir(parents=True)
        native = package / ("claude.exe" if os.name == "nt" else "claude")
        shutil.copyfile(sys.executable, native)
        if os.name != "nt":
            native.chmod(0o500)
        native_sha = producer.sha256_bytes(native.read_bytes())
        home_name = "USERPROFILE" if os.name == "nt" else "HOME"
        original_home = os.environ.get(home_name)
        os.environ[home_name] = str(fixture)
        try:
            resolved, actual, _content = producer.trusted_executable(
                "claude", native_sha, str(bin_dir)
            )
        finally:
            if original_home is None:
                os.environ.pop(home_name, None)
            else:
                os.environ[home_name] = original_home
        check(resolved == native.resolve() and actual == native_sha,
              "standard npm Claude native payload was not resolved")

    with tempfile.TemporaryDirectory(prefix="itd-gemini-bundle-test-") as raw:
        fixture = Path(raw)
        bundle = fixture / "bundle"
        bundle.mkdir()
        launcher = bundle / "gemini.js"
        chunk = bundle / "chunk-fixture.js"
        launcher.write_text(
            '#!/usr/bin/env node\nimport "./chunk-fixture.js";\n', encoding="utf-8"
        )
        chunk.write_text("export const fixture = true;\n", encoding="utf-8")
        if os.name != "nt":
            launcher.chmod(0o500)
        bundle_sha = producer.gemini_bundle_digest(str(launcher))
        bound_launcher, actual, entries = producer.trusted_gemini_bundle(
            str(launcher), bundle_sha, None
        )
        check(bound_launcher == launcher.resolve() and actual == bundle_sha,
              "Gemini complete bundle pin was not accepted")
        check([name for name, _content in entries]
              == ["chunk-fixture.js", "gemini.js"],
              "Gemini bundle manifest is incomplete or unordered")
        chunk.write_text("export const fixture = false;\n", encoding="utf-8")
        try:
            producer.trusted_gemini_bundle(str(launcher), bundle_sha, None)
        except producer.FreeReviewError as exc:
            check(exc.status == "UNVERIFIED",
                  "changed Gemini dependency status drifted")
        else:
            raise AssertionError("changed Gemini dependency bypassed the bundle pin")

    with tempfile.TemporaryDirectory(prefix="itd-anthropic-auth-test-") as raw:
        home = Path(raw)
        source = home / ".claude" / ".credentials.json"
        source.parent.mkdir()
        anthropic_auth = {
            "claudeAiOauth": {
                "accessToken": "[REDACTED]",
                "refreshToken": "[REDACTED]",
                "expiresAt": 4102444800000,
                "scopes": ["user:inference"],
                "subscriptionType": "pro",
                "rateLimitTier": "default",
            }
        }
        source.write_text(json.dumps(anthropic_auth), encoding="utf-8")
        if os.name != "nt":
            source.chmod(0o600)
        with producer.anthropic_transport_home({"HOME": str(home)}) as (
            isolated_home, config,
        ):
            files = sorted(
                path.relative_to(isolated_home).as_posix()
                for path in isolated_home.rglob("*") if path.is_file()
            )
            check(files == [".claude/.credentials.json"],
                  "Claude isolation copied non-auth state")
            check(json.loads((config / ".credentials.json").read_text())
                  == anthropic_auth, "Claude isolated auth changed")

    with tempfile.TemporaryDirectory(prefix="itd-gemini-auth-test-") as raw:
        home = Path(raw)
        source = home / ".gemini" / "oauth_creds.json"
        source.parent.mkdir()
        gemini_auth = {
            "access_token": "[REDACTED]",
            "refresh_token": "[REDACTED]",
            "token_type": "Bearer",
            "expiry_date": 4102444800000,
        }
        source.write_text(json.dumps(gemini_auth), encoding="utf-8")
        if os.name != "nt":
            source.chmod(0o600)
        with producer.gemini_transport_home({"HOME": str(home)}) as (
            isolated_home, policy,
        ):
            files = sorted(
                path.relative_to(isolated_home).as_posix()
                for path in isolated_home.rglob("*") if path.is_file()
            )
            check(files == [
                ".gemini/oauth_creds.json",
                ".gemini/policies/itd-deny-all.toml",
                ".gemini/settings.json",
            ], "Gemini isolation file set is not closed")
            settings = json.loads(
                (isolated_home / ".gemini" / "settings.json").read_text()
            )
            check(settings["security"]["auth"] == {
                "selectedType": "oauth-personal",
                "enforcedType": "oauth-personal",
            }, "Gemini personal OAuth is not enforced")
            check('toolName = "*"' in policy.read_text()
                  and 'decision = "deny"' in policy.read_text(),
                  "Gemini deny-all policy drifted")

    source = PRODUCER.read_text(encoding="utf-8")
    check("api.openai.com" not in source, "mandatory producer contains paid endpoint")
    for marker in ("allow_bypass", "user_bypass", "force_review_pass"):
        check(marker not in source, f"caller bypass surface {marker} exists")
    check(
        all(marker in source for marker in (
            '"--prompt-output"', '"--report-output"',
            "write_text(args.prompt_output, prompt)",
            'write_json(args.report_output, routed["report"])',
        )),
        "shared producer does not persist its exact prompt/report artifacts",
    )
    check(
        source.count('"model": observed_model') == 3
        and all(marker in source for marker in (
            "OpenAI reviewer model telemetry is absent",
            "Claude reviewer model telemetry is absent",
            "Gemini reviewer model telemetry is absent",
        )),
        "reviewer provenance still trusts caller-requested model identity",
    )

    loop_source = LOOP_SOURCE.read_text(encoding="utf-8")
    check(
        '"--phase-one-receipt"' in loop_source
        and '"--producer-keyring"' in loop_source,
        "Verification Loop cannot bind signed phase-one route evidence",
    )
    check(
        '"--require-mandatory-route"' in loop_source
        and "validate_mandatory_route_evidence" in loop_source
        and 'set(value) != {"verdict", "findings", "unverified"}' in loop_source,
        "Verification Loop publication route remains generic or report-open",
    )
    check(
        '"--require-mandatory-route"' in GATE_SOURCE.read_text(encoding="utf-8")
        and '"--expected-repository"' in GATE_SOURCE.read_text(encoding="utf-8"),
        "local publication doctor accepts generic or foreign-repository evidence",
    )
    deploy_text = BROKER_DEPLOY.read_text(encoding="utf-8")
    check(
        '"reviewerModels"' in deploy_text
        and '"reviewerProvider"' not in deploy_text
        and '"reviewerModel"' not in deploy_text,
        "broker deployment guide retains the obsolete reviewer key schema",
    )

    review_text = REVIEW.read_text(encoding="utf-8")
    cross_text = CROSS.read_text(encoding="utf-8")
    loop_text = LOOP_DOC.read_text(encoding="utf-8")
    for label, text in (("review", review_text), ("cross-review", cross_text),
                        ("Verification Loop", loop_text)):
        check("OpenAI -> Anthropic -> Gemini" in text,
              f"{label} does not name the mandatory route")
        check("itd_free_reviewer_producer.py" in text,
              f"{label} does not name the shared producer")
        check("no caller bypass" in text.lower(),
              f"{label} does not prohibit caller bypass")
    check("fail-open" not in cross_text.lower(),
          "cross-review still advertises fail-open behavior")
    check("advisory second opinion" not in cross_text.lower(),
          "cross-review remains a substitutable advisory workflow")

    print(json.dumps({
        "status": "PASSED",
        "checks": checks,
        "route": list(expected_route),
        "paidApiCalls": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
