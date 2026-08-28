#!/usr/bin/env python3
"""GENG-C-EXP фаза 0: PRE/NEW-декомпозиция находок серии N7 (r2-r7).

Вопрос юнита: находят ли N параллельных ревьюеров на ОДНОМ кандидате то, что
приходит в последовательных раундах 2..N? Ревьюер продюсера без состояния,
поэтому N последовательных заходов по НЕИЗМЕННОМУ кандидату эквивалентны N
параллельным. Значит вся разница сегодняшних раундов — в том, что кандидат
правится между ними. Отсюда классификация каждой находки раунда k:

  PRE  — участок, о котором находка, ПРИСУТСТВОВАЛ в кандидате раунда k-1;
         параллельный веер на том кандидате имел физическую возможность её дать.
  NEW  — участок появился вместе с правкой по находкам раунда k-1; веер дать
         её не мог по построению.
  UNDECIDABLE — якорь не локализуется в байтах промпта; в PRE/NEW не сваливается.

Класс присваивается МЕХАНИЧЕСКИ: наличие якорной строки в байтах промпта
предыдущего раунда, а не суждением. Промпты — то, что реально видел ревьюер.

Протокол: .itd-memory/measurements/GENG-C-EXP-protocol.md (пре-регистрация).
Stdlib-only, детерминированный, идемпотентный.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
VL = ROOT / ".itd-memory" / "verification-loop"
OUT = ROOT / ".itd-memory" / "measurements" / "GENG-C-EXP-phase0.json"
ROUNDS = (2, 3, 4, 5, 6, 7)

# Находки, дедуплицированные по существу: отчёты повторяют один дефект дважды
# (юнитный срез + интеграционный), это ОДНА находка, а не две.
# anchors — якорные строки: если ЛЮБАЯ из них есть в промпте предыдущего
# раунда, участок в том кандидате присутствовал.
FINDINGS = [
    # r2 — базовый заход серии: предыдущего раунда нет, класс BASELINE.
    dict(id="r2.A", round=2, severity="high", family="entryCommit-binding",
         anchors=["entryCommit"],
         summary="fail-closed пересчёт не резолвит entryCommit"),
    dict(id="r2.B", round=2, severity="medium", family="row-identity",
         anchors=["outsideMirror"],
         summary="26 строк не привязаны к именам внезеркальных сьютов"),
    # r3
    dict(id="r3.C", round=3, severity="medium", family="scope-path",
         anchors=["ORACLE-DEBT-check.py"],
         summary="новый чекер вне замороженного списка путей SCOPE_LOCK"),
    dict(id="r3.D", round=3, severity="medium", family="row-schema",
         anchors=["seconds", "duration"],
         summary="строки замера не обязаны нести длительность и класс"),
    dict(id="r3.E", round=3, severity="low", family="entryCommit-binding",
         anchors=["entryState"],
         summary="entryState.commit не обязан равняться entryCommit"),
    dict(id="r3.F", round=3, severity="medium", family="class-vocabulary",
         anchors=["classes"],
         summary="словарь классов не пинится, принимается любой непустой"),
    # r4
    dict(id="r4.G", round=4, severity="medium", family="aggregates",
         anchors=["counts", "phaseRequired"],
         summary="агрегаты counts/категории не пересчитываются из строк"),
    dict(id="r4.H", round=4, severity="medium", family="mirror-parser",
         anchors=["mirror_executed"],
         summary="mirror_executed срезает только строки-комментарии целиком"),
    # r5
    dict(id="r5.I", round=5, severity="high", family="entryCommit-binding",
         anchors=["entryState"],
         summary="entryState.commit не привязан к entryCommit/базе кандидата"),
    dict(id="r5.J", round=5, severity="medium", family="class-vocabulary",
         anchors=["classes"],
         summary="словарь классов по-прежнему не пинится"),
    # r6
    dict(id="r6.K", round=6, severity="medium", family="corefull-binding",
         anchors=["outsideMirrorByCoreFull"],
         summary="outsideMirrorByCoreFull не привязан к историческим CORE/FULL"),
    dict(id="r6.L", round=6, severity="high", family="provenance",
         anchors=["historicalRouteApprovalProvenance"],
         summary="провенанс одобрения v5 самозаверяющий"),
    # r7
    dict(id="r7.M", round=7, severity="high", family="acceptance-overclaim",
         anchors=["verify_harness_conformance"],
         summary="критерий обещает 5/5, улика показывает 4/5"),
    dict(id="r7.N", round=7, severity="medium", family="count-convention",
         anchors=["ORACLE-DEBT-2-class-measured"],
         summary="критерий называет 124/26 против строгих 125/25 замера"),
    dict(id="r7.O", round=7, severity="medium", family="registry-reproduce",
         anchors=["--phase <phase>"],
         summary="реестр обещает воспроизведение плейсхолдером"),
]


def load_prompts() -> dict[int, bytes]:
    prompts: dict[int, bytes] = {}
    for k in ROUNDS:
        path = VL / f"ORACLE-DEBT-r{k}-prompt.md"
        if not path.is_file():
            raise SystemExit(f"FAIL: prompt for round r{k} is missing: {path}")
        prompts[k] = path.read_bytes()
    return prompts


def classify(prompts: dict[int, bytes]) -> list[dict]:
    rows = []
    for item in FINDINGS:
        k = item["round"]
        prev = k - 1
        if prev < min(ROUNDS):
            verdict, seen = "BASELINE", None
        else:
            hits = [a for a in item["anchors"]
                    if a.encode("utf-8") in prompts[prev]]
            if hits:
                verdict, seen = "PRE", hits
            else:
                # Якоря нет в предыдущем промпте. Отличаем «участка не было»
                # от «якорь неудачный»: если якоря нет и в СВОЁМ раунде, класс
                # неопределим — это дефект якоря, а не факт о кандидате.
                own = [a for a in item["anchors"]
                       if a.encode("utf-8") in prompts[k]]
                verdict, seen = ("NEW", []) if own else ("UNDECIDABLE", [])
        rows.append({**item, "previousRound": prev if prev >= min(ROUNDS) else None,
                     "class": verdict, "anchorsHit": seen})
    return rows


def main() -> int:
    prompts = load_prompts()
    rows = classify(prompts)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    decidable = counts.get("PRE", 0) + counts.get("NEW", 0)
    payload = {
        "unit": "GENG-C-EXP",
        "phase": 0,
        "protocol": ".itd-memory/measurements/GENG-C-EXP-protocol.md",
        "corpus": {
            "series": "ORACLE-DEBT r2-r7 (N7)",
            "rounds": list(ROUNDS),
            "promptBytes": {f"r{k}": len(v) for k, v in prompts.items()},
            "allCandidatesDistinct": len({bytes(v) for v in prompts.values()}) == len(prompts),
        },
        "findings": rows,
        "counts": counts,
        "preShareOfDecidable": (round(counts.get("PRE", 0) / decidable, 3)
                                if decidable else None),
        "familiesRepeated": sorted({r["family"] for r in rows
                                    if sum(1 for x in rows
                                           if x["family"] == r["family"]) > 1}),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({"counts": counts,
                      "preShareOfDecidable": payload["preShareOfDecidable"],
                      "familiesRepeated": payload["familiesRepeated"]},
                     ensure_ascii=False))
    for row in rows:
        print(f"  {row['id']:6s} {row['class']:11s} {row['family']:22s} {row['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
