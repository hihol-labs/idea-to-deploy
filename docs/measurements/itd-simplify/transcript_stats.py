#!/usr/bin/env python3
"""Real-harness numbers from Claude Code transcripts for the ITD simplification baseline (ADR-016).

Reads the main session transcripts (<dir>/*.jsonl, subagent transcripts excluded) modified since --since and prints
one JSON object:

- hooks: for Bash, Edit and Read calls, the host's own `durationMs` of every recorded hook (the host records a hook
  that produced output; silent hooks leave no entry, so the per-call maximum is a LOWER bound of the phase wall
  time - hooks of one phase run in parallel), as median per phase and per command;
- context: bytes of hook text the host injected into the model context (its `hook_additional_context` records; the
  same text inside hook stdout is not counted twice) per user prompt (UserPromptSubmit) and per session;
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
from datetime import datetime, timezone
from pathlib import Path

TOOLS = ("Bash", "Edit", "Read")


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def median(values):
    return round(statistics.median(values)) if values else None


def injected(attachment: dict) -> int:
    """Bytes of hook text the host added to the model context (its `hook_additional_context` record)."""
    content = attachment.get("content")
    items = content if isinstance(content, list) else [content]
    return sum(len(item.encode("utf-8")) for item in items if isinstance(item, str))


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
    per_prompt: list[int] = []
    session_bytes = collections.Counter()
    skill_starts: list[datetime] = []
    timeline: list[tuple[datetime, str]] = []
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            record = json.loads(line)
        except ValueError:
            continue
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
        elif real_prompt(record) and when:
            timeline.append((when, "prompt"))
        attachment = record.get("attachment")
        if not isinstance(attachment, dict) or not str(attachment.get("type", "")).startswith("hook_"):
            continue
        event = attachment.get("hookEvent")
        if attachment.get("type") == "hook_additional_context":
            size = injected(attachment)
            session_bytes[event] += size
            if event == "UserPromptSubmit":
                per_prompt.append(size)
            continue
        if event in ("PreToolUse", "PostToolUse") and isinstance(attachment.get("durationMs"), (int, float)):
            phases[(attachment.get("toolUseID"), event)].append(attachment)
    for (tool_id, event), hooks in phases.items():
        tool = names.get(tool_id)
        if tool not in TOOLS:
            continue
        acc["phaseLowerBound"][(tool, event)].append(max(h["durationMs"] for h in hooks))
        for hook in hooks:
            command = str(hook.get("command", "")).strip('"').replace("\\", "/")
            acc["perCommand"][(tool, event, command.split("/")[-1].strip('"'))].append(hook["durationMs"])
    if per_prompt or session_bytes:
        acc["sessions"] += 1
        acc["sessionBytes"].append(sum(session_bytes.values()))
        acc["sessionByEvent"].append(dict(session_bytes))
    acc["promptBytes"].extend(per_prompt)
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
           "sessionByEvent": [], "sessionSave": []}
    for directory in args.dirs:
        for path in sorted(directory.expanduser().glob("*.jsonl")):
            if path.stat().st_mtime >= since:
                acc["files"] += 1
                scan(path, acc)
    by_event = collections.defaultdict(list)
    for row in acc["sessionByEvent"]:
        for event, size in row.items():
            by_event[event].append(size)
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
        "sessionSave": {"runs": len(acc["sessionSave"]), "secondsMedian": median(acc["sessionSave"]),
                        "secondsMin": min(acc["sessionSave"], default=None),
                        "secondsMax": max(acc["sessionSave"], default=None)},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
