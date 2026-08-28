#!/usr/bin/env python3
"""Проверка чисел замера N7 (ORACLE-DEBT) против самого дерева.

Что здесь ОБЯЗАТЕЛЬНО и полностью пересчитывается из дерева: пост-состояние
(что зеркало исполняет сейчас, что осталось снаружи, совпадает ли реестр).
Что проверяется как ЗАМОРОЖЕННОЕ ОБЪЯВЛЕНИЕ, а не пересчитывается: состояние
входа — его исходник (`tests/run-all.sh` на entry-коммите) в рабочем дереве
уже недоступен. Поэтому вход объявлен ПОИМЁННО (`entryState.mirrorExecuted`,
`outsideMirrorExecuted`, `outsideMirrorByCoreFull`), и проверяется, что эти
списки разбивают ровно то множество сьютов, которое лежит на диске, что числа
равны длинам списков, и что строки замера — это ИМЕННО внезеркальное множество
входа, а не произвольные 26 записей. Прежняя версия принимала любые числа
входа, лишь бы они давали в сумме 150, и называла себя fail-closed
пересчётом — находка ревьюера r2 (high + medium), закрыта здесь.

Когда объектная база доступна (обычный хост, не изолят), объявление входа
ДОПОЛНИТЕЛЬНО сверяется с `git show <entryCommit>:tests/run-all.sh` — это
усиление; недостижимость истории не ослабляет обязательную часть.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shlex
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
MEASUREMENT = ROOT / ".itd-memory" / "measurements" / "ORACLE-DEBT-n7.json"
RUNALL = ROOT / "tests" / "run-all.sh"
REGISTRY = ROOT / "tests" / "OUT_OF_MIRROR.json"

failed = 0
total = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failed, total
    total += 1
    if cond:
        print("PASS  " + name)
        return
    failed += 1
    print("FAIL  " + name + ((" [" + detail + "]") if detail else ""))


def mirror_executed(text: str) -> tuple[set, list[str]]:
    """Имена сьютов, которые зеркало РЕАЛЬНО исполняет, и нечитаемые строки.

    Хвостовые проверки берутся только из исполняемых вызовов, разобранных
    shlex'ом с comments=True: строчный комментарий вида
    `cmd  # tests/verify_new.py` иначе объявил бы сьют прогоняемым (находка
    ревьюера r4). Логика намеренно совпадает с `mirror_executed` в
    tests/verify_runall_drift.py и продублирована, а не импортирована: чекер
    обязан работать в изоляте, где импорт из tests/ не гарантирован; расхождение
    двух копий ловится тем, что оба считают одно и то же множество и обе
    проверки гоняются в одной машинной ноге.
    """
    names: set = set()
    for variable in ("CORE", "FULL"):
        match = re.search(rf'^{variable}="(.*?)"', text, re.M | re.S)
        if match:
            names.update(word for word in match.group(1).split()
                         if word.startswith("verify_"))
    unparsed: list[str] = []
    for line in text.splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            if "tests/verify_" in line:
                unparsed.append(line.strip()[:120])
            continue
        if not tokens or tokens[0] not in ("run_tail", "run_py"):
            continue
        for token in tokens[1:]:
            hit = re.fullmatch(r"tests/(verify_\w+)\.py", token)
            if hit:
                names.add(hit.group(1))
    return names, unparsed


def main() -> int:
    try:
        measurement = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        runall = RUNALL.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:  # noqa: BLE001 — fail-closed
        print("FAIL  inputs readable [%s]" % exc)
        return 1

    on_disk = {p.name[:-3] for p in (ROOT / "tests").glob("verify_*.py")}
    executed, unparsed = mirror_executed(runall)
    check("post-state: every run-all line that names a suite is parseable",
          not unparsed, "unparseable: %s" % unparsed[:3])
    outside = sorted(on_disk - executed)
    counts = measurement.get("counts") or {}

    check("post-state: suites on disk matches the tree",
          counts.get("onDisk") == len(on_disk),
          "recorded=%s actual=%d" % (counts.get("onDisk"), len(on_disk)))
    check("post-state: strict mirror count matches run-all.sh",
          counts.get("mirrorStrictPost") == len(executed & on_disk),
          "recorded=%s actual=%d" % (counts.get("mirrorStrictPost"),
                                     len(executed & on_disk)))
    check("post-state: strict out-of-mirror count matches run-all.sh",
          counts.get("outsideMirrorStrictPost") == len(outside),
          "recorded=%s actual=%d" % (counts.get("outsideMirrorStrictPost"),
                                     len(outside)))
    entry = measurement.get("entryState") or {}
    entry_mirror = entry.get("mirrorExecuted")
    entry_outside = entry.get("outsideMirrorExecuted")
    entry_outside_cf = entry.get("outsideMirrorByCoreFull")
    named = all(isinstance(value, list) and value
                for value in (entry_mirror, entry_outside, entry_outside_cf))
    check("entry: the entry state is declared by name, not only by count", named)
    if not named:
        print("\n%d checks, %d failed" % (total, failed))
        return 1
    entry_mirror, entry_outside = set(entry_mirror), set(entry_outside)
    entry_outside_cf = set(entry_outside_cf)
    check("entry: named mirror and outside sets partition the suites on disk",
          entry_mirror.isdisjoint(entry_outside)
          and entry_mirror | entry_outside == on_disk,
          "symmetric difference: %s"
          % sorted((entry_mirror | entry_outside) ^ on_disk))
    check("entry: counts equal the length of the named sets",
          counts.get("mirrorStrictEntry") == len(entry_mirror)
          and counts.get("outsideMirrorStrictEntry") == len(entry_outside),
          "recorded=%s/%s named=%d/%d" % (counts.get("mirrorStrictEntry"),
                                          counts.get("outsideMirrorStrictEntry"),
                                          len(entry_mirror), len(entry_outside)))
    check("entry: the CORE/FULL outside set contains the strict one",
          entry_outside <= entry_outside_cf <= on_disk)
    # Усиление, когда история доступна: объявленный вход обязан совпасть с
    # реальным tests/run-all.sh на entry-коммите. В изоляте объектной базы нет,
    # и эта проверка молча не выполняется — обязательная часть выше от неё не
    # зависит.
    entry_commit = str(entry.get("commit") or "")
    # Коммит входа обязан совпадать с верхнеуровневым entryCommit записи: иначе
    # подменённое значение уводило бы усиление в тихий пропуск, и объявленные
    # множества принимались бы вообще без сверки (находка ревьюера r5, high).
    check("entry: the declared entry commit is bound to the record's entryCommit",
          bool(re.fullmatch(r"[0-9a-f]{40}", entry_commit))
          and entry_commit == str(measurement.get("entryCommit") or ""),
          "entryState.commit=%s entryCommit=%s"
          % (entry_commit[:12], str(measurement.get("entryCommit"))[:12]))
    # Пропуск усиления разрешён ТОЛЬКО там, где объектной базы нет вовсе
    # (изолят). Там, где репозиторий есть, недостижимый коммит входа — красный,
    # а не «молча пропустили».
    in_repository = subprocess.run(["git", "rev-parse", "--git-dir"],
                                   cwd=str(ROOT), capture_output=True,
                                   text=True).returncode == 0
    if in_repository and re.fullmatch(r"[0-9a-f]{40}", entry_commit):
        shown = subprocess.run(["git", "show", f"{entry_commit}:tests/run-all.sh"],
                               cwd=str(ROOT), capture_output=True, text=True)
        check("entry: the entry commit resolves where an object database exists",
              shown.returncode == 0, shown.stderr.strip()[:120])
        if shown.returncode == 0:
            historical = mirror_executed(shown.stdout)[0] & on_disk
            check("entry (strengthening): declaration matches run-all.sh at the entry commit",
                  historical == entry_mirror and on_disk - historical == entry_outside,
                  "declared-but-not-historical: %s" % sorted(entry_mirror ^ historical))
            # Множество по CORE/FULL проверялось лишь как надмножество строгого,
            # поэтому подмена одного имени (единственная штатная разница —
            # хвостовой run_tail) проходила незамеченной (находка r6).
            historical_core_full: set = set()
            for variable in ("CORE", "FULL"):
                match = re.search(rf'^{variable}="(.*?)"', shown.stdout, re.M | re.S)
                if match:
                    historical_core_full.update(
                        word for word in match.group(1).split()
                        if word.startswith("verify_"))
            check("entry (strengthening): the CORE/FULL outside set is the historical one",
                  entry_outside_cf == on_disk - (historical_core_full & on_disk),
                  "difference: %s"
                  % sorted(entry_outside_cf ^ (on_disk - (historical_core_full & on_disk))))
            check("entry (strengthening): declared run-all digest matches the entry commit",
                  entry.get("runAllSha256")
                  == hashlib.sha256(shown.stdout.encode("utf-8")).hexdigest())
    else:
        print("NOTE  no object database here: the entry declaration is checked "
              "only by partition and by the row set (isolated path)")

    registered = sorted(pathlib.Path(row.get("suite", "")).name[:-3]
                        for row in registry.get("suites", []))
    check("registry names exactly the suites outside the mirror",
          registered == outside,
          "registry=%s outside=%s" % (registered, outside))

    rows = {row["suite"].split("/")[-1][:-3]: row
            for row in measurement.get("suites", []) if isinstance(row, dict)}
    check("measurement rows are exactly the entry out-of-mirror set",
          len(rows) == len(measurement.get("suites", []))
          and set(rows) == entry_outside_cf,
          "rows=%d symmetric difference=%s"
          % (len(rows), sorted(set(rows) ^ entry_outside_cf)))
    # Каждая строка обязана иметь закрытую форму и класс из закрытого перечня:
    # иначе подменённый набор строк с верным числом «зелёных» проходил бы, а
    # опубликованная разбивка по классам не проверялась вовсе (находка r4).
    row_classes = {"green-standalone", "phase-required", "candidate-bound",
                   "external-evidence-absent", "mirror-runner"}
    malformed = [name for name, row in rows.items()
                 if set(row) != {"suite", "rc", "seconds", "class", "lastLine"}
                 or not isinstance(row.get("rc"), int)
                 or not isinstance(row.get("seconds"), int)
                 or row.get("seconds") < 0
                 or row.get("class") not in row_classes
                 or ((row.get("rc") == 0) is not (row.get("class") == "green-standalone"))]
    check("every measurement row has a closed shape and a class consistent with its rc",
          not malformed, "malformed: %s" % sorted(malformed)[:5])
    by_class: dict = {}
    for row in rows.values():
        by_class[row.get("class")] = by_class.get(row.get("class"), 0) + 1
    check("class breakdown partitions the rows",
          sum(by_class.values()) == len(rows))
    published = {
        "greenStandalone": "green-standalone",
        "phaseRequired": "phase-required",
        "candidateBound": "candidate-bound",
        "externalEvidenceAbsent": "external-evidence-absent",
        "mirrorRunner": "mirror-runner",
    }
    mismatched = {key: (counts.get(key), by_class.get(label, 0))
                  for key, label in published.items()
                  if counts.get(key) != by_class.get(label, 0)}
    check("every published class count is recomputed from the rows",
          not mismatched, "recorded vs actual: %s" % mismatched)
    check("published CORE/FULL totals are recomputed from the entry set",
          counts.get("outsideMirror") == len(entry_outside_cf) == len(rows)
          and counts.get("mirror") == len(on_disk) - len(entry_outside_cf),
          "outside=%s mirror=%s" % (counts.get("outsideMirror"), counts.get("mirror")))
    green = [name for name, row in rows.items() if row.get("rc") == 0]
    check("measured green-standalone count matches the rows",
          counts.get("greenStandalone") == len(green),
          "recorded=%s actual=%d" % (counts.get("greenStandalone"), len(green)))
    check("published green wall-clock total is recomputed from the rows",
          counts.get("greenSecondsTotal")
          == sum(row.get("seconds", 0) for row in rows.values() if row.get("rc") == 0),
          "recorded=%s actual=%d"
          % (counts.get("greenSecondsTotal"),
             sum(row.get("seconds", 0) for row in rows.values() if row.get("rc") == 0)))
    check("every measured green suite now runs in the mirror",
          all(name in executed for name in green),
          "still outside: %s" % sorted(set(green) - executed))
    check("every measured red suite stays classified in the registry",
          all(name in registered or name in executed
              for name, row in rows.items() if row.get("rc") != 0),
          "unclassified: %s" % sorted(name for name, row in rows.items()
                                      if row.get("rc") != 0
                                      and name not in registered
                                      and name not in executed))

    refutation = measurement.get("mergeRefutation") or {}
    donor, keeper = "tests/verify_brownfield_and_gate.py", "tests/verify_skill_enforcement.py"
    check("merge refutation keeps both suites in the tree",
          refutation.get("pair") == [donor, keeper]
          and (ROOT / donor).is_file() and (ROOT / keeper).is_file())

    print("\n%d checks, %d failed" % (total, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
