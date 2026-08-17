#!/usr/bin/env python3
"""itd_unit_lifecycle.py — единица учёта unit-бухгалтерии (S10-LEDGER, v1.98.0).

До этого модуля VCR считался по МНОЖЕСТВУ ИМЁН unit-событий
(`itd_retro_scan.py`, `scripts/itd_metrics.py` — семантика была продублирована).
Три следствия, измеренные на реальном `.itd-memory/events.jsonl`:

  1. Повторные активации и повторные верификации схлопывались в одно имя и
     становились невидимы (`PE5-015` — один `activated` и два `verified`).
  2. Один и тот же id принадлежит разным юнитам разных леджеров (`G-001` — пять
     штук), и бухгалтерия по имени математически не могла их различить.
  3. Юниты, закрытые ЛЕГИТИМНЫМ терминалом `blocked` (внешний блокер, решение
     человека), считались промахами верификации и держали проект ниже VCR 1
     с июля.

Единица учёта — ЖИЗНЕННЫЙ ЦИКЛ: от `activated` до первого терминального
решения, привязанный к леджеру-владельцу. Модуль — единственный источник
правды; потребители только форматируют его вывод.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# Терминалы жизненного цикла. `budget_exhausted` СЮДА НЕ ВХОДИТ: в реальном
# логе он всегда сопровождается последующим `budget_resumed` в том же цикле,
# то есть это пауза типизированного стопа, а не конец юнита (live: LE2/LE3,
# 2026-07-14). `regressed` — демотирование, тоже не конец.
TERMINALS = ("verified", "blocked", "skipped", "abandoned", "superseded")

# Не считаются промахом верификации: явные человеческие/внешние решения.
# `abandoned` СЧИТАЕТСЯ промахом — бросили, потому что не смогли; `superseded`
# не считается — работа уехала в другой юнит и там будет верифицирована.
EXCLUDED_FROM_DENOMINATOR = ("blocked", "skipped", "superseded")

# Псевдо-леджер для task-level юнитов (/task Step 3.5), которые ведутся через
# STATE.currentUnit и ни в одном GOAL-леджере не числятся.
STATE_LEDGER = "STATE"


def _parse_at(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # Нечитаемый лог (или каталог на этом пути) не должен ронять ОБОИХ
        # потребителей: заменённая реализация в itd_metrics.py это учитывала
        # (ревьюер 2026-08-17, error-handling).
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def load_ledgers(mem: Path) -> list[dict]:
    """Все GOAL*.json каталога памяти как окна атрибуции."""
    ledgers = []
    for path in sorted(mem.glob("GOAL*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("units"), list):
            continue
        # Тип id проверяется до построения МНОЖЕСТВА: `{"id": ["G-1"]}`
        # проходит фильтр правдивости и роняет обоих потребителей
        # `TypeError: unhashable type` (ревьюер 2026-08-17). Третий случай
        # этого класса — после манифеста (r7) и события (r8).
        unit_ids = {u["id"] for u in data["units"]
                    if isinstance(u, dict) and isinstance(u.get("id"), str)
                    and u["id"].strip()}
        if not unit_ids:
            continue
        ledgers.append({
            "name": path.name,
            "unitIds": unit_ids,
            "start": _parse_at(data.get("createdAt")),
            "end": _parse_at(data.get("updatedAt")),
        })
    return ledgers


def load_reconciliation(mem: Path) -> dict[tuple[str, str], str]:
    """Ручная реконсиляция исторических строк, чей леджер больше не существует
    в прежнем виде (переименованные/пересозданные юниты).

    Fail-closed: запись без непустого `why` игнорируется, и строка остаётся
    НЕатрибутированной — «объяснить» дороже, чем «замолчать», намеренно.
    """
    path = mem / "LEDGER-RECONCILIATION.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    # Синтаксически валидный, но не-объектный манифест (`[]`, `"x"`) не должен
    # ронять build() и вместе с ним обоих потребителей (ревьюер 2026-08-17).
    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    out: dict[tuple[str, str], str] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        unit, at, led, why = (row.get("unit"), row.get("at"),
                              row.get("ledger"), row.get("why"))
        # Типы полей проверяются ДО использования (unit, at) как ключа: запись
        # вида {"unit": []} с непустым why роняла бы весь разбор
        # `TypeError: unhashable type` (ревьюер 2026-08-17).
        if not all(isinstance(v, str) and v.strip() for v in (unit, at, led, why)):
            continue
        out[(unit, at)] = led
    return out


def attribute(event: dict, ledgers: list[dict],
              reconciliation: dict[tuple[str, str], str] | None = None) -> tuple[str | None, str]:
    """(ledger, reason). None означает НЕатрибутировано — это видимый счётчик,
    а не тихая догадка."""
    explicit = event.get("ledger")
    if isinstance(explicit, str) and explicit:
        return explicit, "explicit"

    name = event.get("name")
    raw_at = event.get("at")
    at = _parse_at(raw_at if isinstance(raw_at, str) else event.get("ts"))
    owners = [led for led in ledgers if name in led["unitIds"]]

    def reconciled() -> tuple[str | None, str]:
        """Ручная запись — ТОЛЬКО последнее средство.

        Манифест объясняет строки, которые машина честно не сводит; применять
        его раньше вывода значило бы разрешить переназначение однозначно
        атрибутируемого события в любой леджер, то есть превратить пояснение в
        переопределение (ревьюер 2026-08-17, high). `at` участвует в КЛЮЧЕ, его
        тип проверяется до обращения.
        """
        if reconciliation and isinstance(raw_at, str):
            manual = reconciliation.get((name, raw_at))
            if manual:
                return manual, "reconciled"
        return None, ""

    if not owners:
        # Отсутствие владельцев — это УМОЛЧАНИЕ (task-level юнит), а не вывод.
        # Манифест бьёт умолчание, но НЕ бьёт вывод: строка юнита, чей прежний
        # леджер больше не существует, попадает сюда, и вернуть ей `STATE`
        # раньше манифеста значило бы игнорировать точное задокументированное
        # объяснение (ревьюер 2026-08-17, high). Обратная сторона правки r12.
        led, why = reconciled()
        if led:
            return led, why
        return STATE_LEDGER, "state"

    if at is None:
        led, why = reconciled()
        return (led, why) if led else (None, "no-timestamp")

    if len(owners) == 1:
        # Единственный владелец имени — двусмысленности нет, окно не нужно.
        # `updatedAt` леджера это лишь последняя ЗАПИСЬ файла: события могут
        # законно быть позже (live: PE5-015 verified 2026-08-10 при
        # GOAL.json updatedAt 2026-07-27).
        return owners[0]["name"], "sole-owner"

    # Имя принадлежит нескольким леджерам (live: `G-001` — пяти) — окно
    # работает ТОЛЬКО как разрешение неоднозначности.
    fits = [led for led in owners
            if (led["start"] is None or at >= led["start"])
            and (led["end"] is None or at <= led["end"])]
    if len(fits) == 1:
        return fits[0]["name"], "window"
    led, why = reconciled()
    if led:
        return led, why
    return (None, "outside-all-windows") if not fits else (None, "ambiguous")


def build(mem: Path) -> dict:
    """Разбор unit-событий каталога памяти в жизненные циклы + сводка."""
    mem = Path(mem)
    ledgers = load_ledgers(mem)
    reconciliation = load_reconciliation(mem)
    events = [e for e in _read_jsonl(mem / "events.jsonl") if e.get("type") == "unit"]

    # Текущий WIP-юнит — ожидаемо открытый цикл, а не дрейф. Он тоже
    # ЛЕДЖЕРНО-ОБЛАСТНОЙ: STATE описывает не более одного цикла, поэтому
    # пометка по одному лишь id пометила бы WIP-ом все открытые циклы этого
    # имени во всех леджерах и вычла бы их из знаменателя (ревьюер 2026-08-17).
    wip_id = ""
    wip_ledger = ""
    state_path = mem / "STATE.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8", errors="replace"))
            cur = (state or {}).get("currentUnit") or {}
            if cur.get("status") in ("in_progress", "verifying", "recovery_required"):
                wip_id = cur.get("id") or ""
                wip_ledger = cur.get("ledger") or ""
        except Exception:
            wip_id = wip_ledger = ""

    rows = []
    unattributed = []
    for e in events:
        name = e.get("name")
        # `.strip()`: имя из одних пробелов так же непригодно, как пустое, и не
        # должно образовывать цикл (ревьюер 2026-08-17).
        if not isinstance(name, str) or not name.strip():
            # Безымянная строка не юнит: без имени она собирала бы цикл
            # (STATE, None) и попадала в числитель (ревьюер 2026-08-17, high).
            unattributed.append({"unit": None, "at": e.get("at"),
                                 "decision": e.get("decision"),
                                 "reason": "missing-unit-name"})
            continue
        led, reason = attribute(e, ledgers, reconciliation)
        if led is None:
            unattributed.append({"unit": e.get("name"), "at": e.get("at"),
                                 "decision": e.get("decision"), "reason": reason})
            continue
        rows.append((_parse_at(e.get("at") or e.get("ts")), led, e))

    # Дефект был в ПЕРЕУПОРЯДОЧИВАНИИ, а не в наличии таких строк: раньше
    # событие без пригодной метки сортировалось как `datetime.min`, и терминал
    # обгонял свою активацию (ревьюер 2026-08-17). Выбрасывать их — оверфикс,
    # который молча теряет события легаси-логов без `at`. Лог append-only, то
    # есть порядок в файле сам по себе хронологичен: строка без метки наследует
    # метку предыдущей и остаётся на своём месте благодаря устойчивой сортировке
    # по (метка, позиция).
    ordered = []
    last_seen = None
    for index, (at, led, e) in enumerate(rows):
        if at is None:
            at = last_seen
        else:
            last_seen = at
        ordered.append((at or datetime.min.replace(tzinfo=timezone.utc), index, led, e))
    ordered.sort(key=lambda r: (r[0], r[1]))
    rows = [(r[0], r[2], r[3]) for r in ordered]

    lifecycles: list[dict] = []
    open_lc: dict[tuple[str, str], dict] = {}
    verified_before: set[tuple[str, str]] = set()

    def new_lc(key, at, no_activation: bool) -> dict:
        lc = {"ledger": key[0], "unit": key[1], "startedAt": at,
              "endedAt": None, "outcome": "open", "reactivations": 0,
              "noActivation": no_activation,
              "reverification": no_activation and key in verified_before}
        if lc["reverification"]:
            lc["noActivation"] = False
        lifecycles.append(lc)
        return lc

    for at, led, e in rows:
        key = (led, e.get("name"))
        decision = e.get("decision")
        at_s = e.get("at") or e.get("ts") or ""

        if decision == "activated":
            lc = open_lc.get(key)
            if lc is not None:
                # Повторная активация без терминала между ними идемпотентна.
                lc["reactivations"] += 1
            else:
                open_lc[key] = new_lc(key, at_s, no_activation=False)
            continue

        if decision in TERMINALS:
            lc = open_lc.pop(key, None)
            if lc is None:
                lc = new_lc(key, at_s, no_activation=True)
            lc["outcome"] = decision
            lc["endedAt"] = at_s
            if decision == "verified" and not lc["noActivation"]:
                # Повторной верификацией считается только та, у которой БЫЛА
                # настоящая активация. Иначе пара `verified, verified` вовсе
                # без активации маскировала бы дефект писателя под безобидную
                # переверификацию (ревьюер 2026-08-17, high).
                verified_before.add(key)
            continue
        # Прочие решения (verification_failed, regressed, budget_exhausted,
        # budget_resumed, verification_sealed, checkpoint…) цикл не закрывают.

    candidates = [lc for lc in lifecycles
                  if lc["outcome"] == "open" and lc["unit"] == wip_id and wip_id]
    if wip_ledger:
        wip = [lc for lc in candidates if lc["ledger"] == wip_ledger]
    else:
        # Без записанного леджера пометка допустима только когда открытый цикл
        # этого имени ровно один — иначе STATE не различает их, и молча
        # исключать все было бы догадкой.
        wip = candidates if len(candidates) == 1 else []
    for lc in wip:
        lc["outcome"] = "wip"

    total = len(lifecycles)
    verified = sum(1 for lc in lifecycles if lc["outcome"] == "verified")
    blocked = sum(1 for lc in lifecycles if lc["outcome"] == "blocked")
    open_count = sum(1 for lc in lifecycles if lc["outcome"] == "open")
    excluded = sum(1 for lc in lifecycles if lc["outcome"] in EXCLUDED_FROM_DENOMINATOR)
    denominator = total - excluded - len(wip)

    return {
        "lifecycles": lifecycles,
        "lifecyclesTotal": total,
        "lifecyclesVerified": verified,
        "lifecyclesBlocked": blocked,
        "lifecyclesOpen": open_count,
        "lifecyclesWip": len(wip),
        "lifecyclesExcluded": excluded,
        # Аномалия писателя — это `verified` БЕЗ активации. Терминал
        # реконсиляции (blocked/superseded) без активации аномалией не является:
        # так закрываются циклы, чья активация предшествует самому логу.
        "lifecyclesNoActivation": sum(
            1 for lc in lifecycles if lc["noActivation"] and lc["outcome"] == "verified"),
        "lifecyclesReconciledTerminal": sum(
            1 for lc in lifecycles if lc["noActivation"] and lc["outcome"] != "verified"),
        "lifecyclesReverified": sum(1 for lc in lifecycles if lc["reverification"]),
        "unattributedEvents": len(unattributed),
        "unattributedSample": unattributed[:20],
        "vcr": round(verified / denominator, 3) if denominator else None,
    }


def has_activation(mem: Path, unit_id: str, ledger: str) -> bool:
    """Есть ли У ЭТОГО ЮНИТА В ЭТОМ ЛЕДЖЕРЕ хоть одно событие `activated`."""
    return any(lc["ledger"] == ledger and lc["unit"] == unit_id
               and not lc["noActivation"]
               for lc in build(Path(mem))["lifecycles"])


def open_lifecycles(mem: Path, unit_id: str) -> list[dict]:
    """Открытые (или WIP) циклы этого юнита — по одному на леджер-владелец.

    Возвращается СПИСОК, а не флаг: один и тот же id живёт в разных леджерах
    (live: `G-001` — пять юнитов), и писатель обязан знать, В КАКОМ именно
    леджере цикл открыт. Ревьюер 2026-08-17 (high/correctness) показал, что
    флаг «есть где-то открытый цикл» позволяет авторизовать терминал циклом
    одного леджера и записать его в другой — исходный цикл остаётся открытым
    навсегда, а в чужом леджере появляется терминал без активации.
    """
    return [lc for lc in build(Path(mem))["lifecycles"]
            if lc["unit"] == unit_id and lc["outcome"] in ("open", "wip")]


def open_lifecycle_exists(mem: Path, unit_id: str, ledger: str | None = None) -> bool:
    """Открыт ли цикл этого юнита; при указанном `ledger` — именно в нём.

    Заменяет проверку «активировали ли это имя КОГДА-ЛИБО»: та пропускала
    `verified`, опирающийся на активацию, закрытую месяцем раньше (live:
    второй `verified` у PE5-015 в августе при активации из июля).
    """
    return any(ledger is None or lc["ledger"] == ledger
               for lc in open_lifecycles(mem, unit_id))
