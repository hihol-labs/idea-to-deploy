#!/usr/bin/env python3
"""itd_verdict_taxonomy.py — закрытые словари схемы вердикта (PILOT P0-1).

Единственная реализация «принять или отклонить запись» для ОБОИХ писателей
review-findings ledger:
  * hooks/verdict-contract.sh        — вердикты субагентов;
  * skills/retro/scripts/itd_review_import.py — внешние GitHub-ревью.
Читатель (skills/retro/scripts/itd_retro_scan.py) берёт отсюда же legacyMapping
и счётчик отклонённых.

Инварианты (ADVISORY-RSI-2026-08-27-v4 §5 PILOT):
  * словари объявлены ровно в одном месте — VERDICT_TAXONOMY.json рядом;
  * валидация forward-only: записи БЕЗ taxonomyVersion не переписываются и не
    проверяются, они нормализуются только на чтении через legacyMapping;
  * отклонение != потеря: невалидная запись целиком уходит в карантин
    review-findings-rejected.jsonl с машиночитаемой причиной, счётчик причин
    ведётся в review-findings-rejected.count.json;
  * недоступный/битый файл словарей — это ПРИЧИНА taxonomy-unavailable, а не
    молчаливый пропуск и не тихая запись в канонический леджер.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TAXONOMY_FILE = "VERDICT_TAXONOMY.json"
FINDINGS_FILE = "review-findings.jsonl"
REJECTED_FILE = "review-findings-rejected.jsonl"
REJECTED_COUNT_FILE = "review-findings-rejected.count.jsonl"
FINDINGS_SOFT_BYTES = 64 * 1024  # bound как у errors.log: на переполнении — хвост
REASON_TAXONOMY_UNAVAILABLE = "taxonomy-unavailable"


def taxonomy_path() -> Path:
    """Путь к словарям. `hooks/` и `skills/` — сиблинги и в репо, и в установке
    (~/.claude), поэтому один относительный резолв работает в обоих случаях."""
    env = os.environ.get("ITD_VERDICT_TAXONOMY", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / TAXONOMY_FILE


def load_taxonomy(path: Path | None = None):
    """Словари или None. None означает «валидировать нечем» — вызывающий обязан
    отправить запись в карантин, а не принять её и не выбросить."""
    try:
        data = json.loads((path or taxonomy_path()).read_text(encoding="utf-8"))
        if not isinstance(data["taxonomyVersion"], int):
            return None
        for key in ("source", "severity", "category"):
            if not isinstance(data[key]["values"], list) or not data[key]["values"]:
                return None
        for key in ("source", "severity", "category"):
            for v in data[key]["values"]:
                if not isinstance(v, str) or not v.strip():
                    return None
        for key in ("severity", "category"):
            by = data[key]["bySource"]
            if not isinstance(by, dict) or not by:
                return None
            # Значения bySource обязаны лежать в объявленном словаре: иначе
            # семантически испорченный файл расширял бы «закрытый» перечень,
            # оставаясь синтаксически валидным. Исключение для не-ревьюеров
            # объявлено ДАННЫМИ (externalOnly), а не зашито в коде.
            permitted = set(data[key]["values"]) | set(
                data[key].get("externalOnly") or [])
            for allowed in by.values():
                if not isinstance(allowed, list) or not allowed:
                    return None
                if not set(allowed) <= permitted:
                    return None
        legacy = data["legacyMapping"]
        for key in ("category", "severity"):
            if not isinstance(legacy[key], dict):
                return None
        if not str(data["rejection"]["file"]).strip():
            return None
        return data
    except Exception:
        return None


def validate_record(rec, tax) -> list:
    """Причины отклонения (пустой список = запись валидна). Причина — короткая
    машиночитаемая строка `поле[индекс]:значение`, чтобы /retro считал классы
    промахов словаря без разбора прозы."""
    reasons = []
    if not isinstance(rec, dict):
        return ["record:not-an-object"]
    src = rec.get("source")
    sources = tax["source"]["values"]
    if not isinstance(src, str) or not src.strip() or src not in sources:
        reasons.append("source:%r" % (src,))
    # Провенанс объявлен как source+lineage (§7): пустой lineage делает запись
    # неотслеживаемой, поэтому он такая же часть схемы, как и source.
    lineage = rec.get("lineage")
    if not isinstance(lineage, str) or not lineage.strip():
        reasons.append("lineage:%r" % (lineage,))
    # Разрешённые значения берутся ТОЛЬКО из bySource: молчаливый откат к
    # глобальному списку означал бы, что битая или неполная таксономия
    # расширяет права источника (глобальный severity содержит unspecified).
    allowed_sev = tax["severity"].get("bySource", {}).get(src)
    categories = tax["category"].get("bySource", {}).get(src)
    if not allowed_sev or not categories:
        reasons.append("taxonomy:bySource-missing-for:%r" % (src,))
        allowed_sev, categories = [], []
    findings = rec.get("findings")
    if not isinstance(findings, list):
        return reasons + ["findings:not-a-list"]
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            reasons.append("finding[%d]:not-an-object" % i)
            continue
        sev = f.get("severity")
        cat = f.get("category")
        if sev not in allowed_sev:
            reasons.append("severity[%d]:%r" % (i, sev))
        if cat not in categories:
            reasons.append("category[%d]:%r" % (i, cat))
    return reasons


def ledger_dir(cwd: str) -> Path:
    """Проектный .itd-memory, иначе глобальный tmp-леджер (как SKILL_BYPASS)."""
    if cwd:
        mem = Path(cwd) / ".itd-memory"
        if mem.is_dir():
            return mem
    return Path(tempfile.gettempdir())


def _name(directory: Path, base: str) -> Path:
    """В tmp-фоллбэке имена префиксуются claude-, как у писателя v1.86."""
    if directory == Path(tempfile.gettempdir()):
        return directory / ("claude-" + base)
    return directory / base


def _dir(cwd: str, directory=None) -> Path:
    """Каталог леджера: явный (импортёр знает свой `--dir`) или выведенный из
    cwd (хук знает только проект)."""
    return Path(directory) if directory else ledger_dir(cwd)


def canonical_path(cwd: str, directory=None) -> Path:
    return _name(_dir(cwd, directory), FINDINGS_FILE)


def rejected_path(cwd: str, tax=None, directory=None) -> Path:
    base = REJECTED_FILE
    if tax:
        base = str(tax.get("rejection", {}).get("file") or REJECTED_FILE)
    return _name(_dir(cwd, directory), base)


def rejected_count_path(cwd: str, directory=None) -> Path:
    return _name(_dir(cwd, directory), REJECTED_COUNT_FILE)


def _append_bounded(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if path.stat().st_size > FINDINGS_SOFT_BYTES:
        tail = path.read_text(encoding="utf-8", errors="replace")[-FINDINGS_SOFT_BYTES // 2:]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(tail, encoding="utf-8")
        os.replace(tmp, path)


def bump_rejected_counter(cwd: str, reasons, directory=None) -> None:
    """Счётчик отклонённых переживает урезание карантина по размеру, поэтому он
    отдельный файл. Форма — append-only JSONL: у записи НЕТ фазы
    read-modify-write, поэтому два писателя (хук и импортёр) не могут ни
    затереть общий tmp, ни потерять обновление друг друга. Агрегат считает
    читатель (`rejected_summary`)."""
    p = rejected_count_path(cwd, directory)
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reasons": [str(r) for r in (reasons or ["unspecified"])],
    }, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def reject(cwd: str, rec, reasons, tax=None, directory=None) -> Path:
    """Запись не принята — но и не потеряна: целиком уходит в карантин."""
    path = rejected_path(cwd, tax, directory)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reasons": list(reasons),
        "record": rec,
    }
    # Осознанный размен: карантин НЕ урезается по размеру. Он и есть улика
    # промаха словаря; выбрасывая старую половину, он уничтожал бы ровно то,
    # ради чего заведён. Ограничение размера остаётся у канонического леджера.
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    bump_rejected_counter(cwd, reasons, directory)
    return path


def admit(cwd: str, rec, tax=None, directory=None) -> tuple:
    """Единственная точка записи. Возвращает (accepted: bool, reasons: list).

    Порядок намеренный: сначала словари, потом валидация, и только потом
    канонический леджер. Нет ветки, в которой запись исчезает."""
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None:
        reject(cwd, rec, [REASON_TAXONOMY_UNAVAILABLE], None, directory)
        return False, [REASON_TAXONOMY_UNAVAILABLE]
    try:
        rec = dict(rec or {})
        rec["taxonomyVersion"] = taxonomy["taxonomyVersion"]
        reasons = validate_record(rec, taxonomy)
    except Exception as exc:
        # Инвариант «запись не теряется» держится ОДНОЙ воронкой, а не
        # перечислением веток: любая неожиданная ошибка разбора или словаря
        # даёт названную причину и карантин, а не тихий дроп через общий
        # except писателя (r4: структурно битый, но парсящийся словарь).
        reasons = ["admit-error:%s" % type(exc).__name__]
        reject(cwd, rec, reasons, None, directory)
        return False, reasons
    if reasons:
        reject(cwd, rec, reasons, taxonomy, directory)
        return False, reasons
    try:
        _append_bounded(canonical_path(cwd, directory),
                        json.dumps(rec, ensure_ascii=False))
    except Exception as exc:
        reasons = ["admit-error:%s" % type(exc).__name__]
        reject(cwd, rec, reasons, None, directory)
        return False, reasons
    return True, []


def normalize_category(value, tax=None):
    """Чтение легаси: свободная строка -> значение enum или None. Леджер при
    этом НЕ переписывается."""
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None or value is None:
        return None
    value = str(value)
    if value in taxonomy["category"]["values"]:
        return value
    return taxonomy["legacyMapping"]["category"].get(value)


def normalize_severity(value, tax=None):
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None:
        return None
    value = "" if value is None else str(value)
    if value in taxonomy["severity"]["values"]:
        return value
    return taxonomy["legacyMapping"]["severity"].get(value)


def rejected_summary(cwd: str, directory=None) -> dict:
    """Счётчик для /retro: сколько записей словарь не принял и по каким классам.
    Агрегируется из append-only журнала, поэтому битая строка теряет одну
    запись, а не весь счёт."""
    p = rejected_count_path(cwd, directory)
    total = 0
    by_reason: dict = {}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        total += 1
        for r in (entry.get("reasons") or ["unspecified"]):
            key = str(r).split(":", 1)[0].split("[", 1)[0] or "unspecified"
            by_reason[key] = by_reason.get(key, 0) + 1
    if not total:
        return {}
    return {"total": total, "byReason": by_reason}
