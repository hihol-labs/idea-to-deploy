#!/usr/bin/env python3
"""
PreToolUse hook — exact external-write approval plus PII/secret egress guard.

Scans the content of OUTBOUND tool calls (Bash egress commands like curl/wget/
scp/ssh, and WebFetch) for secrets and PII just before the data would leave the
machine. Hybrid enforcement:

  • SECRETS (high-confidence: private keys, AWS keys, provider API tokens,
    Bearer tokens) -> DENY. The call is blocked (permissionDecision "deny",
    exit 2), because exfiltrating a live credential is almost never intended and
    these patterns have near-zero false positives.
  • PII / weaker secret signals (emails, card-shaped numbers, password=/api_key=
    assignments) -> ASK. The user is prompted to confirm (permissionDecision
    "ask"), because these have real false positives and judgment should stay with
    the human.

This ports the OUTCOME of omnigent's egress policy (don't leak data), not its
server-side policy engine. It complements `careful.sh` (which guards destructive
commands) by guarding data-leaving-the-box.

Scope: every tool. The host-neutral external-write engine classifies connector
and shell actions; provably read-only/local calls remain silent. External
mutations require a complete preview and a session-bound exact approval before
the existing PII scan permits them. High-confidence secrets remain denied even
after action approval.

`ITD_PII_GUARD=0` disables only pattern scanning; exact write approval remains
fail-closed and has no shared kill switch.

Reads JSON on stdin: {"tool_name": "...", "tool_input": {...}}
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


EXTERNAL_GATE_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills" / "_shared" / "itd_external_write_gate.py"
)

# --- high-confidence secrets -> DENY -----------------------------------------
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
     "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS temporary access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    (re.compile(r"\b[rs]k_live_[A-Za-z0-9]{16,}\b"), "Stripe live key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), "Anthropic API key"),
    # Exclude URL path/query contexts (/sk-..., ?sk=..., &sk=...) — S3 keys, CDN
    # asset paths and pagination cursors routinely start with "sk-"; still catches
    # the token in headers, -d bodies and shell assignments (the real leak vectors).
    (re.compile(r"(?<![/=&?])\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI-style secret key"),
    (re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._\-]{20,}"),
     "Bearer token in Authorization header"),
]

# --- weaker signals / PII -> ASK ---------------------------------------------
PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
     "email address"),
    (re.compile(r"\b(?:\d[ \-]?){13,19}\b"), "card-shaped number"),
    (re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token|access[_-]?token)\b"
                r"\s*[=:]\s*['\"]?[^\s'\"&]{6,}"),
     "credential assignment"),
]

# Bash commands that send data off the machine. (No bare http|https — that would
# match any command merely mentioning a URL; every real outbound transport is
# named explicitly. WebFetch egress is handled by its own branch.)
EGRESS_BASH = re.compile(
    r"\b(curl|wget|nc|ncat|telnet|scp|sftp|rsync|ssh)\b|"
    r"git\s+push|git\s+remote\s+add",
    re.IGNORECASE,
)


def gather_content(tool: str, tool_input: dict) -> str | None:
    """Return the text to scan for an egress tool, or None if not egress."""
    if tool == "Bash":
        cmd = str(tool_input.get("command") or "")
        if cmd and EGRESS_BASH.search(cmd):
            return cmd
        return None
    if tool == "WebFetch":
        parts = [str(tool_input.get("url") or ""), str(tool_input.get("prompt") or "")]
        joined = "\n".join(p for p in parts if p)
        return joined or None
    if re.search(
            r"(?:^|__|_)(?:mcp|gmail|github|linear|slack|notion|drive|calendar|"
            r"outlook|teams|sharepoint|box|atlassian|figma)(?:__|_|$)",
            tool, re.IGNORECASE):
        return json.dumps(tool_input, ensure_ascii=False, sort_keys=True)
    return None


def emit_deny(label: str, tool: str) -> None:
    msg = (
        f"[PII/SECRET EGRESS GUARD] Blocked: a {label} appears in an outbound "
        f"{tool} call.\n\n"
        f"WHY: the outbound payload contains a credential pattern and has no explicit safe authorization.\n"
        f"FIX: redact/parameterize the secret or obtain explicit user confirmation before retrying.\n\n"
        f"Sending a live credential off the machine is almost never intended. "
        f"This call was denied.\n"
        f"If this is a false positive or genuinely required, ask the user to "
        f"confirm explicitly, or redact/parameterize the secret (use an env var "
        f"reference, not the literal value) and retry.\n"
        f"To disable this guard for the project: ITD_PII_GUARD=0."
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(msg)
    sys.exit(2)


def emit_ask(label: str, tool: str) -> None:
    msg = (
        f"[PII/SECRET EGRESS GUARD] An outbound {tool} call appears to contain "
        f"{label}.\n\n"
        f"Confirm this is intended before sending data off the machine. If it is "
        f"PII or sensitive, consider redacting it first. Approve to proceed."
    )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


def load_external_gate():
    loader = importlib.machinery.SourceFileLoader(
        "itd_external_write_gate_hook", str(EXTERNAL_GATE_SCRIPT))
    spec = importlib.util.spec_from_loader("itd_external_write_gate_hook", loader)
    if spec is None:
        raise RuntimeError("cannot load external-write gate")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def external_message(preview: dict, heading: str) -> str:
    why = str(preview.get("why") or "external write has no exact session-bound approval")
    fix = str(preview.get("fix") or
              "Review this exact preview and approve only this pending host prompt.")
    rendered = json.dumps(preview, ensure_ascii=False, sort_keys=True, indent=2)
    return (
        f"[EXTERNAL WRITE GATE] {heading}\n\n"
        f"WHY: {why}.\n"
        f"FIX: {fix}\n\n"
        "Exact preview (targets, full payload, attachments, session provenance):\n"
        f"{rendered}")


def emit_external_deny(preview: dict) -> None:
    msg = external_message(preview, "Blocked before the external mutation.")
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stderr.write(msg)
    raise SystemExit(2)


def emit_external_ask(preview: dict) -> None:
    msg = external_message(
        preview,
        "Host confirmation is required for this exact pending invocation.")
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": msg,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    raise SystemExit(0)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        emit_external_deny({
            "status": "UNVERIFIED", "approvable": False,
            "why": "hook transport payload is malformed",
            "fix": "Restore a valid full PreToolUse payload; do not run the external action.",
        })

    tool = (payload or {}).get("tool_name") or ""
    tool_input = (payload or {}).get("tool_input") or {}

    content = gather_content(tool, tool_input)
    pii_enabled = os.environ.get("ITD_PII_GUARD") != "0"

    # Secrets are never made safe by approving the surrounding action.
    if pii_enabled and content:
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(content):
                emit_deny(label, tool)

    try:
        result = load_external_gate().evaluate(payload, remember=True)
    except Exception as exc:
        # The shared engine is load-bearing for an external connector or a
        # mutating egress command. Local/read-only traffic remains fail-open.
        externalish = (tool not in {
            "", "Read", "Glob", "Grep", "Edit", "Write", "MultiEdit",
            "NotebookEdit", "apply_patch", "Task", "Agent", "Skill",
        } and tool not in {"WebFetch"})
        mutating_shell = tool in {"Bash", "PowerShell"} and bool(
            re.search(r"\bgit\s+push\b|\bcurl\b.*(?:-d|--data|-F|--form|-X\s*(?:POST|PUT|PATCH|DELETE))",
                      str(tool_input.get("command") or ""), re.IGNORECASE))
        if externalish or mutating_shell:
            emit_external_deny({
                "status": "UNVERIFIED", "approvable": False,
                "why": f"external-write decision engine failed: {exc}",
                "fix": "Restore the shared gate and retry; do not perform the external action.",
                "toolName": tool, "payload": tool_input,
            })
        return 0

    if not result.get("allowed"):
        preview = result.get("preview") or {}
        if not preview.get("approvable"):
            emit_external_deny(preview)
        emit_external_ask(preview)

    # Weaker signals / PII — ASK.
    # An approved exact write already displayed the complete PII-bearing
    # payload, so asking again would violate no-repeat approval semantics.
    if pii_enabled and content and not result.get("approved"):
        for pattern, label in PII_PATTERNS:
            if pattern.search(content):
                emit_ask(label, tool)
                return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
