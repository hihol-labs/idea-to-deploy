#!/usr/bin/env python3
"""Real-harness numbers from Claude Code transcripts for the ITD simplification baseline (ADR-016).

Reads the main session transcripts (<dir>/*.jsonl, subagent transcripts excluded) modified since --since and prints
one JSON object:

- hooks: for Bash, Edit and Read calls, the host's own `durationMs` of every recorded hook (not every hook leaves a
  record - observed: the ones with output - so the per-call maximum is a LOWER bound of the phase wall time; hooks of
  one phase run in parallel), as median per phase and per command;
- context: bytes of hook text the host injected into the model context (its `hook_additional_context` records; the
  same text inside hook stdout is not counted twice) per UserPromptSubmit event and per session. One event is the
  user input it follows (a prompt or a notification): every UserPromptSubmit record whose parent chain of attachment
  records leads to the same non-attachment record is summed into it (the host writes one record with one string per
  hook, but the grouping does not rely on that); every prompt of a person is an event, with 0 bytes when no hook
  added text to it (task notifications, interrupts and local-command records count only when a hook added text),
  and every scanned main transcript is a session, also one without injected text;
- meta: counts of the `permissionMode` field, of assistant `message.model` and of the host `version` over all
  records, and the version in the last record of the most recently modified transcript;
- sessionSave: wall time of each `/session-save` run, from the assistant message that invoked the Skill to the
  last assistant message before the next real user prompt.

Usage:
  python3 transcript_stats.py ~/.claude/projects/-home-hihol-projects-idea-to-deploy --since 2026-10-07
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# The per-command name is the one the bench prints (the script token, not the last path segment of the whole
# command line); `-I` drops the script directory from sys.path, so it is added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_bench import command_label  # noqa: E402

TOOLS = ("Bash", "Edit", "Read")
CONTEXT_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse")


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def median(values):
    return round(statistics.median(values)) if values else None


def injected(attachment: dict) -> int:
    """Bytes of hook text the host added to the model context (its `hook_additional_context` record)."""
    content = attachment.get("content")
    items = content if isinstance(content, list) else [content]
    return sum(len(item.encode("utf-8")) for item in items if isinstance(item, str))


def anchor(parents: dict, uuid: str | None) -> str | None:
    """The nearest ancestor that is not an attachment record (the user input a hook event belongs to)."""
    seen = set()
    while uuid in parents and uuid not in seen:
        seen.add(uuid)
        is_attachment, parent = parents[uuid]
        if not is_attachment:
            return uuid
        uuid = parent
    return uuid


# User records with text that the host or the harness generates, not a person: they end a session-save run but
# are not 0-byte prompt events of their own (a UserPromptSubmit record on one still counts with its bytes).
MACHINE_PREFIXES = ("<task-notification>", "[Request interrupted", "<local-command", "<system-reminder>", "Caveat:")


def text_of(record: dict) -> str:
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def human_prompt(record: dict) -> bool:
    return real_prompt(record) and not text_of(record).lstrip().startswith(MACHINE_PREFIXES)


def real_prompt(record: dict) -> bool:
    if record.get("type") != "user" or record.get("isMeta") or record.get("isSidechain"):
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.startswith("<command-") or "<command-name>" in content
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in content)


def scan(path: Path, acc: dict) -> None:
    names: dict[str, str] = {}
    phases: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    per_prompt: collections.Counter = collections.Counter()
    parents: dict[str, tuple[bool, str | None]] = {}  # uuid -> (is an attachment record, parentUuid)
    session_bytes = collections.Counter()
    skill_starts: list[datetime] = []
    timeline: list[tuple[datetime, str]] = []
    latest = None
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record.get("uuid"), str):
            parents[record["uuid"]] = ("attachment" in record, record.get("parentUuid"))
        if isinstance(record.get("permissionMode"), str):
            acc["permissionModes"][record["permissionMode"]] += 1
        if isinstance(record.get("version"), str):
            acc["versions"][record["version"]] += 1
            latest = record["version"]
        if record.get("type") == "assistant" and isinstance((record.get("message") or {}).get("model"), str):
            acc["models"][record["message"]["model"]] += 1
        stamp = record.get("timestamp")
        when = ts(stamp) if isinstance(stamp, str) else None
        if record.get("type") == "assistant" and when:
            timeline.append((when, "assistant"))
            for block in (record.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    names[block.get("id")] = block.get("name")
                    skill = (block.get("input") or {}).get("skill", "") if block.get("name") == "Skill" else ""
                    if skill.split(":")[-1] == "session-save":
                        skill_starts.append(when)
        elif real_prompt(record):
            if when:
                timeline.append((when, "prompt"))
            if isinstance(record.get("uuid"), str) and human_prompt(record):
                per_prompt[record["uuid"]] += 0  # a prompt no hook added text to is a 0-byte event, not a gap
        attachment = record.get("attachment")
        if not isinstance(attachment, dict) or not str(attachment.get("type", "")).startswith("hook_"):
            continue
        event = attachment.get("hookEvent")
        if attachment.get("type") == "hook_additional_context":
            size = injected(attachment)
            session_bytes[event] += size
            if event == "UserPromptSubmit":
                per_prompt[anchor(parents, record.get("parentUuid")) or record.get("uuid")] += size
            continue
        if event in ("PreToolUse", "PostToolUse") and isinstance(attachment.get("durationMs"), (int, float)):
            phases[(attachment.get("toolUseID"), event)].append(attachment)
    for (tool_id, event), hooks in phases.items():
        tool = names.get(tool_id)
        if tool not in TOOLS:
            continue
        acc["phaseLowerBound"][(tool, event)].append(max(h["durationMs"] for h in hooks))
        for hook in hooks:
            acc["perCommand"][(tool, event, command_label(str(hook.get("command", ""))))].append(hook["durationMs"])
    if latest is not None:
        acc["latestVersions"].append((path.stat().st_mtime, latest))
    # every scanned main transcript is a session, also one into which no hook injected anything
    acc["sessions"] += 1
    acc["sessionBytes"].append(sum(session_bytes.values()))
    acc["sessionByEvent"].append(dict(session_bytes))
    acc["promptBytes"].extend(per_prompt.values())
    timeline.sort()
    for start in skill_starts:
        end = start
        for when, kind in timeline:
            if when <= start:
                continue
            if kind == "prompt":
                break
            end = when
        acc["sessionSave"].append(round((end - start).total_seconds()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--since", required=True, help="YYYY-MM-DD (file mtime, UTC)")
    args = ap.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    acc = {"files": 0, "sessions": 0, "phaseLowerBound": collections.defaultdict(list),
           "perCommand": collections.defaultdict(list), "promptBytes": [], "sessionBytes": [],
           "sessionByEvent": [], "sessionSave": [], "permissionModes": collections.Counter(),
           "models": collections.Counter(), "versions": collections.Counter(), "latestVersions": []}
    for directory in args.dirs:
        for path in sorted(directory.expanduser().glob("*.jsonl")):
            if path.stat().st_mtime >= since:
                acc["files"] += 1
                scan(path, acc)
    # Every session counts for every event, with 0 when the event injected nothing there: the median is over
    # sessions, not over the sessions where the event happened to inject.
    events = sorted({event for row in acc["sessionByEvent"] for event in row} | set(CONTEXT_EVENTS))
    by_event = {event: [row.get(event, 0) for row in acc["sessionByEvent"]] for event in events}
    print(json.dumps({
        "dirs": [str(d) for d in args.dirs], "since": args.since, "files": acc["files"], "sessions": acc["sessions"],
        "hooks": {f"{tool}:{event}": {"calls": len(v), "lowerBoundWallMsMedian": median(v)}
                  for (tool, event), v in sorted(acc["phaseLowerBound"].items())},
        "perCommandMedianMs": {f"{tool}:{event}:{name}": {"n": len(v), "median": median(v)}
                               for (tool, event, name), v in sorted(acc["perCommand"].items())},
        "context": {"prompts": len(acc["promptBytes"]), "perPromptBytesMedian": median(acc["promptBytes"]),
                    "perPromptBytesMax": max(acc["promptBytes"], default=None),
                    "perSessionBytesMedian": median(acc["sessionBytes"]),
                    "perSessionBytesByEventMedian": {e: median(v) for e, v in sorted(by_event.items())}},
        "meta": {"permissionModes": dict(acc["permissionModes"].most_common()),
                 "models": dict(acc["models"].most_common()), "versions": dict(acc["versions"].most_common()),
                 "newestTranscriptVersion": max(acc["latestVersions"])[1] if acc["latestVersions"] else None},
        "sessionSave": {"runs": len(acc["sessionSave"]), "secondsMedian": median(acc["sessionSave"]),
                        "secondsMin": min(acc["sessionSave"], default=None),
                        "secondsMax": max(acc["sessionSave"], default=None)},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
