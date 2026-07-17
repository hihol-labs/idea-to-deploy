#!/usr/bin/env python3
"""Behavioural oracle for exact, session-bound external-write approval."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "skills" / "_shared" / "itd_external_write_gate.py"
HOOK = ROOT / "hooks" / "pii-egress-guard.sh"
DISPATCHER = ROOT / "hooks" / "codex-dispatch.py"
POLICY = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
TRUST = ROOT / "docs" / "HARNESS_TRUST_POLICY.json"
PY = sys.executable


passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print("PASS  " + name)
    else:
        failed += 1
        print("FAIL  " + name + ((" — " + detail[:300]) if detail else ""))


def run(args: list[str], *, stdin: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=stdin, cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          env=env, timeout=30)


def payload(tool: str, tool_input: dict, session: str = "session-a") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "cwd": str(ROOT),
        "tool_name": tool,
        "tool_input": tool_input,
    }


def write_request(directory: Path, name: str, value: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def core(directory: Path, command: str, request: dict | None = None,
         *extra: str, session: str = "session-a") -> subprocess.CompletedProcess:
    args = [PY, str(CORE), command]
    if request is not None:
        path = write_request(directory, f"request-{len(list(directory.glob('request-*')))}.json", request)
        args.extend(["--input", str(path)])
    args.extend(extra)
    env = dict(os.environ, ITD_EXTERNAL_WRITE_STATE_DIR=str(directory),
               CLAUDE_SESSION_ID=session, PYTHONUTF8="1")
    return run(args, env=env)


def preview(directory: Path, request: dict) -> tuple[subprocess.CompletedProcess, dict]:
    proc = core(directory, "preview", request)
    try:
        value = json.loads(proc.stdout)
    except Exception:
        value = {}
    return proc, value


def hook(directory: Path, request: dict, codex: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ, ITD_EXTERNAL_WRITE_STATE_DIR=str(directory),
               CLAUDE_SESSION_ID=str(request.get("session_id") or ""),
               PLUGIN_ROOT=str(ROOT), PYTHONUTF8="1")
    command = [PY, str(HOOK)]
    if codex:
        command = [PY, str(DISPATCHER), "--script", HOOK.name]
    return run(command, stdin=json.dumps(request, ensure_ascii=False), env=env)


def decision(proc: subprocess.CompletedProcess) -> tuple[str, str]:
    try:
        value = json.loads(proc.stdout or "{}")
    except Exception:
        return "", ""
    specific = value.get("hookSpecificOutput") or {}
    return (str(specific.get("permissionDecision") or ""),
            str(specific.get("permissionDecisionReason") or ""))


def registration_rows(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        value = json.loads(text)
    else:
        match = re.search(r"DESIRED_HOOKS=\$\(cat <<'JSON'\n(.+?)\nJSON\n\)",
                          text, re.DOTALL)
        value = {"hooks": json.loads(match.group(1))} if match else {}
    rows: list[tuple[str, str]] = []
    for event, groups in (value.get("hooks") or {}).items():
        for group in groups:
            for item in group.get("hooks", []):
                if HOOK.name in str(item.get("command") or ""):
                    rows.append((event, str(group.get("matcher") or "*")))
    return rows


if not CORE.is_file():
    print(f"FAIL  missing runtime: {CORE}")
    raise SystemExit(1)


# Deployment baseline: no args is a quiet no-op.
no_args = run([PY, str(CORE)])
check("no command is a quiet no-op",
      no_args.returncode == 0 and not no_args.stdout and not no_args.stderr)

with tempfile.TemporaryDirectory(prefix="external-write-gate-") as td:
    state = Path(td)
    malformed = run(
        [PY, str(HOOK)], stdin="{",
        env=dict(os.environ, ITD_EXTERNAL_WRITE_STATE_DIR=str(state),
                 CLAUDE_SESSION_ID="session-a", PYTHONUTF8="1"))
    check("malformed hook transport fails closed",
          malformed.returncode == 2 and decision(malformed)[0] == "deny")
    send = payload("mcp__gmail__send_email", {
        "to": ["maxim@example.test"],
        "cc": ["owner@example.test"],
        "subject": "Отчёт PE5-014",
        "body": "Точный текст письма",
        "attachments": [{"name": "report.txt", "sha256": "a" * 64}],
    })

    first, shown = preview(state, send)
    digest = str(shown.get("approvalHash") or "")
    check("preview is complete and approvable",
          first.returncode == 0 and shown.get("status") == "PREVIEW"
          and shown.get("approvable") is True
          and shown.get("payload") == send["tool_input"]
          and shown.get("attachments") == send["tool_input"]["attachments"]
          and any(item.get("key") == "to" for item in shown.get("targets", []))
          and len(digest) == 64, first.stdout + first.stderr)
    check("preview binds canonical tool name and session provenance",
          shown.get("toolName") == "mcp_gmail_send_email"
          and shown.get("sessionId") == "session-a", json.dumps(shown))

    reordered = payload("mcp__gmail__send_email", {
        "attachments": [{"sha256": "a" * 64, "name": "report.txt"}],
        "body": "Точный текст письма", "subject": "Отчёт PE5-014",
        "cc": ["owner@example.test"], "to": ["maxim@example.test"],
    })
    _, shown_again = preview(state, reordered)
    check("canonical JSON ordering produces a stable hash",
          shown_again.get("approvalHash") == digest)

    asked = hook(state, send)
    asked_decision, asked_reason = decision(asked)
    check("external write uses host-native ask with exact preview",
          asked.returncode == 0 and asked_decision == "ask"
          and digest in asked_reason and "WHY:" in asked_reason
          and "FIX:" in asked_reason, asked.stdout + asked.stderr)
    codex_asked = hook(state, send, codex=True)
    check("Codex dispatcher preserves the same native ask decision",
          codex_asked.returncode == 0 and decision(codex_asked)[0] == "ask",
          codex_asked.stdout + codex_asked.stderr)

    direct_approval = core(state, "approve", None, "--hash", digest, "--session",
                           "session-a", "--confirmed-by", "user")
    check("caller-controlled literal user cannot mint approval",
          direct_approval.returncode != 0)
    check("rejected local approval leaves the native prompt authoritative",
          decision(hook(state, send))[0] == "ask")

    secret_send = json.loads(json.dumps(send))
    secret_send["tool_input"]["body"] = "sk-abcdefghijklmnopqrstuvwxyz12"
    secret_result = hook(state, secret_send)
    check("host approval path never downgrades live-secret egress",
          secret_result.returncode == 2
          and "PII/SECRET EGRESS GUARD" in decision(secret_result)[1],
          secret_result.stdout + secret_result.stderr)

    changed_payload = json.loads(json.dumps(send))
    changed_payload["tool_input"]["body"] = "Изменённый текст письма"
    _, changed_payload_preview = preview(state, changed_payload)
    check("payload change invalidates approval",
          changed_payload_preview.get("approvalHash") != digest
          and decision(hook(state, changed_payload))[0] == "ask")
    changed_target = json.loads(json.dumps(send))
    changed_target["tool_input"]["to"] = ["boris@example.test"]
    _, changed_target_preview = preview(state, changed_target)
    check("target change invalidates approval",
          changed_target_preview.get("approvalHash") != digest
          and decision(hook(state, changed_target))[0] == "ask")
    changed_attachment = json.loads(json.dumps(send))
    changed_attachment["tool_input"]["attachments"][0]["sha256"] = "b" * 64
    _, changed_attachment_preview = preview(state, changed_attachment)
    check("attachment change invalidates approval",
          changed_attachment_preview.get("approvalHash") != digest
          and decision(hook(state, changed_attachment))[0] == "ask")
    other_session = json.loads(json.dumps(send))
    other_session["session_id"] = "session-b"
    check("approval cannot cross session provenance",
          decision(hook(state, other_session))[0] == "ask")

    read_only = payload("mcp__gmail__search_emails", {"query": "from:maxim"})
    read_result = hook(state, read_only)
    check("provably read-only connector action is silently allowed",
          read_result.returncode == 0 and not read_result.stdout)
    codex_read = payload("mcp__codex_apps__github__get_repo", {
        "repository_full_name": "acme/demo",
    })
    codex_read_result = hook(state, codex_read, codex=True)
    check("real Codex app read tool is silently allowed",
          codex_read_result.returncode == 0 and not codex_read_result.stdout,
          codex_read_result.stdout + codex_read_result.stderr)
    codex_write = payload("mcp__codex_apps__github__create_issue", {
        "repository_full_name": "acme/demo", "title": "Exact",
        "body": "Exact body",
    })
    _, codex_write_preview = preview(state, codex_write)
    check("real Codex app write tool preserves exact repository target",
          codex_write_preview.get("effect") == "write"
          and codex_write_preview.get("approvable") is True
          and any(item.get("key") == "repository_full_name"
                  and item.get("value") == "acme/demo"
                  for item in codex_write_preview.get("targets", []))
          and decision(hook(state, codex_write, codex=True))[0] == "ask",
          json.dumps(codex_write_preview, ensure_ascii=False))
    local_mcp = payload("mcp__node_repl__js", {"code": "1 + 1"})
    local_mcp_result = hook(state, local_mcp, codex=True)
    check("local Codex MCP compute is outside the external-write gate",
          local_mcp_result.returncode == 0 and not local_mcp_result.stdout,
          local_mcp_result.stdout + local_mcp_result.stderr)
    camel_read = payload("mcp__linear__getIssue", {"issueId": "LIN-17"})
    camel_result = hook(state, camel_read)
    check("camelCase read action is classified without a false block",
          camel_result.returncode == 0 and not camel_result.stdout)
    for tool_name in ("mcp__gmail__mark_email_as_read",
                      "mcp__outlook__mark_message_read"):
        mark_request = payload(tool_name, {"message_id": "message-17"})
        _, mark_preview = preview(state, mark_request)
        check(f"compound read suffix cannot hide remote mutation: {tool_name}",
              mark_preview.get("effect") == "write"
              and decision(hook(state, mark_request))[0] == "ask")
    camel_write = payload("mcp__calendar__createEvent", {
        "calendarId": "primary", "attendees": ["user@example.test"],
        "summary": "Review",
    })
    _, camel_preview = preview(state, camel_write)
    check("camelCase resource IDs and attendees are exact targets",
          camel_preview.get("approvable") is True
          and {item.get("key") for item in camel_preview.get("targets", [])}
          >= {"calendarId", "attendees"})
    local_edit = payload("Edit", {"file_path": "README.md", "new_string": "x"})
    check("local write is outside the external-write gate",
          hook(state, local_edit).returncode == 0)
    curl_get = payload("Bash", {"command": "curl -s https://example.test/status"})
    check("read-only curl GET is not falsely blocked", hook(state, curl_get).returncode == 0)

    unknown = payload("mcp__vendor__do_thing", {"resource_id": "customer-17",
                                                "value": "changed"})
    unknown_proc, unknown_preview = preview(state, unknown)
    check("unknown external action fails closed but remains explicitly approvable",
          unknown_proc.returncode == 0 and unknown_preview.get("approvable") is True
          and decision(hook(state, unknown))[0] == "ask")
    missing_target = payload("mcp__vendor__mutate", {"value": "changed"})
    missing_proc, missing_preview = preview(state, missing_target)
    check("external mutation without exact targets is not approvable",
          missing_proc.returncode != 0 and missing_preview.get("approvable") is False
          and hook(state, missing_target).returncode == 2
          and decision(hook(state, missing_target))[0] == "deny")

    curl_post = payload("Bash", {"command":
        "curl -X POST https://api.example.test/issues -d '{\"title\":\"Exact\"}'"})
    _, curl_preview = preview(state, curl_post)
    check("shell write preview extracts the exact URL target",
          curl_preview.get("approvable") is True
          and any(item.get("value") == "https://api.example.test/issues"
                  for item in curl_preview.get("targets", [])))
    shell_write_cases = [
        payload("Bash", {"command":
            "curl --json '{\"title\":\"Exact\"}' https://api.example.test/issues"}),
        payload("Bash", {"command":
            "curl --request=POST https://api.example.test/issues"}),
        payload("Bash", {"command":
            "gh api --method POST /repos/acme/demo/issues -f title=Exact"}),
        payload("PowerShell", {"command":
            "Invoke-RestMethod -Method Post -Uri https://api.example.test/issues -Body '{}'"}),
    ]
    for index, request in enumerate(shell_write_cases, start=1):
        _, write_preview = preview(state, request)
        check(f"shell mutation spelling {index} fails closed with an exact target",
              write_preview.get("effect") == "write"
              and write_preview.get("approvable") is True
              and decision(hook(state, request))[0] == "ask",
              json.dumps(write_preview, ensure_ascii=False))
    powershell_get = payload("PowerShell", {"command":
        "Invoke-RestMethod -Method Get -Uri https://api.example.test/status"})
    check("provably read-only PowerShell web request is not falsely blocked",
          hook(state, powershell_get).returncode == 0)
    gh_get = payload("Bash", {"command": "gh api /repos/acme/demo/issues/17"})
    check("provably read-only gh api request is not falsely blocked",
          hook(state, gh_get).returncode == 0)
    browser_shot = payload("mcp__browser__screenshot", {"page_id": "page-17"})
    check("provably read-only browser screenshot is not falsely blocked",
          hook(state, browser_shot).returncode == 0)
    extended_shell_writes = [
        payload("Bash", {"command": "git -C /repo push origin main"}),
        payload("Bash", {"command":
            "curl --data-ascii x=1 https://api.example.test/issues"}),
        payload("Bash", {"command":
            "curl --form-string title=Exact https://api.example.test/issues"}),
        payload("Bash", {"command":
            "curl -XPOST https://api.example.test/issues"}),
        payload("Bash", {"command":
            "curl -Xpost https://api.example.test/issues"}),
        payload("Bash", {"command":
            "curl -dx=1 https://api.example.test/issues"}),
        payload("Bash", {"command":
            "gh pr review 12 --approve -R acme/demo"}),
        payload("Bash", {"command":
            "gh workflow run deploy.yml -R acme/demo"}),
    ]
    for index, request in enumerate(extended_shell_writes, start=1):
        _, write_preview = preview(state, request)
        check(f"extended shell mutation spelling {index} fails closed",
              write_preview.get("effect") == "write"
              and write_preview.get("approvable") is True
              and decision(hook(state, request))[0] == "ask",
              json.dumps(write_preview, ensure_ascii=False))
    issue_comment = payload("Bash", {"command":
        "gh issue comment 123 -R acme/demo --body Exact"})
    _, issue_preview = preview(state, issue_comment)
    check("gh mutation preview includes explicit repo and resource targets",
          {item.get("value") for item in issue_preview.get("targets", [])}
          >= {"acme/demo", "123"})
    git_push = payload("Bash", {"command": "git push -u origin codex/pe5-014"})
    _, push_preview = preview(state, git_push)
    check("git push requires explicit remote and ref targets",
          push_preview.get("approvable") is True
          and {item.get("value") for item in push_preview.get("targets", [])}
          >= {"origin", "codex/pe5-014"})

    bad_confirm = core(state, "approve", None, "--hash", digest, "--session",
                       "session-a", "--confirmed-by", "model")
    check("model self-approval is rejected", bad_confirm.returncode != 0)

# Frozen policy remains authoritative and adapter registrations cover all tools.
policy = json.loads(POLICY.read_text(encoding="utf-8"))["externalWrites"]
check("runtime contract matches the frozen approval binding",
      policy.get("approvalBinding") == "sha256-canonical-tool-name-targets-payload"
      and policy.get("sessionProvenanceRequired") is True
      and policy.get("invalidateOnPayloadOrTargetChange") is True)
trust = json.loads(TRUST.read_text(encoding="utf-8"))
pii_gate = next((item for item in trust.get("hardGates", [])
                 if item.get("script") == HOOK.name), {})
check("trust policy routes the existing hard gate across every tool",
      pii_gate.get("matcher") == "*"
      and pii_gate.get("nativeApprovalDecision") == "ask")
for source in (
        ROOT / "hooks/hooks.json",
        ROOT / "skills/adopt/references/project-settings-template.json",
        ROOT / "skills/adopt/references/codex-project-hooks.json",
        ROOT / "scripts/sync-to-active.sh"):
    rows = registration_rows(source)
    check(f"all-tool PreToolUse registration: {source.relative_to(ROOT)}",
          any(event == "PreToolUse" and matcher in {"*", ".*"}
              for event, matcher in rows), str(rows))

print(f"RESULT: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
