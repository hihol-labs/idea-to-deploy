#!/usr/bin/env python3
"""
SubagentStop hook — vendor-neutral verdict-contract validator (v1.51.0).

Release C, part (c). A review subagent (code-reviewer, or /review's fork) must
emit its verdict as a MACHINE-READABLE, VENDOR-NEUTRAL JSON block in the final
message — a fenced ```json … ``` object with {verdict, findings[]} — so that
downstream consumers (kickstart Quality Gate, tiering, the refute pass ledger)
read a stable contract instead of re-parsing prose. The native ReportFindings
tool-call is only an OPTIONAL transport; the load-bearing contract is the text
block, so it survives a vendor/version switch (harness best-effort invariant,
global CLAUDE.md).

Fires (blocks) only when ALL of these hold:
  * the subagent's final assistant message declares a REVIEW verdict in prose —
    one of `FINAL STATUS:`, `Вердикт:`/`Verdict:`, or the compound token
    `PASSED_WITH_WARNINGS` (deliberately NOT bare "PASSED"/"BLOCKED": a
    test-generator saying "all tests passed" must never trip this);
  * the message carries NO valid vendor-neutral JSON verdict block anywhere
    (a fenced ```json object — or an inline object — with a `verdict` field in
    {PASSED, PASSED_WITH_WARNINGS, BLOCKED, FAILED} and a `findings` list);
  * blocks for this subagent transcript so far < ITD_VERDICT_MAX_PINGS
    (default 2) — no infinite resume loop;
  * stop_hook_active is not set (harness-level loop guard).

Complementary to narration-final.sh on the same SubagentStop event, no loop:
narration-final blocks a narration-final that carries NO verdict; this hook
blocks a prose verdict that carries no JSON block. A message with verdict +
JSON block satisfies both and is never blocked; a bare narration-final trips
only narration-final. The two never fire on the same message toward opposite
edits.

Fail-open by design: missing/unreadable transcript, unparseable payload, no
text, any exception → exit 0 silently. Kill switch: ITD_VERDICT_CONTRACT=0.

Transcript resolution mirrors narration-final.sh (agent-direct sidechain file
or main-session fallback to the newest <session-stem>/subagents/agent-*.jsonl).

Reads JSON on stdin:
  {"session_id": "...", "transcript_path": "...", "stop_hook_active": bool}
Blocks by printing {"decision": "block", "reason": "..."} — per the hooks spec
for Stop-class events; the reason is delivered to the subagent, which continues
and appends the JSON block.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MAX_PINGS_DEFAULT = 2

# A REVIEW verdict declaration — narrow on purpose. Bare "PASSED"/"BLOCKED" are
# too common in non-review subagent finals ("all tests passed", "request was
# blocked by CORS"), so we require a declaration form or the compound token.
REVIEW_VERDICT_RE = re.compile(
    r"FINAL\s+STATUS\s*:|(?:Вердикт|Verdict)\s*[:：\-—]|"
    r"\b(?:PASSED_WITH_WARNINGS|UNVERIFIED)\b",
    re.IGNORECASE,
)

ALLOWED_VERDICTS = {
    "PASSED", "PASSED_WITH_WARNINGS", "BLOCKED", "UNVERIFIED", "FAILED",
}

# Fenced ```json … ``` blocks (the canonical transport).
FENCED_JSON_RE = re.compile(r"```json\s*(.+?)```", re.IGNORECASE | re.DOTALL)

REASON_HEAD = (
    "WHY: финальный review-вердикт не содержит обязательного машиночитаемого "
    "JSON-контракта.\nFIX: добавь fenced JSON с verdict, findings и unverified "
    "по схеме ниже.\n\n"
    "Твой финальный вердикт есть в прозе, но без вендор-нейтрального "
    "JSON-блока — контракт вердикта нарушен. Допиши в финальное сообщение "
    "фенсированный блок ```json … ``` с объектом: {\"verdict\": "
    "\"PASSED|PASSED_WITH_WARNINGS|BLOCKED\", \"findings\": [ {\"severity\": "
    "\"critical|important|minor\", \"confidence\": \"high|medium|low\", "
    "\"category\": \"<одно значение из перечня ниже>\", "
    "\"file\": \"путь\", \"line\": N, \"summary\": \"одна строка\"} ], "
    "\"unverified\": [\"…\"] }. Массив findings может быть пустым, но должен "
    "присутствовать. Это машиночитаемый контракт (нативный ReportFindings — "
    "лишь опциональный транспорт), не убирай его."
)
CATEGORY_HINT = (
    "\n\nПоле category ОБЯЗАТЕЛЬНО у каждой находки и берётся из закрытого "
    "перечня (PILOT P0-1): %s. Находка вне перечня не отбрасывается молча — "
    "она уходит в карантин леджера, поэтому выбери ближайшее значение."
)


def reason_text() -> str:
    """Перечень категорий берётся из ЖИВОГО файла словарей, а не из копии в
    тексте: расхождение подсказки и контракта невозможно по построению."""
    mod = load_taxonomy_module()
    tax = mod.load_taxonomy() if mod is not None else None
    if not tax:
        return REASON_HEAD
    return REASON_HEAD + CATEGORY_HINT % ", ".join(tax["category"]["values"])


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
    the caller treats that as «stay silent». Mirrors narration-final.sh.
    """
    tp = Path(transcript_path)
    if not tp.is_file():
        return "", ""
    any_txt, side_txt = scan_transcript(tp)
    if side_txt:
        return side_txt, str(tp)
    if tp.name.startswith("agent-") or tp.parent.name == "subagents":
        return any_txt, str(tp)
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


def _valid_verdict_object(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    v = obj.get("verdict")
    if not isinstance(v, str) or v.strip().upper() not in ALLOWED_VERDICTS:
        return False
    return isinstance(obj.get("findings"), list)


def _inline_verdict_objects(text: str):
    """Yield parsed JSON objects that mention "verdict", scanning brace-balanced
    substrings. Cheap fallback for an un-fenced block."""
    for m in re.finditer(r'"verdict"', text):
        # Walk back to the nearest '{' and forward brace-matching to '}'.
        start = text.rfind("{", 0, m.start())
        if start < 0:
            continue
        depth = 0
        for i in range(start, min(len(text), start + 20000)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    frag = text[start:i + 1]
                    try:
                        yield json.loads(frag)
                    except Exception:
                        pass
                    break


def extract_verdict_object(text: str):
    """First valid verdict object in the message, or None."""
    for m in FENCED_JSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(1).strip())
        except Exception:
            continue
        if _valid_verdict_object(obj):
            return obj
    for obj in _inline_verdict_objects(text):
        if _valid_verdict_object(obj):
            return obj
    return None


def has_valid_json_verdict(text: str) -> bool:
    return extract_verdict_object(text) is not None


# ---------------------------------------------------------------------------
# v1.86.0 — review-findings ledger (пункт 4 Harness Engineering: находки
# /review копятся машиночитаемо, /retro майнит повторяющиеся классы в
# кандидаты-автопроверки). Писатель — харнес (этот хук), не модель: он и так
# единственная точка, где валидный вердикт уже распарсен.
# ---------------------------------------------------------------------------

SOURCE_SUBAGENT = "subagent-verdict"


def _clip(s, n: int = 200) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def load_taxonomy_module():
    """Общий валидатор из skills/_shared. `hooks/` и `skills/` — сиблинги и в
    репо, и в установке (~/.claude), поэтому резолв один. Байткод рядом с
    модулем НЕ пишется: установленный runtime content-addressed, лишний
    __pycache__ — дрейф инвентаря (урок INSTALL-HARDENING, PR #247)."""
    mod_path = (Path(__file__).resolve().parent.parent
                / "skills" / "_shared" / "itd_verdict_taxonomy.py")
    env = os.environ.get("ITD_VERDICT_TAXONOMY_MODULE", "").strip()
    if env:
        mod_path = Path(env)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(
            "itd_verdict_taxonomy_hook", str(mod_path))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None
    finally:
        sys.dont_write_bytecode = prev


def _fallback_reject(cwd: str, rec: dict) -> None:
    """Модуль словарей не загрузился. Запись всё равно не теряется: карантин
    пишется здесь минимальным кодом. Дублируется ТОЛЬКО добавление строки —
    ни словарь, ни правила валидации тут не повторяются."""
    try:
        mem = Path(cwd) / ".itd-memory" if cwd else None
        if mem and mem.is_dir():
            path = mem / "review-findings-rejected.jsonl"
        else:
            path = (Path(tempfile.gettempdir())
                    / "claude-review-findings-rejected.jsonl")
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "reasons": ["taxonomy-unavailable"], "record": rec}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Отклонение считается и на аварийном пути: несчитанное отклонение —
        # это тот же молчаливый дроп, только с сохранённой копией.
        counter = path.with_name(
            path.name.replace("review-findings-rejected.jsonl",
                              "review-findings-rejected.count.jsonl"))
        with counter.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": entry["ts"],
                                 "reasons": entry["reasons"]},
                                ensure_ascii=False) + "\n")
    except Exception:
        pass


def _project_finding(f):
    """Клип известных полей БЕЗ отбрасывания остальных: карантин обязан
    показывать то, что ревьюер прислал, поэтому `line`, `confidence` и любые
    будущие поля доезжают до него, а не исчезают в проекции писателя."""
    if not isinstance(f, dict):
        return f
    out = dict(f)
    out["severity"] = _clip(f.get("severity"), 20)
    out["category"] = _clip(f.get("category"), 60) or None
    out["file"] = _clip(f.get("file"), 160)
    out["summary"] = _clip(f.get("summary"))
    return out


def persist_findings(cwd: str, key: str, obj: dict) -> None:
    """Append одного вердикта в леджер ЧЕРЕЗ закрытые словари (PILOT P0-1):
    невалидная запись не попадает в канонический леджер и не пропадает —
    уходит в карантин со счётчиком. Best-effort: никогда не raises и не влияет
    на block/silent-решение хука. Дедуп — content-sentinel в tmp (тот же финал
    может доехать до SubagentStop повторно через main-fallback)."""
    try:
        # Никакой фильтрации ДО валидации: выбросив здесь не-объект, писатель
        # превратил бы испорченный вердикт в «чистую» запись с пустым списком
        # находок. Всё, что пришло, доезжает до валидатора и либо принимается,
        # либо целиком уходит в карантин с названной причиной.
        findings = obj.get("findings")
        digest = hashlib.md5(
            (key + json.dumps(obj, sort_keys=True, ensure_ascii=False))
            .encode("utf-8", "replace")).hexdigest()[:12]
        sentinel = Path(tempfile.gettempdir()) / f"claude-review-persist-{digest}"
        if sentinel.exists():
            return
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "project": Path(cwd).name if cwd else "",
            "verdict": str(obj.get("verdict", "")).strip().upper(),
            "source": SOURCE_SUBAGENT,
            "lineage": _clip(key, 200),
            "findings": ([_project_finding(f) for f in findings]
                         if isinstance(findings, list) else findings),
        }
        mod = load_taxonomy_module()
        if mod is None:
            _fallback_reject(cwd, rec)
        else:
            mod.admit(cwd, rec)
        try:
            sentinel.write_text("1")
        except Exception:
            pass
    except Exception:
        pass  # леджер — побочный эффект: он не может уронить сессию


def take_ping_slot(key: str, max_pings: int) -> bool:
    """True if this transcript still has a block budget; bumps the counter."""
    digest = hashlib.md5(key.encode("utf-8", "replace")).hexdigest()[:12]
    sentinel = Path(tempfile.gettempdir()) / f"claude-verdict-contract-{digest}"
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
    if os.environ.get("ITD_VERDICT_CONTRACT", "1") == "0":
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("stop_hook_active"):
        return 0
    text, key = resolve_final_text(str(payload.get("transcript_path") or ""))
    if not text:
        return 0
    # Only review-verdict messages are in scope.
    if not REVIEW_VERDICT_RE.search(text):
        return 0
    # A valid JSON verdict block satisfies the contract — persist the findings
    # to the review-findings ledger (retro mining, v1.86.0) and stay silent.
    obj = extract_verdict_object(text)
    if obj is not None:
        cwd = str(payload.get("cwd") or "")
        persist_findings(cwd, key, obj)
        return 0
    if not take_ping_slot(key, env_int("ITD_VERDICT_MAX_PINGS", MAX_PINGS_DEFAULT)):
        return 0
    # M-C10 marker — declared hook event, do not remove (same convention as
    # narration-final.sh): {"hookEventName": "SubagentStop"}
    print(json.dumps({"decision": "block", "reason": reason_text()},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open: a detector must never break the session
