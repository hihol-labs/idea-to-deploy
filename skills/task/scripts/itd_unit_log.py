#!/usr/bin/env python3
"""itd_unit_log.py — harness-писатель unit-бухгалтерии /task Step 3.5 (v1.85.0).

Диагноз G-004 (retro 2026-07-11): Step 3.5 велел МОДЕЛИ вручную дописывать
JSON в STATE.json/events.jsonl — модель теряла activation-события (live:
4 юнита U-2..U-5 verified без activated → «Аномалия учёта» в retro-скане,
VCR слеп). Ремонт слоя: инструкция → инструмент. Переходами unit-статусов
/task управляет этот скрипт; пары activated/verified гарантированы fail-closed
проверкой, verified без evidence не бывает.

Использование (из корня проекта; --dir переопределяет .itd-memory):
  itd_unit_log.py activate U-9 --goal "однострочная формулировка" --risk-tier low
  itd_unit_log.py verified U-9 --evidence "вывод команды верификации"
  itd_unit_log.py backfill-activation U-2 --note "почему активация дописывается задним числом"

Семантика:
  activate  — WIP=1 (откажет, пока текущий unit in_progress/verifying),
              пишет STATE.currentUnit + событие activated (actor: harness).
              `--risk-tier` обязателен: тир определяет цену маршрута ревью
              (PROPORTIONALITY_POLICY), из имени юнита он не выводится, а
              ручная дописка в STATE теряется (S10, S11, LPD-002 R1-R3).
  verified  — требует существующего activated-события юнита (иначе exit 1 с
              подсказкой про осознанный backfill), обновляет STATE.currentUnit,
              пишет событие verified с обязательным evidence.
  backfill-activation — корректирующее событие activated с actor
              harness-reconciliation (для исторической реконсиляции; note
              обязателен — fail-closed, как skippedReason у /goal).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_MAX = 500

# Единица учёта живёт в общем модуле: и писатель, и retro-скан обязаны видеть
# ОДИН И ТОТ ЖЕ жизненный цикл (S10-LEDGER). Раскладка skills/_shared одинакова
# в репо методологии и в установленном ~/.claude/skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
import itd_unit_lifecycle as LC  # noqa: E402

# Терминалы, которыми можно закрыть цикл вручную при реконсиляции.
CLOSE_OUTCOMES = ("superseded", "abandoned", "blocked", "skipped")

# Закрытое множество риск-тиров. Первые три обязаны совпадать с ключами
# `riskRoutes` в `skills/_shared/PROPORTIONALITY_POLICY.json` (дрейф ловит
# `tests/verify_unit_log.py`); `unknown` — честное «не классифицировано»,
# которое политика верификации ведёт по строгому маршруту, а не по дешёвому.
RISK_TIERS = ("low", "medium", "high", "unknown")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LedgerAmbiguity(Exception):
    """Леджер события не выводится однозначно — писать нельзя (fail-closed)."""


def resolve_ledger(mem: Path, unit_id: str, explicit: str = "") -> str:
    """Леджер, которым будет проштампован event.

    Порядок: явный `--ledger` (проверенный по существующим) -> единственный
    владелец имени -> для неоднозначного имени единственный ОТКРЫТЫЙ цикл ->
    отказ. Молчаливый откат на `STATE` для неоднозначного имени был дефектом
    (ревьюер 2026-08-17, high/correctness): терминал авторизовался открытым
    циклом одного леджера и записывался в другой.
    """
    owners = [led["name"] for led in LC.load_ledgers(mem) if unit_id in led["unitIds"]]
    if explicit:
        # Явный леджер обязан ВЛАДЕТЬ юнитом: иначе вызывающий мог бы завести
        # цикл под чужим леджером и сам же его закрыть — проверка открытого
        # цикла подтвердила бы ту же подделку (ревьюер 2026-08-17,
        # high/correctness+security).
        if explicit == LC.STATE_LEDGER:
            if owners:
                raise LedgerAmbiguity(
                    f"{LC.STATE_LEDGER} допустим только для id без леджера-владельца; "
                    f"{unit_id} принадлежит: {', '.join(sorted(owners))}")
            return explicit
        if explicit not in owners:
            raise LedgerAmbiguity(
                f"леджер {explicit} не владеет юнитом {unit_id} (владельцы: "
                f"{', '.join(sorted(owners)) or 'нет — только ' + LC.STATE_LEDGER})")
        return explicit

    if not owners:
        return LC.STATE_LEDGER
    if len(owners) == 1:
        return owners[0]

    # Пересечение с ВЛАДЕЛЬЦАМИ обязательно: `attribute()` считает явное поле
    # `ledger` в строке авторитетным, поэтому подделанная или испорченная
    # append-only запись открывает цикл в леджере, который юнитом не владеет.
    # Без пересечения неявная резолюция выбрала бы именно его, и проверка
    # владения из явной ветки обходилась бы историей (ревьюер 2026-08-17, high).
    open_ledgers = {lc["ledger"] for lc in LC.open_lifecycles(mem, unit_id)}
    owned_open = open_ledgers & set(owners)
    if len(owned_open) == 1:
        return owned_open.pop()
    raise LedgerAmbiguity(
        f"id {unit_id} принадлежит нескольким леджерам ({', '.join(sorted(owners))}), "
        f"а открытых циклов в них {len(owned_open)}"
        + (f" (открытые циклы в невладеющих леджерах игнорируются: "
           f"{', '.join(sorted(open_ledgers - set(owners)))})"
           if open_ledgers - set(owners) else "")
        + " — укажи --ledger явно")


def state_describes(mem: Path, cur: dict, unit_id: str, ledger: str) -> bool:
    """Описывает ли STATE.currentUnit ИМЕННО ТОТ цикл, который сейчас закрывается.

    Совпадения по `id` мало: у коллизионного имени STATE может держать WIP в
    леджере A, пока закрывается легитимный цикл в леджере B — обновление по id
    пометило бы чужой WIP завершённым (ревьюер 2026-08-17, high/correctness).
    Пустой `ledger` в STATE — легаси-запись до этого юнита, она принимается.
    """
    if cur.get("id") != unit_id:
        return False
    recorded = cur.get("ledger")
    # Внешний вход проверяется по ТИПУ: `[]`, `{}`, `0`, `false` в поле `ledger`
    # — искажённая запись, а не легаси-пустая; трактовать её как «без леджера»
    # значило бы снова описать этой записью любой цикл имени (ревьюер
    # 2026-08-17, medium — тот же класс, что закрывался у метки времени и id
    # леджера). Fail-closed: искажённая запись не описывает ни один цикл.
    # Только отсутствие поля / `null` / пустая строка — легаси.
    if recorded is not None and not isinstance(recorded, str):
        return False
    if recorded:
        return recorded == ledger
    # Легаси-запись без `ledger` принимается ТОЛЬКО для однозначного имени:
    # у коллизионного она описывала бы любой цикл, и закрытие цикла в леджере B
    # снова помечало бы завершённым WIP из леджера A — та же дыра, что закрыта
    # выше, лишь уже (ревьюер 2026-08-17, high).
    owners = [led["name"] for led in LC.load_ledgers(mem) if unit_id in led["unitIds"]]
    return len(owners) <= 1


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}")
    return code


def append_event(mem: Path, unit_id: str, decision: str, evidence: str,
                 ledger: str, actor: str = "harness") -> None:
    evt = {
        "id": f"evt-unit-{int(time.time())}",
        "at": now_iso(),
        "actor": actor,
        "type": "unit",
        "name": unit_id,
        "decision": decision,
        "evidence": evidence[:EVIDENCE_MAX],
        # Без этого поля один id из разных леджеров неразличим в логе (live:
        # `G-001` принадлежит пяти разным юнитам). Леджер приходит УЖЕ
        # разрешённым, тем же значением, по которому проверялся открытый цикл.
        "ledger": ledger,
    }
    events = mem / "events.jsonl"
    with events.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")


def has_event(mem: Path, unit_id: str, decision: str) -> bool:
    events = mem / "events.jsonl"
    if not events.exists():
        return False
    for line in events.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "unit" and e.get("name") == unit_id and e.get("decision") == decision:
            return True
    return False


def load_state(mem: Path) -> dict:
    p = mem / "STATE.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_state(mem: Path, state: dict) -> None:
    """Атомарная запись (ACID-контракт v1.75.0: tmp + replace)."""
    p = mem / "STATE.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["activate", "verified", "close", "backfill-activation"])
    ap.add_argument("unit_id")
    ap.add_argument("--goal", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--ledger", default="",
                    help="явный леджер-владелец события; обязателен, когда id "
                         "принадлежит нескольким леджерам и открытый цикл не один")
    ap.add_argument("--risk-tier", choices=RISK_TIERS, default=None,
                    help="риск-тир юнита при activate: " + " | ".join(RISK_TIERS)
                         + " (обязателен: пропорциональность маршрута ревью "
                           "не выводится из имени юнита)")
    ap.add_argument("--outcome", default="superseded",
                    help="терминал для close: " + ", ".join(CLOSE_OUTCOMES))
    ap.add_argument("--dir", default=".itd-memory")
    a = ap.parse_args()

    if not a.unit_id or not a.unit_id.strip():
        return die("unit_id не может быть пустым или из одних пробелов: такое имя "
                   "бухгалтерия отбрасывает как непригодное", 1)
    a.unit_id = a.unit_id.strip()
    mem = Path(a.dir)
    if not mem.is_dir():
        return die(f"{mem} не существует — /task не создаёт .itd-memory (территория /adopt)")

    if a.command == "activate":
        state = load_state(mem)
        cur = state.get("currentUnit") or {}
        if cur.get("id") and cur.get("id") != a.unit_id and cur.get("status") in ("in_progress", "verifying", "recovery_required"):
            return die(f"WIP=1: текущий unit {cur['id']} в статусе {cur['status']} — сначала доведи его", 1)
        if not a.goal:
            return die("--goal обязателен при activate (однострочная формулировка задачи)", 1)
        # Отказ ДО события и до записи STATE: активация без тира оставляла бы
        # цикл открытым, а тир — на ручной дописке (её и теряли на S10/S11 и
        # на R1-R3 плана LPD-002). Пропорциональность обязана быть объявлена
        # тем же вызовом, который открывает цикл.
        if not a.risk_tier:
            return die("--risk-tier обязателен при activate ("
                       + " | ".join(RISK_TIERS)
                       + "): маршрут ревью пропорционален тиру, а тир не "
                         "выводится из имени юнита; неклассифицированный риск "
                         "объявляется явно как unknown и идёт по строгому маршруту", 1)
        try:
            ledger = resolve_ledger(mem, a.unit_id, a.ledger)
        except LedgerAmbiguity as exc:
            return die(str(exc), 1)
        # Событие первым — как в `verified`/`close`. Иначе падение append
        # оставило бы STATE с in_progress без открытого цикла в бухгалтерии:
        # WIP-гейт заблокировал бы всё, а закрывать было бы нечего
        # (ревьюер 2026-08-17). Обратный порядок безопаснее: лишний открытый
        # цикл виден бухгалтерии и закрывается штатной `close`.
        append_event(mem, a.unit_id, "activated", a.goal, ledger)
        state["currentUnit"] = {"id": a.unit_id, "goal": a.goal, "status": "in_progress",
                                "startedAt": now_iso(), "ledger": ledger,
                                "riskTier": a.risk_tier}
        save_state(mem, state)
        print(f"activated {a.unit_id}: {a.goal}")
        return 0

    if a.command == "verified":
        if not a.evidence:
            return die("--evidence обязателен: verified без evidence не бывает", 1)
        # Проверять надо ОТКРЫТЫЙ цикл, а не факт «когда-либо активировали»:
        # старая проверка пропускала verified, опирающийся на активацию,
        # закрытую месяцем раньше (live: второй verified у PE5-015 в августе
        # при активации из июля).
        try:
            ledger = resolve_ledger(mem, a.unit_id, a.ledger)
        except LedgerAmbiguity as exc:
            return die(str(exc), 1)
        # Проверять надо открытый цикл ИМЕННО В ТОМ леджере, которым будет
        # проштамповано событие: иначе терминал уедет в чужой леджер.
        if not LC.open_lifecycle_exists(mem, a.unit_id, ledger):
            hint = ("backfill-activation" if not has_event(mem, a.unit_id, "activated")
                    else "activate")
            return die(
                f"нет ОТКРЫТОГО жизненного цикла у {a.unit_id} в леджере {ledger} — "
                f"verified не пишется вне цикла (нужен `{hint} {a.unit_id}`)", 1)
        # Тот же порядок, что и в `close`: сначала событие, потом STATE.
        append_event(mem, a.unit_id, "verified", a.evidence, ledger)
        state = load_state(mem)
        cur = state.get("currentUnit") or {}
        if state_describes(mem, cur, a.unit_id, ledger):
            cur["status"] = "verified"
            cur["completedAt"] = now_iso()
            state["currentUnit"] = cur
            save_state(mem, state)
        print(f"verified {a.unit_id}")
        return 0

    if a.command == "close":
        # Терминал по реконсиляции: закрывает открытый цикл, который иначе
        # висит вечно и тихо тянет VCR вниз (live: GPG-001 активирован
        # 2026-07-29 и не имеет терминального события вообще).
        if not a.note.strip():
            return die("--note обязателен и не может быть из одних пробелов: "
                       "закрытие цикла без причины не бывает (fail-closed)", 1)
        a.note = a.note.strip()
        if a.outcome not in CLOSE_OUTCOMES:
            return die(f"--outcome должен быть одним из {', '.join(CLOSE_OUTCOMES)}", 1)
        try:
            ledger = resolve_ledger(mem, a.unit_id, a.ledger)
        except LedgerAmbiguity as exc:
            return die(str(exc), 1)
        if not LC.open_lifecycle_exists(mem, a.unit_id, ledger):
            return die(f"у {a.unit_id} нет открытого цикла в леджере {ledger} — "
                       f"закрывать нечего", 1)
        # Событие пишется ПЕРВЫМ: если append упадёт после сохранения STATE,
        # состояние объявит цикл завершённым, а бухгалтерия по-прежнему увидит
        # его открытым — реконсиляция стала бы неатомарной (ревьюер 2026-08-17).
        append_event(mem, a.unit_id, a.outcome, f"close: {a.note}", ledger,
                     actor="harness-reconciliation")
        state = load_state(mem)
        cur = state.get("currentUnit") or {}
        if state_describes(mem, cur, a.unit_id, ledger):
            cur["status"] = a.outcome
            cur["completedAt"] = now_iso()
            state["currentUnit"] = cur
            save_state(mem, state)
        print(f"closed {a.unit_id} as {a.outcome}")
        return 0

    # backfill-activation
    if not a.note.strip():
        return die("--note обязателен и не может быть из одних пробелов: "
                   "реконсиляция без причины не бывает (fail-closed)", 1)
    a.note = a.note.strip()
    try:
        ledger = resolve_ledger(mem, a.unit_id, a.ledger)
    except LedgerAmbiguity as exc:
        return die(str(exc), 1)
    # Проверка обязана быть привязана к леджеру: активация того же имени в
    # ДРУГОМ леджере не должна запрещать backfill в выбранном (ревьюер
    # 2026-08-17, medium/error-handling).
    if LC.has_activation(mem, a.unit_id, ledger):
        return die(f"activation-событие для {a.unit_id} в леджере {ledger} уже есть "
                   f"— backfill не нужен", 1)
    append_event(mem, a.unit_id, "activated", f"backfill: {a.note}", ledger,
                 actor="harness-reconciliation")
    print(f"backfilled activation {a.unit_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
