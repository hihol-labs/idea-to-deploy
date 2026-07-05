#!/usr/bin/env python3
"""
SubagentStop hook — mechanical narration-final detector (v1.49.0).

Problem (retro signal #1, evidence x5 in ONE v1.48.0 review run): a subagent —
most often the code-reviewer — ends its FINAL message on process narration
("Now check…", «Далее проверю…») instead of the deliverable. It kept happening
AFTER the named anti-pattern was written into the agent contract in v1.47.0,
so prompt-level contracts demonstrably do not fix this class. This hook is the
mechanical layer (same class as handoff-readiness.sh: computational detect,
minimal intervention) — it catches the narration-final at subagent stop and
blocks the stop, feeding the resume instruction back to the SUBAGENT so the
caller never has to ping «выдай итог одним сообщением» by hand.

Fires (blocks) only when ALL of these hold:
  * the subagent's final assistant message ends with a paragraph that STARTS
    with a narration opener (Now / Next / Let's / Let me / Далее / Теперь /
    Сейчас + a check/verify/test/run verb);
  * the message carries NO verdict/deliverable marker anywhere (PASSED /
    BLOCKED / FAILED / PASSED_WITH_WARNINGS / FINAL STATUS / Verdict /
    Вердикт / Итог) — a verdict-final message is NEVER blocked, including
    the valid «Не успел проверить: …» tail after a verdict;
  * the final paragraph is short (a dangling announcement, not content);
  * blocks for this subagent transcript so far < ITD_NARRATION_MAX_PINGS
    (default 2) — no infinite resume loop;
  * stop_hook_active is not set (harness-level loop guard).

Fail-open by design: missing/unreadable transcript, unparseable payload, no
text, any exception → exit 0 silently. Kill switch: ITD_NARRATION_FINAL=0.

Transcript resolution (harness variants observed 2026-07): when the payload's
transcript_path itself contains sidechain (isSidechain=true) assistant
entries — or is an agent-*.jsonl / subagents/ file — it IS the subagent
transcript. When it points at the MAIN session file instead, the subagent
transcript is the newest <transcript-dir>/<session-stem>/subagents/
agent-*.jsonl (the subagent that just stopped is the most recently written).

Note on the fallback: misidentifying the agent file under concurrent
subagents can only mis-judge narration-final for the CORRECT recipient — it
cannot route the resume reason to the wrong subagent, because the hook's
stdout is always delivered to the subagent whose stop triggered this
invocation. Worst case is one extra or one missed ping, never a cross-wired
reply.

Reads JSON on stdin:
  {"session_id": "...", "transcript_path": "...", "stop_hook_active": bool}
Blocks by printing {"decision": "block", "reason": "..."} — per the hooks
spec for Stop-class events; the reason is delivered to the subagent, which
continues and finishes properly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

MAX_PINGS_DEFAULT = 2
# Narration-finals are short dangling sentences; a long final paragraph is
# almost certainly content, not an announcement — stay silent on those.
MAX_FINAL_PARA_LEN = 400

# Opener at the very start of the final paragraph (or its LAST sentence) + a
# check/deliverable-verb within the next couple of words. Kept deliberately
# narrow: a false BLOCK costs a whole extra subagent turn, a false pass costs
# one manual ping.
# v1.53.0 (retro 2026-07-05, P3): added the "time to …" opener and the SINGLE
# evidenced verb refute (+ RU опроверг), and the match now also probes the LAST
# sentence of the final paragraph. Evidence: a reviewer ended on «Now I have
# full coverage. Time to refute my own findings before reporting.» — the
# narration sits in the last sentence, not the paragraph start, so start-only
# matching missed it. Deliberately NOT added: report/finalize/summarize/wrap —
# they double as user-facing instructions («Now report back to the team», «Now
# wrap up») and would false-block non-review subagents (review-flagged, pruned
# to the evidenced minimum; re-expand only on a second concrete incident).
NARRATION_RE = re.compile(
    r"^(?:now|next|let'?s|let\s+me|time\s+to|далее|теперь|сейчас)[,\s]+"
    r"(?:[\w-]+[\s,]+){0,2}?"
    r"(?:check|verify|test|re-?run|run|search|look|inspect|refute|"
    r"провер|перепровер|запус|посмотр|глян|поищ|протест|опроверг)",
    re.IGNORECASE,
)

# Any of these anywhere in the message = the deliverable/verdict was issued.
VERDICT_RE = re.compile(
    r"PASSED_WITH_WARNINGS|PASSED|BLOCKED|FAILED|FINAL\s+STATUS|"
    r"\bVerdict\b|\bВердикт\b|\bИтог\b|\bИтого\b",
    re.IGNORECASE,
)

REASON = (
    "Твоё финальное сообщение обрывается на анонсе процесса («Далее проверю…» / "
    "“Now check…”) — анти-паттерн нарратив-финала. Заверши работу СЕЙЧАС одним "
    "итоговым сообщением: либо выполни объявленную проверку и включи её результат, "
    "либо выпусти итог из того, что уже есть (для ревью — вердикт "
    "BLOCKED/PASSED_WITH_WARNINGS/PASSED + находки; всё непроверенное — явным "
    "списком «Не успел проверить»). Не заканчивай сообщение объявлением будущих "
    "действий."
)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def entry_text(entry: dict) -> str:
    """Concatenated text blocks of one transcript entry ('' if none)."""
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content
                 if isinstance(c, dict) and c.get("type") == "text"]
        return "\n".join(p for p in parts if p).strip()
    return ""


def scan_transcript(path: Path) -> tuple[str, str]:
    """Return (last_assistant_text, last_sidechain_assistant_text)."""
    last_any = last_side = ""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") != "assistant":
                continue
            txt = entry_text(e)
            if not txt:
                continue
            last_any = txt
            if e.get("isSidechain"):
                last_side = txt
    return last_any, last_side


def resolve_final_text(transcript_path: str) -> tuple[str, str]:
    """Final subagent text + a stable key for the ping sentinel.

    Returns ('', '') when the subagent transcript cannot be located —
    the caller treats that as «stay silent».
    """
    tp = Path(transcript_path)
    if not tp.is_file():
        return "", ""
    any_txt, side_txt = scan_transcript(tp)
    if side_txt:
        # The subagent's own transcript, or a main transcript with inline
        # sidechain entries — either way the last sidechain text is the one.
        return side_txt, str(tp)
    if tp.name.startswith("agent-") or tp.parent.name == "subagents":
        # Agent transcript that (in some harness build) lacks isSidechain.
        return any_txt, str(tp)
    # Main session transcript without sidechain entries → the subagent lives
    # in <dir>/<session-stem>/subagents/agent-*.jsonl; the newest one is the
    # subagent whose stop fired this hook.
    sub_dir = tp.with_suffix("") / "subagents"
    try:
        agents = sorted(sub_dir.glob("agent-*.jsonl"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        agents = []
    if agents:
        a_any, a_side = scan_transcript(agents[0])
        txt = a_side or a_any
        if txt:
            return txt, str(agents[0])
    return "", ""


def final_paragraph(text: str) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras[-1] if paras else ""


def take_ping_slot(key: str, max_pings: int) -> bool:
    """True if this transcript still has a block budget; bumps the counter."""
    digest = hashlib.md5(key.encode("utf-8", "replace")).hexdigest()[:12]
    sentinel = Path(tempfile.gettempdir()) / f"claude-narration-final-{digest}"
    try:
        count = int(sentinel.read_text().strip())
    except Exception:
        count = 0
    if count >= max_pings:
        return False
    try:
        sentinel.write_text(str(count + 1))
    except Exception:
        pass  # cannot persist the counter — still allow this single block
    return True


def main() -> int:
    if os.environ.get("ITD_NARRATION_FINAL", "1") == "0":
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return 0
    text, key = resolve_final_text(str(payload.get("transcript_path") or ""))
    if not text or VERDICT_RE.search(text):
        return 0
    para = final_paragraph(text)
    if not para or len(para) > MAX_FINAL_PARA_LEN:
        return 0
    # Strip markdown emphasis so «**Далее** проверю…» still matches.
    probe = re.sub(r"[*_`]+", " ", para).lstrip("#>–—•- \t").strip()
    # Probe the paragraph start AND its last sentence: narration often trails a
    # status sentence («Now I have coverage. Time to refute …»), which the
    # start-only match missed (v1.53.0 P3). The verdict-marker exemption above
    # is the real safety net — a review that issued its verdict is never here.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", probe) if s.strip()]
    last = sentences[-1] if sentences else ""
    if not (NARRATION_RE.match(probe) or NARRATION_RE.match(last)):
        return 0
    if not take_ping_slot(key, env_int("ITD_NARRATION_MAX_PINGS", MAX_PINGS_DEFAULT)):
        return 0
    # M-C10 marker — declared hook event, do not remove (same convention as
    # crash-recovery.sh): {"hookEventName": "SubagentStop"}
    print(json.dumps({"decision": "block", "reason": REASON}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: a detector must never break the session
