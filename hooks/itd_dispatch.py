"""Claude Code dispatcher: one process per hook event runs the selected ITD hooks in memory (plan session 6, ADR-016).

Before plan session 6 the host started one Python process per registered hook (10 on a Bash call), and every process
compiled its script and the modules it loads again. scripts/sync-to-active.sh now registers hooks/claude-dispatch.py
(the entry point of this module) once per event and writes the selected hooks, their matchers, budgets and hard-gate
flags into claude-dispatch.json next to it. The dispatcher reads the payload once, picks the hooks whose matcher matches
the tool, runs each unchanged hook as `__main__` in its own thread with its own stdin, stdout and stderr, and merges
the answers like codex-dispatch.py does for Codex: the first blocking answer is passed through as the hook gave it,
asks are joined, context is concatenated.

Bytecode: the process writes no .pyc (the rule of 1.109.1; the entry point sets sys.dont_write_bytecode first).
sync-to-active.sh prepares checked-hash bytecode at install and lists it in itd-bytecode.json; this module, a hook
script and a module it imports are loaded from that bytecode only when the source hash recorded in it equals the
source on disk, otherwise they are compiled in memory.

Failure: a hook that crashes, exits with a code other than 0 or 2, or overruns its budget denies the call (blocks a
SubagentStop) when it is a hard gate (docs/HARNESS_TRUST_POLICY.json) and is dropped silently when it is advisory. An
unreadable table or payload, or a crash of the dispatcher itself, denies a tool call and blocks a SubagentStop, since
the hard gates of the event cannot be told apart then.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import io
import json
import marshal
import math
import os
import re
import sys
import threading
import time
import types
from pathlib import Path

TABLE_FILE = "claude-dispatch.json"
TABLE_KIND = "claude-dispatch-table-v1"
# A hard gate that overruns its host budget is a deny, so a slow host must not turn into a false deny: a hard gate
# gets at least this long. The registration timeout sync writes covers the longest budget of the event.
HARD_GATE_MIN_BUDGET_SECONDS = 30
SEQUENTIAL_WAIT_SECONDS = 0.25
# The registration covers the longest budget of its event plus the sequential waits and the process start.
REGISTRATION_MARGIN_SECONDS = 10
DISPATCHER_COMMAND = "~/.claude/hooks/claude-dispatch.py"
CONTEXT_EVENTS = frozenset({"UserPromptSubmit", "SessionStart"})
# The (script, event) pairs of the hard gates of docs/HARNESS_TRUST_POLICY.json (tests/verify_itd_dispatch.py keeps
# them equal): a table row of one of them is a hard gate whatever its hardGate flag says, so a damaged or edited
# table cannot turn a hard gate into a silent advisory hook.
HARD_GATES = frozenset({
    ("check-commit-completeness.sh", "PreToolUse"), ("check-dod-before-commit.sh", "PreToolUse"),
    ("check-predeploy-gate.sh", "PreToolUse"), ("check-review-before-commit.sh", "PreToolUse"),
    ("check-skill-completeness.sh", "PreToolUse"), ("check-tool-skill.sh", "PreToolUse"),
    ("completion-gate.sh", "PreToolUse"), ("cost-tracker.sh", "PreToolUse"), ("pii-egress-guard.sh", "PreToolUse"),
    ("state-guard.sh", "PreToolUse"), ("narration-final.sh", "SubagentStop"), ("verdict-contract.sh", "SubagentStop"),
})
CHECKED_HASH_PYC = 0b11
INVENTORY_FILE = "itd-bytecode.json"  # scripts/itd_hook_bytecode.py writes it into the install root
INVENTORY_KIND = "itd-hook-bytecode-v1"

_LOCAL = threading.local()


class _ThreadStream:
    """sys.stdin, sys.stdout or sys.stderr of the hook running in the calling thread, the real stream elsewhere."""

    def __init__(self, name: str, real: object) -> None:
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_real", real)

    def _target(self) -> object:
        return getattr(_LOCAL, self._name, None) or self._real

    def __getattr__(self, attribute: str) -> object:
        return getattr(self._target(), attribute)

    def __setattr__(self, attribute: str, value: object) -> None:
        setattr(self._target(), attribute, value)

    def __iter__(self):
        return iter(self._target())


class HookResult:
    def __init__(self, entry: dict, code: int | None, stdout: bytes, stderr: bytes, failure: str = "") -> None:
        self.entry, self.code, self.stdout, self.stderr, self.failure = entry, code, stdout, stderr, failure

    def json(self) -> dict | None:
        try:
            parsed = json.loads(self.stdout.decode("utf-8", "surrogateescape"))
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def blocking(self) -> bool:
        parsed = self.json() or {}
        specific = parsed.get("hookSpecificOutput") if isinstance(parsed.get("hookSpecificOutput"), dict) else {}
        return self.code == 2 or parsed.get("decision") == "block" or specific.get("permissionDecision") == "deny"


_GUARD: dict = {"root": None, "trusted": {}}


def _key(path: object) -> str:
    """One spelling of a path: links and Windows 8.3 short names resolved, case folded where the host folds it."""
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def trust_bytecode(root: Path) -> None:
    """Use only the bytecode the installer produced (review a2).

    A checked-hash header names its source, it does not prove the code object came from it. Under `root` (the
    install) a .pyc is used only when its SHA-256 equals its bytecodeSha256 in itd-bytecode.json; any other is
    refused and the source is compiled in memory instead. The guard covers every load of this process - the hook
    scripts (cached_code) and the modules they import or load by path (SourceFileLoader.get_data) - and leaves
    bytecode outside the install, such as the standard library's, alone.
    """
    trusted: dict[str, str] = {}
    try:
        inventory = json.loads((root / INVENTORY_FILE).read_text(encoding="utf-8"))
        if isinstance(inventory, dict) and inventory.get("kind") == INVENTORY_KIND:
            trusted = {_key(root / row["bytecode"]): str(row["bytecodeSha256"]) for row in inventory["files"]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        trusted = {}
    _GUARD.update(root=_key(root), trusted=trusted)
    loader = importlib.machinery.SourceFileLoader  # every source module load reads its .pyc through it
    if getattr(loader.get_data, "_itd_bytecode_guard", False):
        return
    original = loader.get_data

    def get_data(self, path):
        data = original(self, path)
        if str(path).endswith(".pyc") and under_install(path) and not bytecode_trusted(path, data):
            raise OSError(f"{path}: not the bytecode the install produced")  # the loader then compiles the source
        return data

    get_data._itd_bytecode_guard = True
    loader.get_data = get_data


def under_install(path: object) -> bool:
    return _GUARD["root"] is not None and _key(path).startswith(_GUARD["root"] + os.sep)


def bytecode_trusted(path: object, data: bytes) -> bool:
    """True for a .pyc of the install whose SHA-256 is the one the inventory records."""
    return under_install(path) and _GUARD["trusted"].get(_key(path)) == hashlib.sha256(data).hexdigest()


def cached_code(path: Path, source: bytes) -> types.CodeType | None:
    """The install-time bytecode of `path`: produced by the installer and checked-hash bytecode of this source."""
    try:
        pyc = Path(importlib.util.cache_from_source(str(path)))
        data = pyc.read_bytes()
    except (OSError, ValueError, NotImplementedError):
        return None
    if (not bytecode_trusted(pyc, data) or len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER
            or int.from_bytes(data[4:8], "little") != CHECKED_HASH_PYC
            or data[8:16] != importlib.util.source_hash(source)):
        return None
    try:
        code = marshal.loads(data[16:])
    except (EOFError, ValueError, TypeError):
        return None
    return code if isinstance(code, types.CodeType) else None


def load_code(path: Path) -> types.CodeType:
    source = path.read_bytes()
    return cached_code(path, source) or compile(source, str(path), "exec", dont_inherit=True)


def exit_status(exc: SystemExit) -> int:
    """The process exit status the interpreter would give this SystemExit (a message goes to stderr, status 1)."""
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    print(exc.code, file=sys.stderr)
    return 1


def run_hook(entry: dict, path: Path, payload: bytes, slot: list) -> None:
    """Run one hook script as `__main__` with the payload on its own stdin; the result goes into `slot`."""
    out, err = io.BytesIO(), io.BytesIO()
    _LOCAL.stdin = io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8", errors="surrogateescape")
    _LOCAL.stdout = io.TextIOWrapper(out, encoding="utf-8", errors="surrogateescape", write_through=True)
    _LOCAL.stderr = io.TextIOWrapper(err, encoding="utf-8", errors="backslashreplace", write_through=True)
    code = 0
    try:
        module = types.ModuleType("__main__")
        module.__file__ = str(path)
        exec(load_code(path), module.__dict__)
    except SystemExit as exc:
        code = exit_status(exc)
    except BaseException:  # noqa: BLE001 - reported as the interpreter would report an uncaught exception
        import traceback  # only on a crash: a cold import costs tens of ms on every call

        traceback.print_exc()
        code = 1
    finally:
        for name in ("stdout", "stderr"):
            try:
                getattr(_LOCAL, name).flush()
            except (OSError, ValueError):
                pass
    slot.append(HookResult(entry, code, out.getvalue(), err.getvalue()))


def matches(matcher: str, tool: str) -> bool:
    if matcher in ("", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return matcher == tool


def valid_entry(entry: object) -> bool:
    """A table row exactly as routing() writes it: string matcher and script, a positive timeout, a boolean flag."""
    if not isinstance(entry, dict) or set(entry) != {"matcher", "script", "timeout", "hardGate"}:
        return False
    timeout = entry["timeout"]
    return (isinstance(entry["matcher"], str) and isinstance(entry["script"], str) and bool(entry["script"])
            and isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
            and math.isfinite(timeout) and timeout > 0  # JSON admits Infinity and NaN; a thread join does not
            and isinstance(entry["hardGate"], bool))


def selected(table: dict, event: str, tool: str) -> list[dict]:
    hooks = table.get("hooks")
    if not isinstance(hooks, dict):
        raise ValueError("table hooks are not an object")
    entries = hooks.get(event, [])
    if not isinstance(entries, list):
        raise ValueError(f"table entries of {event} are not a list")
    chosen: dict[str, dict] = {}
    for entry in entries:
        if not valid_entry(entry):
            raise ValueError(f"table entry of {event} is malformed: {entry!r:.200}")
        if matches(entry["matcher"], tool):
            hard = entry["hardGate"] or (entry["script"], event) in HARD_GATES
            chosen.setdefault(entry["script"], dict(entry, hardGate=hard))  # the host runs an identical command once
    return list(chosen.values())


def budget(entry: dict) -> float:
    seconds = float(entry.get("timeout") or 5)
    return max(seconds, HARD_GATE_MIN_BUDGET_SECONDS) if entry.get("hardGate") else seconds


def routing(desired: dict, hard_gates: set[tuple[str, str]]) -> tuple[dict, dict]:
    """The routing table and the settings.json hooks of the selected `desired` hooks (scripts/sync-to-active.sh).

    `desired` has the shape of settings.json hooks (event -> groups of matcher and commands naming a hook file);
    `hard_gates` holds the (script, event) pairs of docs/HARNESS_TRUST_POLICY.json. Per event the table keeps every
    hook in order with its matcher, timeout and hard-gate flag; the registration is one dispatcher command under the
    union of the matchers with a timeout REGISTRATION_MARGIN_SECONDS above the longest budget of the event.
    """
    table: dict = {"version": 1, "kind": TABLE_KIND, "hooks": {}}
    registration: dict = {}
    for event, groups in desired.items():
        entries: list[dict] = []
        matchers: list[str] = []
        longest = 0.0
        for group in groups:
            matcher = group.get("matcher", "")
            for hook in group["hooks"]:
                script = hook["command"].replace("\\", "/").rsplit("/", 1)[-1]
                entry = {"matcher": matcher, "script": script, "timeout": hook.get("timeout", 5),
                         "hardGate": (script, event) in hard_gates}
                entries.append(entry)
                longest = max(longest, budget(entry))
            for alternative in (matcher.split("|") if matcher not in ("", "*") else ["*"]):
                if alternative not in matchers:
                    matchers.append(alternative)
        if not entries:
            continue
        table["hooks"][event] = entries
        group = {"hooks": [{"type": "command", "command": DISPATCHER_COMMAND,
                            "timeout": int(longest) + REGISTRATION_MARGIN_SECONDS}]}
        if any("matcher" in g for g in groups):
            group = {"matcher": "*" if "*" in matchers else "|".join(matchers), **group}
        registration[event] = [group]
    return table, registration


def run_all(entries: list[dict], hooks_dir: Path, payload: bytes) -> tuple[list[HookResult], bool]:
    """Run the hooks; return their results in table order and whether one is still running.

    Each hook runs in its own thread, one after another: hooks that share one interpreter contend for the GIL, so
    running the usual few-millisecond hooks in parallel is slower than in turn. A hook still running after
    SEQUENTIAL_WAIT_SECONDS keeps running while the next ones start, so the slowest hook (a commit gate running the
    project checks) bounds the wall time as it did when the host ran every hook in its own process.
    """
    started = []
    for entry in entries:
        path = (hooks_dir / entry["script"]).resolve()
        if path.parent != hooks_dir or not path.is_file():
            started.append((entry, None, [], 0.0))
            continue
        slot: list[HookResult] = []
        thread = threading.Thread(target=run_hook, args=(entry, path, payload, slot), daemon=True)
        thread.start()
        started.append((entry, thread, slot, time.monotonic() + budget(entry)))
        thread.join(min(SEQUENTIAL_WAIT_SECONDS, budget(entry)))
    results, abandoned = [], False
    for entry, thread, slot, deadline in started:
        if thread is None:
            results.append(HookResult(entry, None, b"", b"", "the hook file is missing"))
            continue
        thread.join(max(0.0, deadline - time.monotonic()))
        if thread.is_alive():
            abandoned = True
            results.append(HookResult(entry, None, b"", b"", f"the hook overran its {budget(entry):g} s budget"))
        elif slot[0].code not in (0, 2):
            results.append(HookResult(entry, slot[0].code, b"", slot[0].stderr,
                                      f"the hook exited {slot[0].code}"))
        else:
            results.append(slot[0])
    return results, abandoned


def failure_answer(event: str, reason: str, stop_hook_active: bool = False) -> tuple[bytes, bytes, int]:
    message = f"ITD high-risk hook transport failed closed: {reason}"
    if event == "SubagentStop":
        if stop_hook_active:  # the subagent already continues because of a stop hook: never block it in a loop
            return b"", message.encode("utf-8"), 0
        answer = {"decision": "block", "reason": message}
    elif event == "PreToolUse":
        answer = {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny",
                                         "permissionDecisionReason": message}}
    else:
        return b"", message.encode("utf-8"), 0
    return json.dumps(answer, ensure_ascii=False).encode("utf-8"), message.encode("utf-8"), 2


def merge(results: list[HookResult], event: str, stop_hook_active: bool) -> tuple[bytes, bytes, int]:
    for result in results:  # a blocking answer is passed through exactly as its hook gave it
        if not result.failure and result.blocking():
            return result.stdout, result.stderr, result.code or 0
    for result in results:
        if result.failure and result.entry.get("hardGate"):
            detail = result.stderr.decode("utf-8", "replace").strip()[-400:]
            reason = f"{result.entry['script']}: {result.failure}" + (f": {detail}" if detail else "")
            return failure_answer(event, reason, stop_hook_active)
    asks, contexts, messages, stop_reasons, stderr = [], [], [], [], []
    should_continue = True
    for result in results:
        if result.failure:  # an advisory hook that failed stays silent
            continue
        if result.stderr.strip():
            stderr.append(result.stderr.decode("utf-8", "replace").strip())
        if not result.stdout.strip():
            continue
        parsed = result.json()
        if parsed is None:  # plain text is context on a prompt event and transcript-only elsewhere
            text = result.stdout.decode("utf-8", "replace").strip()
            (contexts if event in CONTEXT_EVENTS else stderr).append(text)
            continue
        specific = parsed.get("hookSpecificOutput") if isinstance(parsed.get("hookSpecificOutput"), dict) else {}
        if specific.get("permissionDecision") == "ask":
            asks.append(str(specific.get("permissionDecisionReason") or ""))
        if specific.get("additionalContext"):
            contexts.append(str(specific["additionalContext"]))
        if parsed.get("systemMessage"):
            messages.append(str(parsed["systemMessage"]))
        if parsed.get("continue") is False:
            should_continue = False
        if parsed.get("stopReason"):
            stop_reasons.append(str(parsed["stopReason"]))
    merged: dict = {}
    specific: dict = {}
    if asks:
        specific.update(permissionDecision="ask",
                        permissionDecisionReason="\n".join(dict.fromkeys(reason for reason in asks if reason)))
    if contexts:
        specific["additionalContext"] = "\n".join(dict.fromkeys(contexts))
    if specific:
        merged["hookSpecificOutput"] = {"hookEventName": event, **specific}
    if messages:
        merged["systemMessage"] = "\n".join(dict.fromkeys(messages))
    if not should_continue:
        merged["continue"] = False
    if stop_reasons:
        merged["stopReason"] = "\n".join(dict.fromkeys(stop_reasons))
    stdout = json.dumps(merged, ensure_ascii=False).encode("utf-8") if merged else b""
    return stdout, "\n".join(dict.fromkeys(stderr)).encode("utf-8"), 0


def payload_event(payload: dict) -> str:
    event = payload.get("hook_event_name")
    if isinstance(event, str) and event:
        return event
    return "PostToolUse" if "tool_response" in payload else "PreToolUse" if "tool_name" in payload else ""


def dispatch(raw: bytes, hooks_dir: Path) -> tuple[tuple[bytes, bytes, int], bool]:
    try:
        payload = json.loads(raw.decode("utf-8", "surrogateescape")) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("the payload is not a JSON object")
    except ValueError as exc:
        return failure_answer("PreToolUse", f"invalid hook payload: {exc}"), False
    event = payload_event(payload)
    stop_hook_active = payload.get("stop_hook_active") is True
    try:
        table = json.loads((hooks_dir / TABLE_FILE).read_text(encoding="utf-8"))
        if not isinstance(table, dict) or table.get("kind") != TABLE_KIND:
            raise ValueError(f"not a {TABLE_KIND} table")
        entries = selected(table, event, str(payload.get("tool_name") or ""))
    except (OSError, ValueError) as exc:
        return failure_answer(event, f"{TABLE_FILE} is unusable ({exc}); FIX: re-run scripts/sync-to-active.sh",
                              stop_hook_active), False
    if not entries:
        return (b"", b"", 0), False
    results, abandoned = run_all(entries, hooks_dir, raw)
    return merge(results, event, stop_hook_active), abandoned


def silence_descriptors() -> tuple[list[tuple[int, int]], bool]:
    """Point fds 1 and 2 at the null device while the hooks run; return the saved copies and whether both moved.

    A child process a hook starts without capturing its output inherits the process descriptors: with one process
    per hook its noise stayed in that hook's own output, here it would land in the merged answer.
    """
    saved: list[tuple[int, int]] = []
    try:
        sink = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return saved, False
    try:
        for fd in (1, 2):
            try:
                saved.append((fd, os.dup(fd)))
                os.dup2(sink, fd)
            except OSError:
                return saved, False
    finally:
        os.close(sink)
    return saved, True


def restore_descriptors(saved: list[tuple[int, int]]) -> None:
    for fd, copy in saved:
        try:
            os.dup2(copy, fd)
            os.close(copy)
        except OSError:
            pass


def payload_flags(raw: bytes) -> tuple[str, bool]:
    """The event of a payload (PreToolUse when it cannot be told) and its stop_hook_active flag."""
    try:
        payload = json.loads(raw.decode("utf-8", "surrogateescape")) or {}
        return payload_event(payload), payload.get("stop_hook_active") is True
    except (ValueError, AttributeError):
        return "PreToolUse", False


def answer(raw: bytes, hooks_dir: Path) -> tuple[bytes, bytes, int]:
    """The dispatcher's answer to one payload; a crash of the dispatcher itself fails closed like a hard gate."""
    try:
        trust_bytecode(hooks_dir.parent)
        return dispatch(raw, hooks_dir)[0]
    except Exception as exc:  # noqa: BLE001 - the dispatcher itself failed: fail closed
        event, stop_hook_active = payload_flags(raw)
        return failure_answer(event, f"dispatcher crashed: {type(exc).__name__}: {exc}", stop_hook_active)


def respond(raw: bytes, hooks_dir: Path) -> tuple[bytes, bytes, int]:
    """answer() with the process descriptors isolated; when they cannot be, the event fails closed (review a2)."""
    saved, isolated = silence_descriptors()
    try:
        if not isolated:
            event, stop_hook_active = payload_flags(raw)
            return failure_answer(event, "the hook output descriptors cannot be isolated", stop_hook_active)
        return answer(raw, hooks_dir)
    finally:
        restore_descriptors(saved)


def main() -> int:
    real = {name: getattr(sys, name) for name in ("stdin", "stdout", "stderr")}
    raw = real["stdin"].buffer.read()
    for name, stream in real.items():
        setattr(sys, name, _ThreadStream(name, stream))
    stdout, stderr, code = respond(raw, Path(__file__).resolve().parent)
    real["stdout"].buffer.write(stdout)
    real["stdout"].flush()
    if stderr:
        real["stderr"].buffer.write(stderr if stderr.endswith(b"\n") else stderr + b"\n")
        real["stderr"].flush()
    # Leave without the interpreter shutdown: tearing down the hundred-odd modules the hooks loaded costs about 20 ms
    # per call, and a hook that overran its budget may still run in its thread. The answer is flushed above; the hooks
    # register no exit handlers (no atexit, finalizers, temporary directories or logging).
    os._exit(code)
