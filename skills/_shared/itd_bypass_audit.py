#!/usr/bin/env python3
"""Перенос строк аудита обхода из рабочего леджера в канонический журнал.

Почему это отдельный шаг, а не дозапись на месте. Коммит-гейт исполняется
ВНУТРИ `git commit`: строка, записанная в отслеживаемый `.itd-memory/events.jsonl`,
делает рабочее дерево отличным от прореверенного кандидата, и гейт точного
дерева отказывает ровно тому коммиту, ради которого обход и был выдан. Поэтому
строки копятся в неотслеживаемом append-only леджере
`.itd-memory/completion-bypass.jsonl`, а в журнал их переносит ledger-close -
момент, когда дерево и так меняется бухгалтерски.

Перенос идемпотентен: строка с уже присутствующим в журнале `id` не дублируется,
поэтому повторный прогон на том же состоянии ничего не меняет.

Использование:
  itd_bypass_audit.py carry [--root .] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

LEDGER = "completion-bypass.jsonl"
JOURNAL = "events.jsonl"


def safe_atomic():
    """Общий якорный примитив: и чтение, и запись идут через него."""
    spec = pathlib.Path(__file__).with_name("itd_safe_atomic.py")
    if str(spec.parent) not in sys.path:
        sys.path.insert(0, str(spec.parent))
    import itd_safe_atomic as module  # noqa: E402
    return module


def rows(root: pathlib.Path, relative: pathlib.Path) -> list[dict]:
    """Прочитать леджер ЯКОРНО, без следования по симлинкам.

    Писатель был якорным, а читатель - нет: подложенная по пути леджера ссылка
    втягивала чужой JSON прямо в канонический журнал в обход всей защиты записи
    (находка независимого ревьюера). Асимметрия закрыта - обе стороны ходят
    через один примитив.
    """
    raw = safe_atomic().read_ledger_snapshot(root / relative)
    if raw is None:
        return []
    out = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except ValueError:
            # Битая строка не пропускается молча: аудит обхода - улика.
            raise SystemExit(f"FAIL {relative}: unparsable audit row: {line[:120]}")
        if not isinstance(value, dict) or not str(value.get("id") or "").strip():
            raise SystemExit(f"FAIL {relative}: audit row without an id: {line[:120]}")
        out.append(value)
    return out


def canonical_form(row: dict) -> str:
    """Каноническая форма строки: сравнение по содержимому, не по порядку."""
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def carry(root: pathlib.Path, dry_run: bool) -> int:
    """Перенести непереносённые строки в журнал. Леджер НЕ удаляется.

    Удаление и было источником потери: между снимком и очисткой гейт может
    дописать новую строку обхода, а писатель, державший дескриптор, допишет её
    даже в уже отвязанный inode (две находки независимого ревьюера). Ни
    ротация, ни наблюдение за размером этого не закрывают - доказать, что
    писатель больше не допишет, нельзя. Поэтому опасная операция убрана
    целиком: перенос только ЧИТАЕТ леджер и дописывает журнал, а уже
    перенесённые строки отсеиваются по `id`. Строку физически нечему потерять.

    Цена - леджер растёт. Она мала: строка появляется только при осознанном
    обходе, файл не отслеживается, а повторный перенос его не дублирует.
    """
    memory = pathlib.Path(".itd-memory")
    # Хвост от прежней версии переноса, если он остался на диске, читается
    # наравне с леджером: иначе его строки остались бы в стороне навсегда.
    pending = (rows(root, memory / (LEDGER + ".carrying"))
               + rows(root, memory / LEDGER))
    if not pending:
        print(json.dumps({"carried": 0, "status": "EMPTY"}, sort_keys=True))
        return 0
    # Журнал сравнивается по СОДЕРЖИМОМУ, а не только по `id`: тот же
    # идентификатор с другим содержимым - не «уже перенесено», а конфликт
    # (находка независимого ревьюера). Считать такую строку перенесённой
    # значило бы тихо потерять улику, ради которой леджер и существует.
    # Карта строится ПОШАГОВО, а не включением: включение молча схлопывает
    # дубль внутри самого журнала, и если у копий разное содержимое, выживает
    # последняя. Тогда строка, совпавшая с ней, считалась бы благополучно
    # перенесённой, а конфликт в журнале оставался бы невидимым (находка
    # независимого ревьюера). Конфликт в журнале - такой же отказ, как и в
    # партии: чинить его должен человек, а не тихо выбирать копию.
    known: dict[str, str] = {}
    for row in rows(root, memory / JOURNAL):
        rid, canonical = str(row.get("id")), canonical_form(row)
        if rid in known and known[rid] != canonical:
            raise SystemExit(
                f"FAIL journal id {rid} appears twice with different content; "
                "resolve events.jsonl by hand before carrying")
        known[rid] = canonical
    # Дедупликация обязана работать и ВНУТРИ партии: один и тот же `id` может
    # лежать в леджере дважды или встретиться и в леджере, и в осевшем хвосте
    # (находка независимого ревьюера). Совпадение `id` при РАЗНОМ содержимом -
    # не безобидный повтор, а признак порчи, и молча выбрать одну из копий
    # значит потерять улику: это отказ.
    fresh, seen = [], {}
    for row in pending:
        rid = str(row.get("id"))
        canonical = canonical_form(row)
        if rid in seen:
            if seen[rid] != canonical:
                raise SystemExit(
                    f"FAIL audit id {rid} carries two different payloads; "
                    "resolve the ledger by hand before carrying")
            continue
        seen[rid] = canonical
        if rid in known:
            if known[rid] != canonical:
                raise SystemExit(
                    f"FAIL audit id {rid} already exists in the journal with "
                    "different content; resolve it by hand before carrying")
            continue
        fresh.append(row)
    if dry_run:
        print(json.dumps({"carried": len(fresh), "pending": len(pending),
                          "status": "DRY-RUN"}, sort_keys=True))
        return 0
    if fresh:
        payload = "".join(json.dumps(row, ensure_ascii=False) + "\n"
                          for row in fresh).encode("utf-8")
        safe_atomic().durable_append_bytes(memory / JOURNAL, payload, root=root)
    print(json.dumps({"carried": len(fresh), "pending": len(pending),
                      "status": "CARRIED"}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["carry"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return carry(pathlib.Path(args.root).resolve(), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
