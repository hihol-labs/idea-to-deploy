#!/usr/bin/env python3
"""Codex transport adapter for the shared Idea to Deploy hooks.

Codex and Claude share the lifecycle payload and decision protocol. The one
material mutation difference is Codex's ``apply_patch`` tool: its input is a
patch string rather than a single ``file_path``. This dispatcher expands the
patch into synthetic Write events, invokes the unchanged shared hook once per
affected path, and merges the results without weakening a deny decision.

It is also the one place that decides which registered hooks run (plan
session 5, ADR-016): the optional hooks below run only when the user names
them in itd-enabled-hooks.txt, and a hook named in itd-disabled-hooks.txt
never runs. scripts/sync-to-active.sh and skills/_shared/itd_project_hooks.py
load this module for the same decision, so Codex and Claude Code read the same
two lists and do not depend on Codex's positional hooks.state keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from typing import Any


PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File:|Move to:) (.+?)\s*$", re.MULTILINE
)
DEFAULT_SHARED_HOOK_TIMEOUT_SECONDS = 3
# The strict completion gate may synchronously rerun the project's approved
# verification contract (bounded internally at 720 seconds).  Keep the Codex
# transport deadline below the 900-second host registration while leaving
# 120 seconds for bounded root/scope/baseline work and process overhead.
SCRIPT_TIMEOUT_SECONDS = {
    "completion-gate.sh": 840,
    # On a commit the DoD gate may run the project's .itd/checks, bounded at
    # 120 seconds; the host registration is 150 seconds (plan session 5).
    "check-dod-before-commit.sh": 140,
}
# Off by default, on through itd-enabled-hooks.txt: the diagnostics, plus crash-recovery, which writes a checkpoint
# and runs git on every tool call whether or not the project keeps .itd-memory.
OPTIONAL_HOOKS = frozenset({
    "completion-stop.sh",
    "context-aware.sh",
    "context-budget.sh",
    "cost-tracker.sh",
    "crash-recovery.sh",
    "execution-trace.sh",
    "risk-score.sh",
    "session-open-diagnostic.sh",
    "stuck-detection.sh",
})
DISABLED_HOOKS_FILE = "itd-disabled-hooks.txt"
ENABLED_HOOKS_FILE = "itd-enabled-hooks.txt"
# Codex PreToolUse does not support permissionDecision "ask": the call runs
# (fail open). A shared-hook ask becomes a deny that names the hash of the
# exact call; the owner answers with this line in the chat, UserPromptSubmit
# records a one-time approval for the session, and the same exact call passes
# once (CODEX-ASK-GATES-1). The store is guarded only by the OS user's file
# permissions - weaker than Claude's native prompt, bound to one exact call.
APPROVALS_DIR = "itd-codex-approvals"
APPROVAL_TTL_SECONDS = 30 * 60
# A CRLF line end (Windows transports) is accepted; with MULTILINE, $ stops before "\n", not "\r".
APPROVE_LINE_RE = re.compile(r"^ITD-APPROVE ([0-9a-f]{64})\r?$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    return parser.parse_args()


def hook_lists_home() -> Path:
    """The directory of the two hook lists: the Claude home sync-to-active.sh installs into."""
    configured = os.environ.get("CLAUDE_HOME")
    return Path(configured) if configured else Path.home() / ".claude"


def read_hook_list(path: Path) -> set[str]:
    """Hook file names, one per line; '#' starts a comment and a BOM from a Windows editor is dropped.

    A missing or unreadable list is empty: a broken disabled list switches no hook off, and a broken enabled
    list leaves the optional hooks off, as they are by default.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return set()
    return {line.split("#", 1)[0].strip() for line in text.splitlines()} - {""}


def hook_selected(script_name: str, disabled: set[str], enabled: set[str]) -> bool:
    if script_name in disabled:
        return False
    return script_name not in OPTIONAL_HOOKS or script_name in enabled


def selected_for_user(script_name: str) -> bool:
    try:
        lists = hook_lists_home()
    except RuntimeError:  # no home directory: no lists, the defaults apply
        return script_name not in OPTIONAL_HOOKS
    return hook_selected(script_name, read_hook_list(lists / DISABLED_HOOKS_FILE),
                         read_hook_list(lists / ENABLED_HOOKS_FILE))


def shared_hook_timeout(script_name: str) -> int:
    return SCRIPT_TIMEOUT_SECONDS.get(script_name, DEFAULT_SHARED_HOOK_TIMEOUT_SECONDS)


def configure_utf8_stdio() -> None:
    """Keep Codex hook transport Unicode-safe on Windows hosts.

    Python otherwise decodes redirected stdin with the active Windows code
    page.  Codex emits UTF-8 JSON, so non-ASCII workspace paths can make the
    dispatcher silently fail open before a shared hook sees the payload.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def plugin_root() -> Path:
    configured = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parent.parent


def hard_gate_policy(root: Path, script_name: str) -> tuple[dict[str, Any] | None, bool]:
    """Return a canonical hard-gate entry and whether the policy was readable.

    An unreadable policy is not equivalent to a soft/unregistered hook.  The
    caller must fail closed because it cannot safely downgrade the selected
    command while the trust registry is unavailable.
    """
    policy_paths = [
        root / "docs" / "HARNESS_TRUST_POLICY.json",
        Path(__file__).resolve().parent.parent / "docs" / "HARNESS_TRUST_POLICY.json",
    ]
    saw_valid = False
    for policy_path in dict.fromkeys(policy_paths):
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8"))
            gates = payload["hardGates"]
            if not isinstance(gates, list):
                continue
            saw_valid = True
            for gate in gates:
                if isinstance(gate, dict) and gate.get("script") == script_name:
                    return gate, True
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return None, saw_valid


def transport_failure(root: Path, script_name: str, reason: str) -> int:
    """Preserve graduated trust when the adapter itself cannot run a hook."""
    gate, policy_ok = hard_gate_policy(root, script_name)
    if gate is None and policy_ok:
        return 0
    event = str((gate or {}).get("event") or "PreToolUse")
    message = f"ITD high-risk hook transport failed closed: {script_name}: {reason}"
    if event == "SubagentStop":
        output = {"decision": "block", "reason": message}
    else:
        output = {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    print(json.dumps(output, ensure_ascii=False))
    return 2


def affected_paths(command: str) -> list[str]:
    return list(dict.fromkeys(path.strip() for path in PATCH_PATH_RE.findall(command)))


def normalized_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("tool_name") != "apply_patch":
        return [payload]
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "")
    paths = affected_paths(command)
    if not paths:
        clone = dict(payload)
        clone["tool_name"] = "Write"
        clone["tool_input"] = {"file_path": "", "content": command}
        return [clone]
    result = []
    for path in paths:
        clone = dict(payload)
        clone["tool_name"] = "Write"
        clone["tool_input"] = {
            "file_path": path,
            "content": command,
            "command": command,
        }
        result.append(clone)
    return result


def command_for(script: Path) -> list[str]:
    first_line = script.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    if "python" in first_line:
        return [sys.executable, str(script)]
    bash = shutil.which("bash")
    if bash:
        return [bash, str(script)]
    return [str(script)]


def approval_hash(script_name: str, payload: dict[str, Any]) -> str:
    """The hash of one exact call: the asking hook, the tool, its full input and the cwd.

    A missing field and an empty or null one hash differently: only present keys are bound.
    """
    binding: dict[str, Any] = {"script": script_name}
    for key in ("tool_name", "tool_input", "cwd"):
        if key in payload:
            binding[key] = payload[key]
    # ASCII-escaped JSON: a lone surrogate in the input hashes instead of raising (a crash would let the call run).
    text = json.dumps(binding, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def approvals_dir(session_id: str) -> Path:
    session_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
    return hook_lists_home() / APPROVALS_DIR / session_key


def windows_owned_by_user(path: Path) -> bool:
    """True when the file's owner SID is this process's user SID (TokenUser).

    The token's default owner is not accepted: on an elevated token it is the Administrators
    group, so a record owned by that group is refused (an elevated session gets no approvals).

    The DACL is not inspected: a store under the user profile inherits the profile's ACL.
    Any API failure is False, so a record that cannot be checked approves nothing.
    """
    try:
        import ctypes
        from ctypes import wintypes
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                              wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        advapi32.GetSecurityDescriptorOwner.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                                        ctypes.POINTER(wintypes.BOOL)]
        advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        owner_information = 0x1
        needed = wintypes.DWORD(0)
        advapi32.GetFileSecurityW(str(path), owner_information, None, 0, ctypes.byref(needed))
        if not needed.value:
            return False
        descriptor = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetFileSecurityW(str(path), owner_information, descriptor, needed,
                                         ctypes.byref(needed)):
            return False
        owner = ctypes.c_void_p()
        defaulted = wintypes.BOOL()
        if not advapi32.GetSecurityDescriptorOwner(descriptor, ctypes.byref(owner),
                                                   ctypes.byref(defaulted)) or not owner.value:
            return False
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x8, ctypes.byref(token)):
            return False
        try:
            for information_class in (1,):  # TokenUser: TOKEN_USER starts with the user SID pointer
                size = wintypes.DWORD(0)
                advapi32.GetTokenInformation(token, information_class, None, 0, ctypes.byref(size))
                if not size.value:
                    continue
                data = ctypes.create_string_buffer(size.value)
                if not advapi32.GetTokenInformation(token, information_class, data, size, ctypes.byref(size)):
                    continue
                sid = ctypes.c_void_p.from_buffer(data).value
                if sid and advapi32.EqualSid(owner, sid):
                    return True
        finally:
            kernel32.CloseHandle(token)
    except Exception:
        return False
    return False


def private_entry(path: Path, directory: bool) -> bool:
    """A real (not linked) entry of the expected type that only this OS user owns.

    POSIX: owned by this uid and not writable by group/other. Windows: no reparse point and
    owned by this user (windows_owned_by_user); the profile ACL is inherited, not inspected.
    """
    try:
        info = os.lstat(path)
    except OSError:
        return False
    # lstat: a symlink is neither S_ISDIR nor S_ISREG, so a linked entry is refused here.
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        return False
    if getattr(info, "st_file_attributes", 0) & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT (junction)
        return False
    getuid = getattr(os, "getuid", None)
    if getuid is not None:
        return info.st_uid == getuid() and not info.st_mode & 0o022
    return os.name == "nt" and windows_owned_by_user(path)


def private_approvals_dir(session_id: str, create: bool) -> Path | None:
    """The session's approval directory, or None when it or its parent is not private to this user."""
    directory = approvals_dir(session_id)
    for path in (directory.parent, directory):
        if create:
            try:
                os.mkdir(path, 0o700)
            except FileExistsError:
                pass
        if not private_entry(path, directory=True):
            return None
    return directory


def record_approvals(payload: dict[str, Any]) -> None:
    """Record each `ITD-APPROVE <hash>` line of the user's prompt; the model never writes this channel."""
    session_id = str(payload.get("session_id") or "")
    text = payload.get("prompt")
    if text is None:
        text = payload.get("user_prompt")
    if not session_id or not isinstance(text, str):
        return
    digests = dict.fromkeys(APPROVE_LINE_RE.findall(text))
    if not digests:
        return
    hook_lists_home().mkdir(parents=True, exist_ok=True)
    directory = private_approvals_dir(session_id, create=True)
    if directory is None:
        return  # a shared, linked or foreign directory records nothing
    for digest in digests:
        path = directory / f"{digest}.json"
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            continue  # the same prompt reaches every registered UserPromptSubmit hook
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"approvedAt": time.time()}, handle)


def touches_approval_channel(payload: dict[str, Any]) -> bool:
    """A tool call that names the approval channel: it could mint an approval outside the user's prompt.

    No tool input - a shell command, a file path or the content a file tool writes - may mention
    the ITD-APPROVE line, the approval store or a hand-made UserPromptSubmit for this dispatcher.
    A guardrail, not a boundary: an obfuscated command or a process with the OS user's rights
    that bypasses the hook transport can still write a record.
    """
    if payload.get("hook_event_name") != "PreToolUse":
        return False
    text = json.dumps(payload.get("tool_input") or {}, ensure_ascii=False).casefold()
    return ("itd-approve" in text or APPROVALS_DIR in text
            or ("userpromptsubmit" in text and "codex-dispatch" in text))


def deny_approval_channel() -> int:
    reason = ("[ITD APPROVAL CHANNEL] This call names the ITD-APPROVE channel or its store. Only the "
              "user's own chat line ITD-APPROVE <hash> grants an approval; a tool call never does.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))
    print(reason, file=sys.stderr)
    return 2


def approve_from_prompt(payload: dict[str, Any]) -> None:
    """UserPromptSubmit only, whether or not the hook it runs for is selected; a failed write approves nothing."""
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return
    try:
        record_approvals(payload)
    except (OSError, RuntimeError):
        pass


def consume_approval(session_id: str, digest: str) -> bool:
    """True once for a fresh approval of this exact hash in this session; the record is spent either way."""
    if not session_id:
        return False
    directory = private_approvals_dir(session_id, create=False)
    if directory is None:
        return False
    path = directory / f"{digest}.json"
    if not private_entry(path, directory=False):
        return False
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        path.unlink()
    except OSError:
        return False  # another hook process spent it first
    try:
        approved_at = float(json.loads(raw)["approvedAt"])
    except (ValueError, KeyError, TypeError):
        return False  # a malformed record is spent too, so the user can approve the call again
    age = time.time() - approved_at
    return 0 <= age <= APPROVAL_TTL_SECONDS


def deny_ask(merged: dict[str, Any], script_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    reason = str((merged.get("hookSpecificOutput") or {}).get("permissionDecisionReason") or "")
    if payload.get("session_id"):
        answer = (f"Codex cannot ask natively, so this call is denied. To allow exactly this call once "
                  f"(30 minutes), the user replies in the chat with the line:\n"
                  f"ITD-APPROVE {approval_hash(script_name, payload)}\n"
                  f"then retry the call unchanged. Do not write this line yourself.")
    else:
        answer = "Codex cannot ask natively and the call has no session provenance, so it cannot be approved."
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (reason + "\n\n" if reason else "") + answer,
        }
    }


def merge_json(outputs: list[dict[str, Any]], event: str) -> dict[str, Any] | None:
    if not outputs:
        return None
    for item in outputs:
        specific = item.get("hookSpecificOutput") or {}
        if specific.get("permissionDecision") == "deny" or item.get("decision") == "block":
            return item

    asks = [item for item in outputs
            if (item.get("hookSpecificOutput") or {}).get("permissionDecision") == "ask"]
    if asks:
        reasons = [str((item.get("hookSpecificOutput") or {}).get(
            "permissionDecisionReason") or "") for item in asks]
        asked: dict[str, Any] = {
            "hookSpecificOutput": {
                "hookEventName": event,
                "permissionDecision": "ask",
                "permissionDecisionReason": "\n".join(
                    dict.fromkeys(reason for reason in reasons if reason)),
            }
        }
        contexts = [str((item.get("hookSpecificOutput") or {}).get("additionalContext") or "")
                    for item in outputs]
        if any(contexts):
            asked["hookSpecificOutput"]["additionalContext"] = "\n".join(
                dict.fromkeys(context for context in contexts if context))
        return asked

    contexts: list[str] = []
    messages: list[str] = []
    should_continue = True
    stop_reasons: list[str] = []
    for item in outputs:
        specific = item.get("hookSpecificOutput") or {}
        context = specific.get("additionalContext")
        if context:
            contexts.append(str(context))
        if item.get("systemMessage"):
            messages.append(str(item["systemMessage"]))
        if item.get("continue") is False:
            should_continue = False
        if item.get("stopReason"):
            stop_reasons.append(str(item["stopReason"]))

    merged: dict[str, Any] = {}
    if contexts:
        merged["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": "\n".join(dict.fromkeys(contexts)),
        }
    if messages:
        merged["systemMessage"] = "\n".join(dict.fromkeys(messages))
    if not should_continue:
        merged["continue"] = False
    if stop_reasons:
        merged["stopReason"] = "\n".join(dict.fromkeys(stop_reasons))
    return merged or None


def main() -> int:
    configure_utf8_stdio()
    args = parse_args()
    root = plugin_root()
    if not selected_for_user(args.script):
        raw = sys.stdin.read()
        try:
            skipped = json.loads(raw)
        except ValueError:
            return 0
        if isinstance(skipped, dict):
            approve_from_prompt(skipped)
            if touches_approval_channel(skipped):
                return deny_approval_channel()  # the guard holds even for a switched-off hook
        return 0
    try:
        payload = json.load(sys.stdin) or {}
    except Exception:
        return transport_failure(root, args.script, "invalid hook payload")
    approve_from_prompt(payload)
    if touches_approval_channel(payload):
        return deny_approval_channel()

    script = (root / "hooks" / args.script).resolve()
    hooks_root = (root / "hooks").resolve()
    if hooks_root not in script.parents:
        print(f"Invalid shared hook path: {args.script}", file=sys.stderr)
        return 2
    if not script.is_file():
        return transport_failure(root, args.script, "shared hook file is missing")

    env = os.environ.copy()
    env["ITD_HOST"] = "codex"
    env["PYTHONUTF8"] = "1"
    env.setdefault("PLUGIN_ROOT", str(root))
    env.setdefault("CLAUDE_PLUGIN_ROOT", str(root))
    if payload.get("session_id"):
        env["CLAUDE_SESSION_ID"] = str(payload["session_id"])

    json_outputs: list[dict[str, Any]] = []
    stderr_parts: list[str] = []
    worst_code = 0
    deadline = time.monotonic() + shared_hook_timeout(args.script)
    for normalized in normalized_payloads(payload):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return transport_failure(root, args.script, "shared hook deadline exhausted")
        try:
            proc = subprocess.run(
                command_for(script),
                input=json.dumps(normalized, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=str(Path(payload.get("cwd") or os.getcwd())),
                env=env,
                timeout=remaining,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return transport_failure(root, args.script, type(exc).__name__)
        if proc.returncode not in (0, 2):
            return transport_failure(root, args.script, f"shared hook exited {proc.returncode}")
        worst_code = 2 if proc.returncode == 2 else max(worst_code, proc.returncode)
        if proc.stderr.strip():
            stderr_parts.append(proc.stderr.strip())
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
                if isinstance(parsed, dict):
                    json_outputs.append(parsed)
            except json.JSONDecodeError:
                # Plain text is valid context on some lifecycle events.
                json_outputs.append({"systemMessage": proc.stdout.strip()})
        if proc.returncode == 2:
            break

    merged = merge_json(json_outputs, str(payload.get("hook_event_name") or "PreToolUse"))
    if merged and (merged.get("hookSpecificOutput") or {}).get("permissionDecision") == "ask":
        if consume_approval(str(payload.get("session_id") or ""), approval_hash(args.script, payload)):
            # The approved call runs; advisory context of the hooks still reaches the model.
            context = merged["hookSpecificOutput"].get("additionalContext")
            if context:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                         "additionalContext": context}},
                                 ensure_ascii=False))
            return 0
        denial = deny_ask(merged, args.script, payload)
        print(json.dumps(denial, ensure_ascii=False))
        print(denial["hookSpecificOutput"]["permissionDecisionReason"], file=sys.stderr)
        return 2
    if merged:
        print(json.dumps(merged, ensure_ascii=False))
    if stderr_parts:
        print("\n".join(dict.fromkeys(stderr_parts)), file=sys.stderr)
    return worst_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        configure_utf8_stdio()
        root = plugin_root()
        script_name = "unknown"
        try:
            script_name = parse_args().script
        except SystemExit:
            pass
        raise SystemExit(transport_failure(root, script_name, type(exc).__name__))
