#!/usr/bin/env python3
"""Exact preview and session-bound approval for external writes.

The engine is host-neutral: adapters pass a hook-shaped payload, while this
module classifies the action and builds the canonical preview without storing
approval state. The host-native PreToolUse `ask` decision is the trusted
confirmation boundary. No arguments is a quiet no-op.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "skills" / "_shared" / "WORKING_DEADLINE_POLICY.json"
WRITE_VERBS = {
    "add", "approve", "archive", "cancel", "close", "comment", "copy",
    "create", "delete", "draft", "edit", "forward", "invite", "label",
    "merge", "move", "post", "publish", "push", "remove", "reply",
    "resolve", "restore", "schedule", "send", "set", "share", "submit", "mark",
    "transfer", "update", "upload", "write",
}
READ_VERBS = {
    "download", "export", "fetch", "find", "get", "inspect", "list",
    "lookup", "open", "query", "read", "retrieve", "search", "show",
    "screenshot", "snapshot", "status", "view",
}
LOCAL_TOOLS = {
    "agent", "apply_patch", "bash", "edit", "glob", "grep", "notebookedit",
    "powershell", "read", "skill", "task", "write",
}
LOCAL_MCP_PREFIXES = {
    # Local compute transport exposed by Codex. It has no connector target and
    # must not be mistaken for an unknown remote mutation merely because its
    # native tool name starts with ``mcp__``.
    "mcp_node_repl_",
}
# Built-in Claude desktop host tools (raw ``mcp__<server>__<tool>`` names)
# that only drive the local app UI. Every other tool of a ccd server, such as
# permission, settings, connector, worktree, cloud or PR tools, keeps the
# generic connector classification.
HOST_LOCAL_MCP_TOOLS = {
    ("ccd_turn", "update_plan"), ("ccd_turn", "wrap_up"),
    ("ccd_session", "dismiss_task"), ("ccd_session", "mark_chapter"),
    ("ccd_session", "read_widget_context"), ("ccd_session", "spawn_task"),
    ("ccd_view", "close_pane"), ("ccd_view", "get_layout"),
    ("ccd_view", "set_transcript_view"), ("ccd_view", "show_pane"),
    ("ccd_window", "close_split"), ("ccd_window", "get_window_layout"),
    ("ccd_window", "open_session_in"), ("ccd_window", "set_sidebar_collapsed"),
    ("ccd_sidebar", "create_group"), ("ccd_sidebar", "create_section"),
    ("ccd_sidebar", "list_groups"), ("ccd_sidebar", "list_sections"),
    ("ccd_sidebar", "mark_completed"), ("ccd_sidebar", "move_sessions"),
    ("ccd_sidebar", "rename_group"), ("ccd_sidebar", "rename_section"),
    ("ccd_sidebar", "set_pinned"), ("ccd_sidebar", "set_unread"),
    ("ccd_sidebar", "set_view"),
    ("ccd_host", "get_storage_usage"), ("ccd_host", "open_in_editor"),
    ("ccd_host", "request_keep_awake"), ("ccd_host", "reveal_path"),
}
# context-mode (mksglu/context-mode): its executors run code on this machine,
# so their code gets the same text classification as a Bash command (which
# also sees ``python -c "..."`` source). Its knowledge-base tools are local;
# other tools keep the generic connector classification.
CONTEXT_MODE_SERVERS = {"context_mode", "plugin_context_mode_context_mode"}
CONTEXT_MODE_EXECUTORS = {"ctx_batch_execute", "ctx_execute", "ctx_execute_file"}
CONTEXT_MODE_LOCAL_TOOLS = {
    "ctx_doctor", "ctx_index", "ctx_purge", "ctx_search", "ctx_stats",
}
EXTERNAL_PROVIDERS = {
    "atlassian", "box", "browser", "calendar", "chrome", "drive", "figma",
    "github", "gmail", "google", "linear", "notion", "outlook", "sharepoint",
    "slack", "teams",
}
TARGET_KEYS = {
    "assignee", "assignees", "attendee", "attendees", "bcc", "branch", "calendar", "calendar_id",
    "cc", "channel", "channel_id", "destination", "email", "emails",
    "file_id", "folder_id", "issue", "issue_id", "issue_number", "owner",
    "parent", "parent_id", "project", "project_id", "recipient", "recipients",
    "ref", "remote", "repo", "repo_full_name", "repository",
    "repository_full_name", "resource", "resource_id", "room",
    "room_id", "site", "target", "targets", "team", "team_id", "thread_id",
    "to", "url", "uri", "user", "user_id",
}
ATTACHMENT_KEYS = {"attachment", "attachments", "file_ids", "files", "uploads"}
URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
CURL_WRITE_RE = re.compile(
    r"(?:^|\s)--(?:request|method)(?:\s+|=)(?:POST|PUT|PATCH|DELETE)\b|"
    r"(?:^|\s)--(?:data(?:-ascii|-raw|-binary|-urlencode)?|form(?:-string)?|"
    r"upload-file|json)(?:\s+|=)",
    re.IGNORECASE,
)
CURL_SHORT_WRITE_RE = re.compile(
    r"(?:^|\s)-X\s*(?i:POST|PUT|PATCH|DELETE)\b|"
    r"(?:^|\s)-(?:d|F|T)(?:\S*)")
WGET_WRITE_RE = re.compile(
    r"(?:^|\s)--(?:method(?:\s+|=)(?:POST|PUT|PATCH|DELETE)|"
    r"post-(?:data|file)|body-(?:data|file))(?:\s+|=)?",
    re.IGNORECASE,
)
READ_HTTP_METHOD_RE = re.compile(
    r"(?:^|\s)(?:-X|--request|--method)(?:\s+|=)(?:GET|HEAD|OPTIONS)\b",
    re.IGNORECASE,
)
POWERSHELL_HTTP_RE = re.compile(
    r"\b(?:Invoke-RestMethod|Invoke-WebRequest|irm|iwr)\b", re.IGNORECASE)
POWERSHELL_WRITE_RE = re.compile(
    r"(?:^|\s)-Method(?:\s+|[:=])(?:POST|PUT|PATCH|DELETE)\b|"
    r"(?:^|\s)-(?:Body|Form|InFile)(?:\s+|:|=)",
    re.IGNORECASE,
)
GH_API_WRITE_RE = re.compile(
    r"(?:^|\s)(?:-X|--method)(?:\s+|=)(?:POST|PUT|PATCH|DELETE)\b|"
    r"(?:^|\s)(?:-f|-F|--field|--raw-field|--input)(?:\s+|=)",
    re.IGNORECASE,
)
# Shell narrowing. The word checks below stay the baseline; a match is dropped
# only when the command provably cannot run the program it names.
COMPLEX_SHELL_RE = re.compile(r"[`()]|\$\{|<<|--%")
SEPARATOR_RE = re.compile(r"\|\||&&|;|\n|(?<![<>])&(?!>)|(?<!>)\|&?")
# The usual agent commit: a commit message from a quoted-delimiter heredoc,
# which keeps the body literal. Only this exact shape is accepted.
COMMIT_HEREDOC_RE = re.compile(
    r"\s*(?:cd [\w./~-]+ && )?(?:git add [\w./ -]+ && )?"
    r"git commit(?: --?[\w-]+)* -m \"\$\(cat <<'(?P<tag>[A-Za-z_]\w*)'\n"
    r"(?P<body>.*)\n(?P=tag)\n\)\"\s*",
    re.DOTALL)
# Utilities that read or print local data and never run another program; a
# pipeline made only of them cannot hand flags to curl or wget.
INERT_UTILITIES = {
    "[", "basename", "cd", "cut", "date", "dirname", "head", "ls", "mkdir",
    "pwd", "realpath", "sleep", "stat", "tail", "test", "tr", "uniq", "wc",
}
# Programs that only read or print local data and never run another program
# (no rg: --pre; no sort: --compress-program; no find: -exec; no file: -z).
# In a command made only of them a transport word is an argument, never the
# program run. Matched case-sensitively, like the search narrowing.
NON_EXECUTING_PROGRAMS = {
    "[", "Get-ChildItem", "Get-Content", "Test-Path", "basename", "cat", "cd",
    "cut", "dir", "dirname", "du", "egrep", "fgrep", "gc", "gci", "grep",
    "head", "ls", "md5sum", "nl", "pwd", "readlink", "realpath", "sha256sum",
    "stat", "tail", "test", "tr", "tree", "type", "uniq", "wc",
}
# Output thrown away: a whole ">/dev/null" (optionally with one descriptor
# digit and spaces before the path) or "2>&1", also glued to the previous
# argument; never a longer path (">/dev/nullX") nor "&>", "*>", a
# multi-digit descriptor or an escaped character ("Q" after _mask_quotes).
NULL_REDIRECT_RE = r"(?<![&*\dQ])(?:\d?>\s*/dev/null|2>&1)(?![^\s;&|<>()])"
SEARCH_PROGRAMS = {"egrep", "fgrep", "grep", "rg"}
SEARCH_FILTERS = {"cut", "head", "nl", "tail", "tr", "uniq", "wc"}
LOCAL_GIT_SUBCOMMANDS = {
    "add", "commit", "diff", "log", "restore", "show", "stash", "status",
}
GH_READ_ACTIONS = {
    "browse", "checks", "checkout", "clone", "diff", "download", "list",
    "status", "view", "watch",
}
GH_WRITE_ACTIONS = {
    "approve", "archive", "cancel", "close", "comment", "create", "delete",
    "disable", "edit", "enable", "lock", "merge", "pin", "publish", "ready",
    "reopen", "rerun", "review", "run", "set", "submit", "transfer",
    "unlock", "unpin", "update", "upload",
}


class GateError(ValueError):
    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_tool_name(value: Any) -> str:
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or "").strip())
    name = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return {"power_shell": "powershell", "web_fetch": "webfetch"}.get(name, name)


def load_policy() -> dict[str, Any]:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GateError(
            f"external-write policy is unavailable: {exc}",
            "Restore WORKING_DEADLINE_POLICY.json before attempting an external write.",
        ) from exc
    external = policy.get("externalWrites") or {}
    required_true = (
        "exactPreviewRequired", "exactTargetsRequired", "fullPayloadRequired",
        "attachmentsIncluded", "sessionProvenanceRequired",
        "invalidateOnPayloadOrTargetChange",
    )
    if (policy.get("id") != "working-deadline-v1"
            or any(external.get(field) is not True for field in required_true)
            or external.get("approvalBinding")
            != "sha256-canonical-tool-name-targets-payload"
            or external.get("readOnlyRequiresWriteApproval") is not False
            or external.get("exactAlreadyAuthorizedActionRequiresRepeatApproval") is not False):
        raise GateError(
            "external-write policy is malformed or weakened",
            "Restore the frozen policy; do not infer a permissive approval path.",
        )
    return external


def session_id(payload: dict[str, Any], explicit: str | None = None) -> str:
    return str(explicit or payload.get("session_id")
               or os.environ.get("CLAUDE_SESSION_ID") or "").strip()


def _tokens(tool_name: str) -> set[str]:
    return {token for token in tool_name.split("_") if token}


def looks_external(tool_name: str) -> bool:
    if any(tool_name.startswith(prefix) for prefix in LOCAL_MCP_PREFIXES):
        return False
    tokens = _tokens(tool_name)
    return tool_name.startswith(("mcp_", "connector_", "app_")) \
        or bool(tokens & EXTERNAL_PROVIDERS)


def connector_action(tool_name: str) -> str:
    parts = [part for part in tool_name.split("_") if part]
    transported = bool(parts and parts[0] in {"app", "connector", "mcp"})
    # Codex app tools use mcp__codex_apps__<provider>__<action>; Claude-style
    # MCP tools use mcp__<provider>__<action>. Remove every transport wrapper,
    # then the provider/server namespace, before interpreting the action.
    while parts and parts[0] in {"app", "apps", "codex", "connector", "mcp"}:
        parts.pop(0)
    if transported and parts and parts[0] not in EXTERNAL_PROVIDERS:
        parts.pop(0)
    while parts and parts[0] in EXTERNAL_PROVIDERS:
        parts.pop(0)
    # Composite provider namespaces (for example atlassian_rovo) may leave a
    # non-semantic token ahead of the verb. Prefer the first explicit effect
    # verb while preserving order: mark_*_read stays a write, not a read.
    for part in parts:
        if part in WRITE_VERBS or part in READ_VERBS:
            return part
    return parts[0] if parts else ""


def _shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def _program_name(token: str) -> str:
    return re.split(r"[/\\]", token)[-1].lower().removesuffix(".exe")


def _program_indexes(tokens: list[str], program: str) -> list[int]:
    return [index for index, token in enumerate(tokens)
            if _program_name(token) == program]


def _git_subcommands(tokens: list[str]) -> list[str]:
    commands: list[str] = []
    value_options = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                     "--super-prefix", "--config-env"}
    for git_index in _program_indexes(tokens, "git"):
        skip_next = False
        for token in tokens[git_index + 1:]:
            if skip_next:
                skip_next = False
                continue
            option = token.split("=", 1)[0]
            if option in value_options and "=" not in token:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            commands.append(token.lower())
            break
    return commands


def _gh_parts(tokens: list[str]) -> list[str]:
    indexes = _program_indexes(tokens, "gh")
    if not indexes:
        return []
    value_options = {
        "-R", "--repo", "--hostname", "-X", "--method", "-f", "-F",
        "--field", "--raw-field", "--input", "--header", "-H", "--cache",
        "--json", "--jq", "-q", "--template", "-t", "--limit", "-L",
    }
    parts: list[str] = []
    skip_next = False
    for token in tokens[indexes[0] + 1:]:
        if skip_next:
            skip_next = False
            continue
        option = token.split("=", 1)[0]
        if option in value_options and "=" not in token:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        parts.append(token)
    return parts


@functools.lru_cache(maxsize=8)
def _mask_quotes(command: str) -> str | None:
    """Same-length copy with quoted text and escapes replaced by ``Q``.

    The same command may run under bash, PowerShell (Codex reports its
    Windows shell as ``Bash``) or cmd, so anything they read differently
    returns None and callers keep the whole-text checks: comments,
    ``$'...'``, a backslash before a special character, ``\\"`` or a command
    substitution inside a double-quoted string, ``^`` escapes, typographic
    quotes, line breaks other than ``\\n`` (PowerShell ends a statement at a
    lone CR), single-quoted text with shell punctuation (cmd has no single
    quotes) and unbalanced quoting.
    """
    if re.search("[‘-‟^\r\x0b\x0c\x85  ]", command):
        return None
    out = list(command)
    index = 0
    while index < len(command):
        char = command[index]
        if char == "#" or command.startswith("$'", index):
            return None
        if char == "\\":
            if index + 1 >= len(command) or command[index + 1] in ";&|'\"`#<>()$\r\n":
                return None
            end = index + 2
        elif char == "'":
            end = command.find("'", index + 1) + 1
            if not end or re.search(r"[;&|<>()\n\"]", command[index:end]):
                return None
        elif char == '"':
            end = index + 1
            while end < len(command) and command[end] != '"':
                if command.startswith('\\"', end):
                    return None
                end += 2 if command[end] == "\\" else 1
            # PowerShell keeps a backslash literal, so even ``\$(`` expands.
            if end >= len(command) or "$(" in command[index:end] \
                    or "`" in command[index:end]:
                return None
            end += 1
        else:
            index += 1
            continue
        out[index:end] = "Q" * (end - index)
        index = end
    return "".join(out)


def _simple_commands(command: str) -> list[tuple[str, str]] | None:
    """(raw text, separator before it) of each top-level simple command.

    None for substitutions, subshells, functions, heredocs, parameter
    expansions or uncertain quoting, which keep the whole-text checks.
    """
    masked = _mask_quotes(command)
    if masked is None or COMPLEX_SHELL_RE.search(masked):
        return None
    commands: list[tuple[str, str]] = []
    start, separator = 0, ""
    for match in SEPARATOR_RE.finditer(masked):
        commands.append((command[start:match.start()], separator))
        start, separator = match.end(), match.group()
    commands.append((command[start:], separator))
    return [(text, sep) for text, sep in commands if text.strip()]


def _http_scope(command: str) -> str:
    """Text whose curl/wget flags count.

    Drops only pipelines made entirely of inert utilities without curl/wget
    text (``ls -d out``, ``cut -d, -f1 f``); everything else, including
    assignments, ``set``, loops and runners, stays.
    """
    commands = _simple_commands(command)
    if commands is None:
        return command
    pipelines: list[list[str]] = []
    for text, separator in commands:
        if pipelines and separator in {"|", "|&"}:
            pipelines[-1].append(text)
        else:
            pipelines.append([text])
    # A redirected inert command can still write a curl config (~/.curlrc).
    return "\n".join(
        text for pipeline in pipelines
        if not all(text.split()[0] in INERT_UTILITIES
                   and not re.search(r"curl|wget", text, re.IGNORECASE)
                   and ">" not in re.sub(NULL_REDIRECT_RE, "", text)
                   for text in pipeline)
        for text in pipeline)


def _search_only(command: str) -> bool:
    """A grep search (or rg --no-config), optionally piped through text filters.

    It only reads local files, so words in its patterns name nothing to run.
    """
    commands = _simple_commands(command)
    masked = _mask_quotes(command)
    if not commands or masked is None:
        return False
    masked = re.sub(NULL_REDIRECT_RE, " ", masked)
    # rg runs --pre and --hostname-bin programs; quotes do not hide the flag.
    if re.search(r"[<>]", masked) or re.search(r"--pre|--hostname-bin", command):
        return False
    # The bare program name only: a path or a VAR=value prefix (PATH=...) can
    # run a different program under the same name.
    for index, (text, separator) in enumerate(commands):
        allowed = SEARCH_FILTERS if index else SEARCH_PROGRAMS
        if (index and separator != "|") or text.split()[0] not in allowed:
            return False
    # rg also reads options from RIPGREP_CONFIG_PATH, where a --pre runs a
    # program; only --no-config as its first argument rules that out.
    words = commands[0][0].split()
    return words[0] != "rg" or words[1:2] == ["--no-config"]


def _local_git_only(command: str) -> bool:
    """cd and local git commands (add, commit, status, ...) chained by && or ;.

    Quoted text there is commit data, not a command to run; so is the body of
    the usual quoted-delimiter heredoc commit message.
    """
    heredoc = COMMIT_HEREDOC_RE.fullmatch(command)
    if heredoc:
        tag = heredoc.group("tag")
        return not any(line.lstrip().startswith(tag)
                       for line in heredoc.group("body").split("\n"))
    commands = _simple_commands(command)
    if not commands:
        return False
    for text, separator in commands:
        words = text.split()
        if separator not in {"", "&&", ";", "\n"}:
            return False
        if words[0] == "cd" and len(words) <= 2:
            continue
        rest = words[1:]
        if rest[:1] == ["-C"]:
            rest = rest[2:]
        if words[0] != "git" or not rest \
                or rest[0] not in LOCAL_GIT_SUBCOMMANDS:
            return False
    return True


def _non_executing(command: str) -> bool:
    """Every simple command starts with a bare program that runs nothing else.

    Redirections, script blocks, UNC paths and whatever ``_simple_commands``
    cannot split (substitutions, ``${...}``, subshells, heredocs, uncertain
    quoting) keep the whole-text checks.
    """
    commands = _simple_commands(command)
    masked = _mask_quotes(command)
    if not commands or masked is None:
        return False
    masked = re.sub(NULL_REDIRECT_RE, " ", masked)
    if re.search(r"[<>{}]|(?:^|\s)(?:\\\\|//)", masked):
        return False
    return all(text.split()[0] in NON_EXECUTING_PROGRAMS for text, _ in commands)


def _names_program(command: str, pattern: str) -> bool:
    """True when some word match may name a program to run.

    In a command that runs nothing else (``_non_executing``) a match is not a
    program when it is a hidden name (``~/.ssh``), a directory component
    (``.../ssh-d2719c3f/x``, ``rsync-logs/``) or the last path component with
    a generated hex id (``/tmp/ssh-d2719c3f``). Anywhere else every match
    counts: an expansion (``${x#.}``), a pipeline into a shell, sed or xargs
    can turn such a path into the program name. The same name at command
    position (``ssh-1a2b3c4d host``, bash ``\\ssh-1a2b3c4d``) and other
    hyphenated names, such as ``ssh-copy-id`` or ``rsync-ssl``, still count.
    """
    lowered = command.lower()
    if not _non_executing(command):
        return bool(re.search(pattern, lowered))
    for match in re.finditer(pattern, lowered):
        before = lowered[match.start() - 1:match.start()]
        rest = re.match(r"[\w.~/\\-]*", lowered[match.end():]).group()
        # A backslash is a path separator only after a path word; after a
        # space, an operator or an expansion (``$x\``) bash reads it as an
        # escape of a bare name.
        word = re.search(r"[\w.~:\\/-]*\\\Z", lowered[:match.start()])
        in_path = before == "/" or bool(
            word and re.match(r"[\w.~:-]", word.group())
            and lowered[word.start() - 1:word.start()] != "$")
        if before == "." or "/" in rest or "\\" in rest \
                or (in_path and re.match(
                    r"-(?=[0-9a-f]*\d)[0-9a-f]{6,}(?![g-z])", rest)):
            continue
        return True
    return False


def classify_shell(command: str) -> tuple[str, str]:
    lowered = command.lower()
    tokens = _shell_tokens(command)
    git_commands = _git_subcommands(tokens)
    if "push" in git_commands or any(
            command_name == "send-email" for command_name in git_commands):
        return "write", "git push mutates a remote repository"
    if _search_only(command):
        return "local", "search command only reads local files"
    if _local_git_only(command):
        return "local", "local git commands carry quoted text as data"
    if re.search(r"\b(?:curl|wget)\b", lowered):
        scope = _http_scope(command)
        if (CURL_WRITE_RE.search(scope) or CURL_SHORT_WRITE_RE.search(scope)
                or WGET_WRITE_RE.search(scope)):
            return "write", "HTTP request carries a mutating method or body"
        if READ_HTTP_METHOD_RE.search(scope) or not re.search(
                r"(?:^|\s)(?:-X|--request|--method)(?:\s+|=)", scope,
                re.IGNORECASE):
            return "read", "HTTP GET/download is read-only for the remote target"
        return "unknown", "HTTP method cannot be proven read-only"
    if POWERSHELL_HTTP_RE.search(command):
        if POWERSHELL_WRITE_RE.search(command):
            return "write", "PowerShell web request carries a mutating method or body"
        if re.search(r"(?:^|\s)-Method(?:\s+|[:=])(?:GET|HEAD|OPTIONS)\b",
                     command, re.IGNORECASE) or "-method" not in lowered:
            return "read", "PowerShell web request is provably read-only"
        return "unknown", "PowerShell web request method cannot be proven read-only"
    gh_parts = _gh_parts(tokens)
    if gh_parts and gh_parts[0].lower() == "api":
        if GH_API_WRITE_RE.search(command):
            return "write", "GitHub API command carries a mutating method or body"
        return "read", "GitHub API inspection is read-only"
    if gh_parts:
        group = gh_parts[0].lower()
        action = gh_parts[1].lower() if len(gh_parts) > 1 else ""
        if group in {"browse", "search", "status"} or action in GH_READ_ACTIONS:
            return "read", "GitHub CLI inspection is read-only"
        if action in GH_WRITE_ACTIONS:
            return "write", "GitHub CLI command mutates remote state"
        return "unknown", "GitHub CLI action cannot be proven read-only"
    if _names_program(command, r"\b(?:scp|sftp|rsync)\b"):
        operands = [token for token in tokens[1:] if not token.startswith("-")]
        if operands and re.search(r"[^/\s]+:.+", operands[-1]):
            return "write", "file transfer destination is remote"
        if operands and re.search(r"[^/\s]+:.+", operands[0]):
            return "read", "file transfer source is remote and destination is local"
        return "unknown", "file-transfer direction cannot be proven"
    if _names_program(command, r"\bssh\b"):
        return "unknown", "remote shell command may mutate external state"
    if _names_program(command, r"\b(?:nc|ncat|telnet)\b"):
        return "unknown", "raw network transport may mutate external state"
    return "local", "shell command has no external mutation signal"


def _mcp_parts(raw_tool: str) -> tuple[str, str]:
    """(server, tool) of a raw ``mcp__<server>__<tool>`` name."""
    parts = raw_tool.split("__")
    if len(parts) == 3 and parts[0] == "mcp":
        return parts[1], parts[2]
    return "", ""


def _context_mode_server(server: str) -> bool:
    return re.sub(r"[^a-z0-9]+", "_", server.lower()) in CONTEXT_MODE_SERVERS


def shell_commands(raw_tool: str, tool_input: dict[str, Any]) -> list[str] | None:
    """Command or code texts the tool runs on this machine, else None.

    An executor input without the expected text field keeps the generic tool
    classification: the source it would run is not in the payload.
    """
    if raw_tool in {"Bash", "PowerShell"} \
            or canonical_tool_name(raw_tool) in {"bash", "powershell"}:
        return [str(tool_input.get("command") or "")]
    server, name = _mcp_parts(raw_tool)
    if not (_context_mode_server(server) and name in CONTEXT_MODE_EXECUTORS):
        return None
    if name != "ctx_batch_execute":
        code = tool_input.get("code")
        return [code] if isinstance(code, str) else None
    commands = tool_input.get("commands")
    items = commands if isinstance(commands, list) else [commands]
    if not all(isinstance(item, dict) and isinstance(item.get("command"), str)
               for item in items):
        return None
    return [item["command"] for item in items]


def classify(payload: dict[str, Any]) -> tuple[str, str]:
    raw_tool = str(payload.get("tool_name") or "")
    tool = canonical_tool_name(raw_tool)
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return "unknown", "tool input is not an object"
    commands = shell_commands(raw_tool, tool_input)
    if commands is not None:
        rank = {"local": 0, "read": 1, "unknown": 2, "write": 3}
        return max((classify_shell(command) for command in commands),
                   key=lambda result: rank[result[0]],
                   default=("local", "shell command has no external mutation signal"))
    if raw_tool == "WebFetch" or tool in {"webfetch", "web_run"}:
        return "read", "web lookup transport is read-only"
    if raw_tool in {"Read", "Glob", "Grep"} or tool in LOCAL_TOOLS:
        return "local", "local harness tool does not mutate an external system"
    server, name = _mcp_parts(raw_tool)
    if (server, name) in HOST_LOCAL_MCP_TOOLS:
        return "local", "built-in host tool drives the local app"
    if _context_mode_server(server) and name in CONTEXT_MODE_LOCAL_TOOLS:
        return "local", "context-mode knowledge-base tool is local"
    if not looks_external(tool):
        return "local", "tool has no external connector namespace"
    action = connector_action(tool)
    if action in WRITE_VERBS:
        return "write", "connector action name contains a mutating verb"
    if action in READ_VERBS:
        return "read", "connector action name is provably read-only"
    return "unknown", "external connector action has no provable read-only semantics"


def _target_key(key: str) -> bool:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower().replace("-", "_")
    return (normalized in TARGET_KEYS or normalized.endswith("_target")
            or normalized.endswith("_target_id")
            or normalized.endswith("_recipient")
            or normalized.endswith("_recipient_id")
            or normalized.endswith("_id") or normalized.endswith("_ids"))


def _walk_targets(value: Any, path: str = "") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            child_path = f"{path}.{key}" if path else key
            if _target_key(str(key)) and child not in (None, "", [], {}):
                found.append({"path": child_path, "key": str(key), "value": child})
            elif isinstance(child, (dict, list)):
                found.extend(_walk_targets(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_targets(child, f"{path}[{index}]"))
    return found


def _walk_attachments(value: Any, path: str = "") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            child_path = f"{path}.{key}" if path else key
            if str(key).lower() in ATTACHMENT_KEYS and child not in (None, "", [], {}):
                found.append({"path": child_path, "value": child})
            elif isinstance(child, (dict, list)):
                found.extend(_walk_attachments(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_attachments(child, f"{path}[{index}]"))
    return found


def shell_targets(command: str) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    urls = URL_RE.findall(command)
    for index, url in enumerate(urls):
        targets.append({"path": f"command.url[{index}]", "key": "url", "value": url})
    tokens = _shell_tokens(command)
    push_operands: list[str] = []
    push_index = -1
    if "push" in _git_subcommands(tokens):
        for git_index in _program_indexes(tokens, "git"):
            for index in range(git_index + 1, len(tokens)):
                if tokens[index].lower() == "push":
                    push_index = index
                    break
            if push_index >= 0:
                break
    if push_index >= 0:
        options_with_values = {"-o", "--push-option", "--receive-pack", "--exec"}
        skip_next = False
        for token in tokens[push_index + 1:]:
            if skip_next:
                skip_next = False
                continue
            option = token.split("=", 1)[0]
            if option in options_with_values and "=" not in token:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            push_operands.append(token)
    if len(push_operands) >= 2:
        targets.extend([
            {"path": "command.remote", "key": "remote", "value": push_operands[0]},
            {"path": "command.ref", "key": "ref", "value": push_operands[1]},
        ])
    gh_parts = _gh_parts(tokens)
    if len(gh_parts) >= 2 and gh_parts[0].lower() == "api":
        targets.append({"path": "command.api", "key": "api", "value": gh_parts[1]})
    repo = re.search(r"(?:--repo|-R)(?:=|\s+)([^\s]+)", command)
    if repo:
        targets.append({"path": "command.repo", "key": "repo", "value": repo.group(1)})
        if (len(gh_parts) >= 3
                and gh_parts[0].lower() in {"issue", "pr", "release", "run", "workflow"}):
            resource_kind = gh_parts[0].lower()
            targets.append({
                "path": f"command.{resource_kind}",
                "key": resource_kind,
                "value": gh_parts[2],
            })
    ssh = re.search(r"\bssh\s+(?:-[^\s]+\s+)*([^\s]+)", command)
    if ssh:
        targets.append({"path": "command.host", "key": "host", "value": ssh.group(1)})
    return targets


def build_preview(payload: dict[str, Any]) -> dict[str, Any]:
    load_policy()
    if not isinstance(payload, dict):
        raise GateError("tool request must be a JSON object", "Pass the complete hook payload.")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise GateError("tool_input must be a JSON object", "Pass the complete structured payload.")
    tool_name = canonical_tool_name(payload.get("tool_name"))
    if not tool_name:
        raise GateError("canonical tool name is missing", "Provide the exact tool_name.")
    effect, reason = classify(payload)
    commands = shell_commands(str(payload.get("tool_name") or ""), tool_input)
    targets = (shell_targets("\n".join(commands)) if commands is not None
               else _walk_targets(tool_input))
    targets = sorted(targets, key=canonical_json)
    attachment_entries = _walk_attachments(tool_input)
    attachments: list[Any] = []
    for entry in attachment_entries:
        value = entry["value"]
        attachments.extend(value if isinstance(value, list) else [value])
    sid = session_id(payload)
    binding = {"toolName": tool_name, "targets": targets, "payload": tool_input}
    digest = sha256_text(canonical_json(binding))
    requires = effect in {"write", "unknown"}
    approvable = (requires and bool(sid) and bool(targets))
    status = "PREVIEW" if requires else ("READ_ONLY" if effect == "read" else "LOCAL")
    why = ""
    fix = ""
    if requires and not sid:
        why = "session provenance is missing"
        fix = "Retry through a host adapter that supplies session_id."
    elif requires and not targets:
        why = "exact external targets cannot be derived"
        fix = "Use explicit recipients/repository/resource IDs or an explicit remote URL/ref."
    return {
        "status": status,
        "effect": effect,
        "classificationReason": reason,
        "requiresApproval": requires,
        "approvable": approvable,
        "approvalHash": digest,
        "sessionId": sid,
        "toolName": tool_name,
        "targets": targets,
        "payload": tool_input,
        "attachments": attachments,
        "why": why,
        "fix": fix,
    }


def evaluate(payload: dict[str, Any], remember: bool = True) -> dict[str, Any]:
    preview = build_preview(payload)
    if not preview["requiresApproval"]:
        return {"allowed": True, "approved": False, "preview": preview}
    return {"allowed": False, "approved": False, "preview": preview}


def read_input(path: str) -> dict[str, Any]:
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        value = json.loads(text)
    except Exception as exc:
        raise GateError(f"cannot read exact tool request: {exc}",
                        "Pass a UTF-8 JSON hook payload via --input.") from exc
    if not isinstance(value, dict):
        raise GateError("tool request must be a JSON object", "Pass the complete hook payload.")
    return value


def fail(why: str, fix: str, preview: dict[str, Any] | None = None) -> int:
    value: dict[str, Any] = {"status": "FAIL", "why": why, "fix": fix}
    if preview is not None:
        value["preview"] = preview
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 1


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        return 0
    parser = argparse.ArgumentParser(description="Exact external-write approval gate")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "check"):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True)
    approve = sub.add_parser("approve")
    approve.add_argument("--hash", required=True)
    approve.add_argument("--session", required=True)
    approve.add_argument("--confirmed-by", required=True)
    args = parser.parse_args(args_list)
    try:
        if args.command == "approve":
            raise GateError(
                "caller-controlled approval is forbidden",
                "Approval is granted only by the host-native PreToolUse prompt for the "
                "exact pending invocation; no local ledger can mint it.",
            )
        request = read_input(args.input)
        result = evaluate(request, remember=True)
        preview_value = result["preview"]
        if args.command == "preview":
            print(json.dumps(preview_value, ensure_ascii=False, sort_keys=True))
            return 0 if (not preview_value["requiresApproval"]
                         or preview_value["approvable"]) else 1
        if result["allowed"]:
            return 0
        return fail(
            preview_value.get("why") or "external write has no exact session-bound approval",
            preview_value.get("fix") or
            "Show the exact preview, obtain user confirmation, approve its hash, and retry unchanged.",
            preview_value,
        )
    except GateError as exc:
        return fail(exc.why, exc.fix)
    except Exception as exc:
        return fail(
            f"unexpected external-write gate error: {exc}",
            "Do not perform the external action; inspect the exact request and retry.",
        )


if __name__ == "__main__":
    raise SystemExit(main())
