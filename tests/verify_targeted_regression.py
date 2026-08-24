#!/usr/bin/env python3
"""verify_targeted_regression.py — оракул LPD-003-1: run-all перестаёт быть
входом по умолчанию для точечной правки.

Замер G0 (743 квитанции, 2026-08-22): `tests/run-all.sh` — 859 из 1054 минут
машинного слоя (82%), из них 128 минут — прогоны, уже ставшие красными и
доигранные до конца. Этот гард закрывает три отдельных класса дефекта, каждый
проверяемый независимо:

1. **false-red по host-owned входу.** Сьюты, берущие значение у ХОСТА (а не у
   репозитория), в изолированном дереве машинного продюсера не видят своего
   входа: `.itd-memory/` git-ignored, а изоляция материализует только tracked
   staged tree. Сегодня это печатается как `FAIL <suite>` и неотличимо от
   сломанного кандидата. Класс входа обязан быть отдельным (`BLOCKED`), с
   WHY+FIX и по-прежнему НЕнулевым кодом выхода — иначе вместо false-red
   получится false-green.
2. **доигрывание красного прогона.** Первый красный сьют не останавливает
   остальные ~100; `--fail-fast` обязан останавливать.
3. **отсутствие targeted-маршрута.** Отбор сьютов по `.itd/IMPACT_GRAPH.json`
   обязан быть ПОЛНЫМ (ни один сьют, связанный картой с изменённым файлом, не
   теряется), fail-closed на неизвестном пути (уходить в полный прогон, а не
   молча сужать) и подмножеством зеркала run-all.

Тесты полноты сформулированы против НЕЗАВИСИМОГО пересчёта из карты, поэтому
удаление ребра ломает их, а не подгоняет.

Stdlib-only, кросс-платформенный.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNALL = ROOT / "tests" / "run-all.sh"
SELECTOR = ROOT / "scripts" / "itd_regression_select.py"
GRAPH = ROOT / ".itd" / "IMPACT_GRAPH.json"
PATTERNS = ROOT / ".itd" / "IMPACT_PATTERNS.json"

passed = failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print("PASS  %s" % name)
    else:
        failed += 1
        print("FAIL  %s%s" % (name, (" — " + detail) if detail else ""))


def run_selector(args: list[str], root: Path | None = None,
                 timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SELECTOR), *args],
        cwd=str(root or ROOT), capture_output=True, text=True, timeout=timeout,
    )


def _load_selector_module():
    """Внутренний шов вместо публичного override карты.

    Селектор судит только тот репозиторий, в котором лежит (`.itd/DECISIONS.md`,
    2026-08-24), поэтому подложить карту снаружи процессом больше нельзя. Тесты
    мутаций грузят модуль и зовут `load_graph()`/`select()` напрямую — это и
    есть тот шов, который заменяет удалённый флаг.
    """
    spec = importlib.util.spec_from_file_location("itd_regression_select", SELECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def runall_universe() -> set[str]:
    """Имена сьютов зеркала — намеренно ДРУГИМ разбором, чем у селектора.

    Селектор извлекает их регэкспом; повторить тот же регэксп здесь означало бы
    проверять парсер самим собой (находка ревьюера, LPD-003-1). Здесь разбор
    построчный: набираем токены между присваиванием CORE=/FULL= и закрывающей
    кавычкой, учитывая перенос строки обратным слешем.
    """
    names: set[str] = set()
    collecting = False
    for line in RUNALL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not collecting:
            for key in ("CORE=\"", "FULL=\""):
                if stripped.startswith(key):
                    stripped = stripped[len(key):]
                    collecting = True
                    break
            if not collecting:
                continue
        if stripped.endswith('"'):
            stripped = stripped[:-1]
            collecting = False
        elif stripped.endswith("\\"):
            stripped = stripped[:-1]
        names.update(token for token in stripped.split()
                     if token and not token.startswith("#"))
    return names


def graph_edges() -> dict[str, list[str]]:
    document = json.loads(GRAPH.read_text(encoding="utf-8"))
    edges: dict[str, list[str]] = {}
    for section in ("declared", "generated"):
        for source, targets in (document.get(section) or {}).items():
            edges.setdefault(source, [])
            for target in targets:
                if target not in edges[source]:
                    edges[source].append(target)
    return edges


def expected_suites(changed: list[str], edges: dict[str, list[str]]) -> set[str]:
    """Независимый пересчёт: транзитивное замыкание, отфильтрованное до сьютов."""
    seen: set[str] = set()
    queue = list(changed)
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(edges.get(node, []))
    return {
        Path(node).stem for node in seen
        if node.startswith("tests/") and Path(node).name.startswith("verify_")
        and node.endswith(".py")
    }


def fake_python(directory: Path, log: Path, name: str,
                exit_code: int = 1, delegate: str = "") -> Path:
    """Подставной интерпретатор: пишет каждый прогон в лог и падает.

    run-all.sh уважает $PYTHON, поэтому счётчик запусков — прямой замер того,
    остановился ли прогон на первом красном сьюте. ``delegate`` — подстрока
    аргумента, при которой вызов уходит НАСТОЯЩЕМУ интерпретатору: селектор
    тоже вызывается через $PYTHON, и без делегирования любой targeted-прогон
    сваливался бы в strict, то есть тест мерил бы не то, что заявлено.
    """
    script = directory / ("fake_python_%s.sh" % name)
    delegation = (
        'case "$*" in\n'
        '  *%s*) exec %s "$@" ;;\n'
        'esac\n' % (delegate, sys.executable)
    ) if delegate else ""
    script.write_text(
        "#!/bin/sh\n"
        "# `-c` используется run-all.sh для пробы интерпретатора — она обязана\n"
        "# пройти, иначе скрипт молча уйдёт на другой интерпретатор.\n"
        'if [ "$1" = "-c" ]; then exit 0; fi\n'
        + delegation
        + 'printf "%%s\\n" "$*" >> "%s"\n'
        "exit %d\n" % (log.as_posix(), exit_code),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def runall_copy(text: str, destination: Path) -> Path:
    """Копия run-all.sh, выполняющаяся ПРОТИВ корня репозитория.

    Оригинал делает `cd "$(dirname "$0")/.."`, поэтому копия во временном
    каталоге считала бы сьюты в /tmp и молча меряла не то (поймано на самой
    этой проверке).
    """
    anchored = text.replace('cd "$(dirname "$0")/.." || exit 1',
                            'cd "%s" || exit 1' % ROOT.as_posix())
    destination.write_text(anchored, encoding="utf-8")
    return destination


def run_runall(args: list[str], env_extra: dict[str, str] | None = None,
               timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["sh", str(RUNALL), *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, env=env,
    )


def main() -> int:
    check("selector exists", SELECTOR.is_file(),
          "expected %s" % SELECTOR.relative_to(ROOT))
    if not SELECTOR.is_file():
        print("\n%d passed, %d failed" % (passed, failed))
        return 1

    edges = graph_edges()
    universe = runall_universe()
    text_for_counts = RUNALL.read_text(encoding="utf-8")
    check("parser: run-all universe is non-trivial", len(universe) >= 100,
          "parsed %d suite names" % len(universe))

    # --- 3a. Полнота отбора против независимого пересчёта --------------------
    # Ожидания объявлены ЗДЕСЬ, а не выведены из той же карты: сравнение
    # «выбор == замыкание карты» проходило бы и после реальной потери ребра
    # (находка cross-vendor ревьюера). Якоря — сьюты, которые исполняют
    # именно этот файл, по смыслу, а не по данным карты.
    samples = [
        (["skills/_shared/itd_verification_loop.py"],
         {"verify_verification_loop", "verify_review_cache",
          "verify_push_gate_adjudicated"}),
        (["hooks/completion-gate.sh"],
         {"verify_completion_gate", "verify_strict_completion_policy"}),
        (["skills/_shared/itd_verification_loop.py", "tests/run-all.sh"],
         {"verify_verification_loop", "verify_runall_drift",
          "verify_targeted_regression"}),
    ]
    for changed, sample_anchors in samples:
        result = run_selector(["--changed", *changed, "--format", "json"])
        label = ",".join(Path(c).name for c in changed)
        if result.returncode != 0:
            check("selector selects for %s" % label, False,
                  "rc=%d %s" % (result.returncode, result.stderr.strip()[:200]))
            continue
        payload = json.loads(result.stdout)
        selected = set(payload.get("suites") or [])
        named = set(payload.get("outsideMirror") or [])
        expected = expected_suites(changed, edges)
        missing = sorted(expected - selected - named)
        check("nothing from the map closure is dropped silently for %s" % label,
              not missing,
              "map links these suites, selector neither runs nor names them: %s"
              % missing[:6])
        missing_files = sorted(
            name for name in selected
            if not (ROOT / "tests" / ("%s.py" % name)).is_file())
        check("every selected suite exists for %s" % label, not missing_files,
              "selected suites without a file: %s" % missing_files[:6])
        # Карта покрывает ВСЕ tests/verify_*.py, а зеркало run-all — только то,
        # что гоняет CI. Пересечения мало: сьют-сирота (существует, но его не
        # гоняет ни CI, ни run-all) — это false-green класс сам по себе.
        # Targeted обязан такие сьюты ГОНЯТЬ (строго сильнее зеркала) и
        # НАЗЫВАТЬ их, а не тихо расширять набор.
        # Сьюты вне зеркала (свой флаг/кандидат/пин) прогоном «просто так»
        # дают false-red — их называют, а не гоняют. Обе половины проверяются:
        # ничего гоняемого не потеряно, ничего негоняемого не запущено.
        check("the run set contains only suites the mirror can run for %s" % label,
              selected <= universe,
              "would run outside the mirror: %s" % sorted(selected - universe)[:6])
        check("suites outside the mirror are named, not silent for %s" % label,
              named == (expected - universe),
              "named %s, actually outside: %s"
              % (sorted(named)[:6], sorted(expected - universe)[:6]))
        check("selection is proportional for %s" % label,
              0 < len(selected) < len(universe),
              "selected %d of %d" % (len(selected), len(universe)))
        check("declared anchors are selected for %s" % label,
              sample_anchors <= (selected | named),
              "the map lost suites that must exercise this path: %s"
              % sorted(sample_anchors - (selected | named)))

    # --- 3b. Мутация карты: убранное ребро обязано ломать полноту ------------
    document = json.loads(GRAPH.read_text(encoding="utf-8"))
    node = "skills/_shared/itd_verification_loop.py"
    generated = dict(document.get("generated") or {})
    dropped = list(generated.get(node) or [])
    if len(dropped) >= 2:
        with tempfile.TemporaryDirectory(prefix="itd-targeted-mutation-") as td:
            mutant_map = Path(td) / "IMPACT_GRAPH.json"
            mutated = json.loads(json.dumps(document))
            mutated["generated"][node] = dropped[:1]
            mutant_map.write_text(json.dumps(mutated), encoding="utf-8")
            # Внутренний шов, а не публичный флаг: `--graph` удалён вместе с
            # `--root`/`--rules` (решение 2026-08-24, `.itd/DECISIONS.md`) —
            # публичный override карты порождал неисчерпаемый класс находок
            # «чужая карта сужает прогон». Гарантия «убранное ребро сужает
            # выбор» проверяется тем же способом, что и раньше.
            mutation_module = _load_selector_module()
            try:
                mutant_selected = set(mutation_module.select(
                    [node], mutation_module.load_graph(mutant_map),
                    mutation_module.load_patterns(PATTERNS))["suites"])
            except mutation_module.StrictRequired:
                mutant_selected = set()
            # Якорь объявлен ЗДЕСЬ, а не выведен из той же карты: сравнение
            # «мутант меньше текущего графа» проходило бы и после реального
            # удаления ребра из репозиторной карты (находка cross-vendor
            # ревьюера). Эти три сьюта обязаны быть в замыкании узла по
            # смыслу — они исполняют именно его.
            anchors = {"verify_verification_loop", "verify_review_cache",
                       "verify_push_gate_adjudicated"}
            live_selection = expected_suites([node], edges)
            check("the map still links the loop module to its own suites",
                  anchors <= live_selection,
                  "missing from the live map closure: %s"
                  % sorted(anchors - live_selection))
            check("map mutation shrinks the selection (guard is load-bearing)",
                  mutant_selected < live_selection
                  and not anchors <= mutant_selected,
                  "mutant selected %d of %d, anchors still present: %s"
                  % (len(mutant_selected), len(live_selection),
                     sorted(anchors & mutant_selected)))
    else:
        check("map mutation fixture is available", False,
              "node %s has %d edges" % (node, len(dropped)))

    # --- 3c. Неизвестный путь: fail-closed в полный прогон -------------------
    result = run_selector(
        ["--changed", "src/does/not/exist/in/the/map.py", "--format", "json"])
    check("unknown path fails closed instead of narrowing",
          result.returncode != 0
          and "strict" in (result.stdout + result.stderr).lower(),
          "rc=%d out=%s" % (result.returncode,
                            (result.stdout + result.stderr).strip()[:200]))

    # --- 3d. Правила для путей, которые нельзя перечислить узлами ------------
    # Контракты юнитов и записи прогонов создаются каждый раз заново, узлами
    # карты они не станут никогда; без правил targeted не применяется вообще
    # (замер: 2 из 3 недавних юнитов уходили в strict). Правило «влияния нет»
    # опасно ровно тем, чем лечим, поэтому оно судится ПРОТИВ карты, а не
    # принимается на веру.
    selector_module = _load_selector_module()
    rules = json.loads(PATTERNS.read_text(encoding="utf-8"))["rules"]
    check("impact rules exist and are non-trivial", len(rules) >= 3,
          "%d rules" % len(rules))
    # Узлы берутся из ОБЕИХ секций: селектор ходит по declared+generated, и
    # правило no-impact, противоречащее ручному declared-ребру, обязано быть
    # поймано так же, как противоречащее сгенерированному (находка
    # cross-vendor ревьюера).
    graph_document = json.loads(GRAPH.read_text(encoding="utf-8"))
    graph_nodes = sorted(set(graph_document.get("generated") or {})
                         | set(graph_document.get("declared") or {}))
    for rule in rules:
        pattern = rule["pattern"]
        if rule["effect"] == "suites":
            unknown = [name for name in rule["suites"]
                       if not (ROOT / "tests" / ("%s.py" % name)).is_file()]
            check("rule %s names existing suites" % pattern, not unknown,
                  "unknown suites: %s" % unknown)
            check("rule %s names suites the mirror can run" % pattern,
                  set(rule["suites"]) <= universe,
                  "outside the mirror: %s"
                  % sorted(set(rule["suites"]) - universe))
        else:
            contradicting = [node for node in graph_nodes
                             if selector_module.match_rule(node, [rule])]
            check("rule %s claims no impact and the map agrees" % pattern,
                  not contradicting,
                  "the generated map links these paths to suites: %s"
                  % contradicting[:4])

    # Правило, называющее несуществующий сьют, обязано валить загрузку правил,
    # а не молча расширять выбор пустотой (находка cross-vendor ревьюера).
    # Правило, называющее несуществующий сьют, обязано отвергаться при
    # ЗАГРУЗКЕ правил. CLI-флага --rules больше нет, поэтому проверка идёт
    # через модуль (находка cross-vendor ревьюера: комментарий требовал, а
    # мутантного файла правил после упрощения не осталось).
    with tempfile.TemporaryDirectory(prefix="itd-bogus-rule-") as td:
        bogus_rules = Path(td) / "rules.json"
        bogus_rules.write_text(json.dumps({"rules": [{
            "pattern": ".itd-memory/contracts/*.md", "effect": "suites",
            "suites": ["verify_this_suite_does_not_exist"],
            "why": "deliberately wrong rule used to prove the validator bites"}]}),
            encoding="utf-8")
        try:
            selector_module.load_patterns(bogus_rules)
            bogus_closed, bogus_detail = False, "a missing suite name was accepted"
        except selector_module.StrictRequired as exc:
            bogus_closed = "do not exist" in str(exc)
            bogus_detail = str(exc)[:160]
        check("a rule naming a missing suite fails closed", bogus_closed, bogus_detail)

    # Корень файла правил обязан быть объектом. `load_graph` это проверяет, а
    # `load_patterns` шла сразу в `document.get()`: синтаксически валидный
    # файл с корнем-массивом, строкой или null давал AttributeError и exit 1
    # вместо документированного strict с WHY+FIX (находка cross-vendor
    # ревьюера). Непрочитанные правила — неизвестное влияние, а не пустой
    # набор правил.
    with tempfile.TemporaryDirectory(prefix="itd-rules-root-") as td:
        for label, payload in (("array", "[]"), ("string", '"rules"'),
                               ("null", "null"), ("number", "7")):
            rooted = Path(td) / ("rules-%s.json" % label)
            rooted.write_text(payload, encoding="utf-8")
            try:
                selector_module.load_patterns(rooted)
                closed, detail = False, "a non-object rules root was accepted"
            except selector_module.StrictRequired as exc:
                closed, detail = True, str(exc)[:160]
            except Exception as exc:  # noqa: BLE001 - именно это и есть дефект
                closed = False
                detail = "%s escaped instead of StrictRequired: %s" % (
                    type(exc).__name__, str(exc)[:120])
            check("a rules file rooted in %s fails closed" % label, closed, detail)

    # Шаблон правила НЕ должен переходить границу каталога: `*` в fnmatch
    # означал «в том числе через /», и правило про один каталог говорило за
    # всё поддерево (находка cross-vendor ревьюера).
    single = [{"pattern": ".itd-memory/contracts/*.md", "effect": "suites",
               "suites": ["verify_task_contract_advisory"], "why": "one directory"}]
    deep = [{"pattern": ".itd-memory/verification-loop/**", "effect": "no-impact",
             "why": "whole subtree"}]
    # Таблица краевых случаев матчера: ручные эвристики здесь дважды дали
    # дефект (fnmatch пропускал `/` через `*`; проверка «хвоста» после `**`
    # сравнивала подстроку, из-за чего `a/**/b.md` ловил `a/xb.md`). Теперь
    # семантика пиннуется таблицей, включая производственный шаблон с `*/**`.
    matcher_cases = [
        (".itd-memory/contracts/A.md", ".itd-memory/contracts/*.md", True),
        (".itd-memory/contracts/nested/A.md", ".itd-memory/contracts/*.md", False),
        ("a/b.md", "a/**/b.md", True),
        ("a/x/y/b.md", "a/**/b.md", True),
        ("a/xb.md", "a/**/b.md", False),
        ("b.md", "**/b.md", True),
        ("weird-b.md", "**/b.md", False),
        (".itd-memory/verification-loop/a/b.json",
         ".itd-memory/verification-loop/**", True),
        ("tests/fixtures/live-model-evidence/runs/X/output/CLAUDE.md",
         "tests/fixtures/live-model-evidence/runs/*/**", True),
        ("tests/fixtures/live-model-evidence/other.json",
         "tests/fixtures/live-model-evidence/runs/*/**", False),
    ]
    mismatched = [
        (path, pattern, expected)
        for path, pattern, expected in matcher_cases
        if selector_module._segment_match(path, pattern) is not expected
    ]
    check("the segment matcher honours path boundaries in every declared case",
          not mismatched, "cases that disagree: %s" % mismatched[:4])

    # match_rule обязан отвечать РОВНО тем же, что матчер: прежние префиксные
    # эвристики пережили переписывание и расходились с ним (находка
    # cross-vendor ревьюера), а несколько `**` без мемоизации уводили выбор в
    # комбинаторный перебор вместо честного strict.
    tail_rule = [{"pattern": "a/*/**/c.md", "effect": "suites",
                  "suites": ["verify_targeted_regression"], "why": "tail after **"}]
    check("match_rule agrees with the segment matcher on a tail after **",
          selector_module.match_rule("a/b", tail_rule) is None
          and selector_module.match_rule("a/b/x/c.md", tail_rule) is not None,
          "match_rule diverges from _segment_match on a pattern with a ** tail")
    heavy_pattern = "/".join(["**"] * 12) + "/z.md"
    heavy_path = "/".join("s%d" % index for index in range(20)) + "/z.md"
    started = time.monotonic()
    heavy_result = selector_module._segment_match(heavy_path, heavy_pattern)
    elapsed = time.monotonic() - started
    check("many ** tokens stay linear, not combinatorial",
          heavy_result and elapsed < 5.0,
          "12 ** tokens over 20 segments took %.2fs (result %s)"
          % (elapsed, heavy_result))

    check("a single-star rule stays inside its directory",
          bool(selector_module.match_rule(".itd-memory/contracts/A.md", single))
          and not selector_module.match_rule(
              ".itd-memory/contracts/nested/A.md", single),
          "single-star pattern crossed a path separator")
    check("a double-star rule spans the subtree",
          bool(selector_module.match_rule(
              ".itd-memory/verification-loop/a/b.json", deep)),
          "double-star pattern failed to span the subtree")

    # Каждое правило проверяется ДИНАМИЧЕСКИ: селектор гоняется на пути,
    # совпадающем с шаблоном, и обязан вернуть ровно обещанные сьюты
    # (для no-impact — назвать путь исключённым). Статической проверки имён
    # мало: правило может существовать и всё равно не срабатывать (находка
    # cross-vendor ревьюера).
    for rule in rules:
        pattern = rule["pattern"]
        sample = (pattern.replace("/**", "/deep/sample.json")
                  .replace("/*/", "/one/").replace("*", "sample"))
        # К образцу добавляется реальный путь из карты: набор, состоящий
        # ТОЛЬКО из no-impact-путей, законно уходит в strict, и без спутника
        # проверка мерила бы не то.
        result = run_selector(
            ["--changed", sample, "hooks/completion-gate.sh", "--format", "json"])
        if result.returncode != 0:
            check("rule %s fires on a matching path" % pattern, False,
                  "selector rc=%d for %s: %s"
                  % (result.returncode, sample,
                     (result.stdout + result.stderr).strip()[:160]))
            continue
        payload = json.loads(result.stdout)
        if rule["effect"] == "suites":
            promised = set(rule["suites"])
            delivered = set(payload.get("suites") or [])
            check("rule %s delivers the suites it promises" % pattern,
                  promised <= delivered,
                  "sample %s selected %s, rule promised %s"
                  % (sample, sorted(delivered)[:4], sorted(promised)))
        else:
            check("rule %s names the path it excludes" % pattern,
                  sample in (payload.get("ruledNoImpact") or []),
                  "sample %s is not listed in ruledNoImpact" % sample)

    # Пробелы по краям имени — часть валидного Git-пути, и селектор не имеет
    # права их срезать: `foo ` и `foo` — разные файлы (находка cross-vendor
    # ревьюера).
    spaced = " spaced name.py "
    edges_spaced = {spaced: ["tests/verify_targeted_regression.py"]}
    payload_spaced = selector_module.select([spaced], edges_spaced, [])
    check("a path with edge whitespace is not silently renamed",
          payload_spaced["changed"] == [spaced],
          "selector rewrote %r to %r" % (spaced, payload_spaced["changed"]))

    # Сьют, пришедший ИЗ КАРТЫ, тоже обязан существовать: стейл-ребро на
    # исчезнувший сьют иначе молча расширяло бы выбор пустотой (находка
    # cross-vendor ревьюера).
    stale_edges = {"stale-source.py": ["tests/verify_this_suite_vanished.py"]}
    try:
        selector_module.select(["stale-source.py"], stale_edges, [])
        stale_ok, stale_detail = False, "a map edge to a missing suite was accepted"
    except selector_module.StrictRequired as exc:
        stale_ok = "do not exist" in str(exc)
        stale_detail = str(exc)[:160]
    check("a map edge to a missing suite fails closed", stale_ok, stale_detail)

    # `--` завершает список путей: путь, начинающийся с дефисов, законен.
    dashed = run_selector(["--changed", "--", "--dashed-path.py", "--format", "json"])
    check("`--` lets a dashed path through the CLI",
          dashed.returncode == 3
          and "--dashed-path.py" in (dashed.stdout + dashed.stderr),
          "rc=%d out=%s" % (dashed.returncode,
                            (dashed.stdout + dashed.stderr).strip()[:160]))

    # Испорченная карта не должна выглядеть валидной: ложная секция и
    # нестроковая цель прежде проходили молча (находка cross-vendor ревьюера).
    with tempfile.TemporaryDirectory(prefix="itd-broken-map-") as td:
        for name, document, marker in (
            ("empty-list-section",
             {"declared": [], "generated": {"a.py": ["tests/verify_x.py"]}},
             "not an object"),
            ("non-string-target",
             {"declared": {}, "generated": {"a.py": [{"suite": "x"}]}},
             # Формулировка слилась с проверкой канонической формы (2026-08-24):
             # нестроковая цель и `tests/x/../verify_*.py` — один класс «цель не
             # является каноническим repo-relative путём». Гарантия та же.
             "not a canonical repository-relative path"),
        ):
            broken_map = Path(td) / ("%s.json" % name)
            broken_map.write_text(json.dumps(document), encoding="utf-8")
            try:
                selector_module.load_graph(broken_map)
                broken_ok, broken_detail = False, "a broken map loaded cleanly"
            except selector_module.StrictRequired as exc:
                broken_ok = marker in str(exc)
                broken_detail = str(exc)[:160]
            check("a %s map fails closed" % name, broken_ok, broken_detail)

    # `--changed` без путей — малформленный ввод, а не «взять срез из git».
    empty_changed = run_runall(["--targeted", "--changed"])
    check("--changed without a path is rejected, not reinterpreted",
          empty_changed.returncode == 2
          and "without any path" in empty_changed.stdout,
          "rc=%d stdout: %s"
          % (empty_changed.returncode, empty_changed.stdout.strip()[:160]))

    # Нечитаемое зеркало обязано уводить в strict, а не давать пустое
    # множество: пустое делало проверку outsideMirror вакуумной (находка
    # ревьюера раунда 12, теперь пиннуется мутацией).
    saved_runall = selector_module.RUNALL
    try:
        selector_module.RUNALL = ROOT / "tests" / "no-such-run-all.sh"
        try:
            selector_module.mirror_suites()
            mirror_failed_closed = False
            mirror_detail = "an unreadable mirror returned a set instead of strict"
        except selector_module.StrictRequired as exc:
            mirror_failed_closed = "mirror" in str(exc).lower()
            mirror_detail = str(exc)[:160]
    finally:
        selector_module.RUNALL = saved_runall
    check("an unreadable run-all mirror fails closed",
          mirror_failed_closed, mirror_detail)

    # Читаемое, но неразбираемое зеркало — тоже strict, и его диагностика
    # обязана СТРОИТЬСЯ (в ней была ссылка на несуществующую переменную —
    # ветка падала бы NameError вместо честного отказа; находка cross-vendor
    # ревьюера).
    with tempfile.TemporaryDirectory(prefix="itd-unparsable-mirror-") as td:
        shapeless = Path(td) / "run-all.sh"
        shapeless.write_text("echo no CORE or FULL declaration here\n",
                             encoding="utf-8")
        saved_runall = selector_module.RUNALL
        try:
            selector_module.RUNALL = shapeless
            try:
                selector_module.mirror_suites()
                shapeless_ok, shapeless_detail = False, "an unparsable mirror returned a set"
            except selector_module.StrictRequired as exc:
                shapeless_ok = "declares no suites" in str(exc)
                shapeless_detail = str(exc)[:160]
            except NameError as exc:
                shapeless_ok, shapeless_detail = False, "diagnostic raised NameError: %s" % exc
        finally:
            selector_module.RUNALL = saved_runall
    check("an unparsable run-all mirror fails closed with a buildable message",
          shapeless_ok, shapeless_detail)

    # Override-флаги (--root/--rules) удалены по решению владельца: селектор
    # судит только то дерево, в котором лежит сам. Проверяется именно это —
    # CLI не принимает их, и поверхности для чужого/поддельного дерева нет.
    for flag in ("--root", "--rules"):
        rejected = run_selector(
            ["--changed", "hooks/completion-gate.sh", flag, "/tmp"])
        check("the selector refuses the removed %s override" % flag,
              rejected.returncode == 2
              and "unrecognized arguments" in (rejected.stdout + rejected.stderr),
              "rc=%d out=%s" % (rejected.returncode,
                                (rejected.stdout + rejected.stderr).strip()[:160]))

    bogus = {"pattern": "skills/_shared/*.py", "effect": "no-impact",
             "why": "deliberately false rule used to prove the guard bites"}
    contradicting = [node for node in graph_nodes
                     if selector_module.match_rule(node, [bogus])]
    check("mutation: a false no-impact rule is caught by the same check",
          bool(contradicting),
          "the guard would accept a rule that silences a mapped source path")

    # --- 3e. changed_from_git: срез правки — объединение трёх проб -----------
    # Находка независимого ревьюера: «первая непустая проба выигрывает» на
    # ветке с уже сделанными коммитами возвращала только их и молча теряла
    # новый staged-файл вместе со всеми связанными с ним сьютами. Рабочий
    # режим этого репо (коммиты + WIP поверх) делает сценарий обычным, поэтому
    # он покрывается ЖИВОЙ git-песочницей, а не чтением кода.
    with tempfile.TemporaryDirectory(prefix="itd-changed-probe-") as td:
        sandbox = Path(td) / "repo"
        sandbox.mkdir()
        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": "itd", "GIT_AUTHOR_EMAIL": "itd@example.invalid",
            "GIT_COMMITTER_NAME": "itd", "GIT_COMMITTER_EMAIL": "itd@example.invalid",
        })

        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(["git", "-C", str(sandbox), *args],
                                  capture_output=True, text=True, timeout=120,
                                  env=env)

        git("init", "-q", "-b", "main")
        (sandbox / "base.txt").write_text("base\n", encoding="utf-8")
        git("add", "base.txt")
        git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "base")
        git("branch", "-f", "probe-base", "HEAD")
        (sandbox / "committed.txt").write_text("committed\n", encoding="utf-8")
        git("add", "committed.txt")
        git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "ahead")
        (sandbox / "staged.txt").write_text("staged\n", encoding="utf-8")
        git("add", "staged.txt")
        (sandbox / "base.txt").write_text("base changed\n", encoding="utf-8")

        changed, sources = selector_module.changed_from_git(sandbox, "probe-base")
        check("changed_from_git sees the committed change", "committed.txt" in changed,
              "returned %s" % changed)
        check("changed_from_git sees the staged file on top of commits",
              "staged.txt" in changed,
              "probe priority dropped the newer staged change: %s" % changed)
        check("changed_from_git sees the unstaged edit too",
              "base.txt" in changed, "returned %s" % changed)
        # Untracked-файл обязан попадать в срез: git diff про него молчит,
        # и без отдельной пробы targeted пропускал бы только что созданный
        # сьют (находка cross-vendor ревьюера).
        (sandbox / "brand_new.txt").write_text("new\n", encoding="utf-8")
        changed_new, sources_new = selector_module.changed_from_git(
            sandbox, "probe-base")
        check("changed_from_git sees an untracked new file",
              "brand_new.txt" in changed_new
              and sources_new.get("brand_new.txt") == "untracked",
              "returned %s / %s" % (changed_new, sources_new))

        # Упавшая проба — неизвестное влияние, а не пустой срез. Проверяется
        # на уровне функции: CLI больше не принимает --root, поэтому база
        # подставляется прямо в вызов против песочницы.
        try:
            selector_module.changed_from_git(sandbox, "refs/heads/no-such-base-ref")
            probe_failed_closed = False
            probe_detail = "a failed probe returned a change set instead of strict"
        except selector_module.StrictRequired as exc:
            probe_failed_closed = "probe" in str(exc).lower()
            probe_detail = str(exc)[:160]
        check("a failed git probe is unknown impact, not an empty change set",
              probe_failed_closed, probe_detail)
        check("changed_from_git names the source of every path",
              set(sources) == set(changed) and set(sources.values())
              <= {"committed-ahead-of-base", "staged", "unstaged"},
              "sources: %s" % sources)

    # --- 3f. Правило no-impact не выдаёт зелёное без единого прогона ---------
    result = run_selector(
        ["--changed", ".itd-memory/verification-loop/probe.json", "--format", "json"])
    combined = (result.stdout + result.stderr).lower()
    check("a no-impact-only changeset fails closed with its real reason",
          result.returncode == 3 and "no-impact rule" in combined
          and "zero suites" in combined,
          "rc=%d out=%s" % (result.returncode, combined.strip()[:200]))

    # --- 2. fail-fast: красный прогон не доигрывается ------------------------
    with tempfile.TemporaryDirectory(prefix="itd-failfast-") as td:
        directory = Path(td)
        log_all = directory / "all.log"
        log_fast = directory / "fast.log"
        interpreter_all = fake_python(directory, log_all, "all")
        interpreter_fast = fake_python(directory, log_fast, "fast")
        run_runall(["--quick"], {"PYTHON": str(interpreter_all)})
        result_fast = run_runall(
            ["--quick", "--fail-fast"], {"PYTHON": str(interpreter_fast)})
        runs_all = len(log_all.read_text(encoding="utf-8").splitlines()) \
            if log_all.exists() else 0
        runs_fast = len(log_fast.read_text(encoding="utf-8").splitlines()) \
            if log_fast.exists() else 0
        check("baseline: a red run without --fail-fast plays every suite",
              runs_all >= 10, "only %d suites executed" % runs_all)
        check("--fail-fast stops on the first red suite",
              0 < runs_fast <= 2,
              "executed %d suites (baseline %d)" % (runs_fast, runs_all))
        check("--fail-fast still exits non-zero",
              result_fast.returncode != 0,
              "rc=%d" % result_fast.returncode)
        check("--fail-fast names where it stopped",
              "stopped-early" in result_fast.stdout,
              "stdout tail: %s" % result_fast.stdout.strip()[-200:])
        # Отсутствующий файл сьюта — тоже красный; прежде эта ветка возвращала
        # управление без stopped_early, и прогон доигрывался (находка
        # cross-vendor ревьюера). Проверяется поведением: подставной CORE с
        # несуществующим первым сьютом.
        missing_log = directory / "missing.log"
        missing_interpreter = fake_python(directory, missing_log, "missing",
                                          exit_code=0)
        script = (RUNALL.read_text(encoding="utf-8")
                  .replace('CORE="meta_review ',
                           'CORE="verify_this_suite_does_not_exist meta_review ', 1))
        alt = runall_copy(script, directory / "run-all-missing.sh")
        missing_run = subprocess.run(
            ["sh", str(alt), "--quick", "--fail-fast"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300,
            env={**os.environ, "PYTHON": str(missing_interpreter)})
        executed = len(missing_log.read_text(encoding="utf-8").splitlines()) \
            if missing_log.exists() else 0
        # Хвостовые проверки полного профиля тоже пиннуются поведением:
        # без этого правка run_tail или его вызовов прошла бы незамеченной
        # (находка ревьюера раунда 8). Стабы падают по очереди; под
        # --fail-fast обязана исполниться ровно первая.
        tail_log = directory / "tail.log"
        stub_dir = directory / "stubs"
        stub_dir.mkdir(exist_ok=True)
        tail_script = (RUNALL.read_text(encoding="utf-8")
                       .replace('"$PY" scripts/verify_skill_profiles.py',
                                'sh "%s/tail_stub.sh" skill_profiles' % stub_dir.as_posix())
                       .replace('bash scripts/verify-sync-to-active.sh',
                                'sh "%s/tail_stub.sh" sync_verify' % stub_dir.as_posix())
                       .replace('"$PY" tests/verify_snapshot.py --all',
                                'sh "%s/tail_stub.sh" snapshot' % stub_dir.as_posix()))
        (stub_dir / "tail_stub.sh").write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$1" >> "' + tail_log.as_posix() + '"\n'
            "exit 1\n", encoding="utf-8")
        tail_runner = runall_copy(tail_script, directory / "run-all-tail.sh")
        tail_interpreter = fake_python(directory, directory / "tail-py.log",
                                       "tail", exit_code=0)
        tail_run = subprocess.run(
            ["sh", str(tail_runner), "--fail-fast"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHON": str(tail_interpreter)})
        tail_names = tail_log.read_text(encoding="utf-8").split() \
            if tail_log.exists() else []
        # targeted тоже обязан гонять хвостовые проверки: без них правка
        # scripts/verify_skill_profiles.py в targeted-режиме не проверялась бы
        # ничем (находка cross-vendor ревьюера).
        targeted_tail_log = directory / "targeted-tail.log"
        targeted_stub = stub_dir / "targeted_stub.sh"
        targeted_stub.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$1" >> "' + targeted_tail_log.as_posix() + '"\n'
            "exit 0\n", encoding="utf-8")
        targeted_script = (RUNALL.read_text(encoding="utf-8")
                           .replace('"$PY" scripts/verify_skill_profiles.py',
                                    'sh "%s" skill_profiles' % targeted_stub.as_posix())
                           .replace('bash scripts/verify-sync-to-active.sh',
                                    'sh "%s" sync_verify' % targeted_stub.as_posix())
                           .replace('"$PY" tests/verify_snapshot.py --all',
                                    'sh "%s" snapshot' % targeted_stub.as_posix()))
        targeted_runner = runall_copy(targeted_script,
                                      directory / "run-all-targeted-tail.sh")
        targeted_interpreter = fake_python(
            directory, directory / "targeted-py.log", "targetedtail",
            exit_code=0, delegate="itd_regression_select.py")
        subprocess.run(
            ["sh", str(targeted_runner), "--targeted",
             "--changed", "hooks/completion-gate.sh"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHON": str(targeted_interpreter)})
        targeted_tail = sorted(set(
            targeted_tail_log.read_text(encoding="utf-8").split()
            if targeted_tail_log.exists() else []))
        check("a targeted run still executes the full-profile tail checks",
              targeted_tail == ["skill_profiles", "snapshot", "sync_verify"],
              "tail checks executed in targeted mode: %s" % targeted_tail)

        check("--fail-fast covers the full-profile tail checks",
              tail_names == ["skill_profiles"],
              "tail checks executed: %s (stdout tail: %s)"
              % (tail_names, tail_run.stdout.strip()[-160:]))

        # Класс BLOCKED проверяется ПРОГОНОМ, а не подстроками исходника:
        # копия скрипта указывает на несуществующий host-owned вход (находка
        # cross-vendor ревьюера).
        blocked_interpreter = fake_python(directory, directory / "blocked.log",
                                          "blocked", exit_code=0)
        blocked_script = RUNALL.read_text(encoding="utf-8").replace(
            'host_pin=".itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256"',
            'host_pin=".itd-memory/host-inputs/NO_SUCH_HOST_INPUT.sha256"')
        blocked_runner = runall_copy(blocked_script, directory / "run-all-blocked.sh")
        blocked_run = subprocess.run(
            ["sh", str(blocked_runner), "--quick"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHON": str(blocked_interpreter)})
        check("a missing host input is reported as BLOCKED, with a non-zero exit",
              "BLOCKED verify_independent_review_efficacy" in blocked_run.stdout
              and "blocked:" in blocked_run.stdout
              and blocked_run.returncode != 0
              and "FAIL verify_independent_review_efficacy" not in blocked_run.stdout,
              "rc=%d stdout tail: %s"
              % (blocked_run.returncode, blocked_run.stdout.strip()[-220:]))

        check("--fail-fast stops on a missing suite file too",
              executed == 0 and "stopped-early" in missing_run.stdout,
              "executed %d suites after a missing file; stdout tail: %s"
              % (executed, missing_run.stdout.strip()[-160:]))

    # --- 1. host-owned вход: отдельный класс, WHY+FIX, не false-green --------
    body = RUNALL.read_text(encoding="utf-8").partition("run_py() {")[2] \
        .partition("\n}")[0]
    check("missing host input is classified, not reported as a suite failure",
          "BLOCKED" in body and "fails=\"$fails $t\"" not in
          body.split("host_pin")[-1].split("esac")[0],
          "run_py still counts a missing host input as a candidate regression")
    check("missing host input prints the exact FIX",
          "--input" in body,
          "run_py does not tell the caller how to declare the host input")
    # Проверяется ИМЕННО итоговое условие выхода, а не наличие слова "exit 1"
    # где-нибудь в файле: посторонний exit удовлетворял прежнюю проверку
    # (находка cross-vendor ревьюера).
    runall_text = RUNALL.read_text(encoding="utf-8")
    check("blocked input keeps the run non-zero (no false green)",
          re.search(r'\[ -z "\$fails" \]\s*&&\s*\[ -z "\$blocked" \]\s*\|\|\s*exit 1',
                    runall_text) is not None,
          "the final exit condition does not fail closed on a blocked input")

    # --- targeted-режим самого run-all --------------------------------------
    text = RUNALL.read_text(encoding="utf-8")
    check("run-all exposes --targeted", "--targeted" in text)
    check("run-all delegates selection to the selector",
          "itd_regression_select.py" in text,
          "targeted mode must reuse the audited map, not a second selector")
    check("this guard is wired into run-all.sh",
          "verify_targeted_regression" in text)
    check("the full run states how much of the suite set the mirror covers",
          "MIRROR-COVERAGE" in text,
          "'DONE fails:none' must not read wider than the mirror actually is")
    # Строка покрытия проверяется ПОВЕДЕНИЕМ, а не совпадением строки кода:
    # прежняя проверка прошла бы и на рефакторинге, который сохранил текст
    # условия, но сломал гарантию (находка ревьюера, LPD-003-1).
    with tempfile.TemporaryDirectory(prefix="itd-coverage-") as td:
        directory = Path(td)
        interpreter = fake_python(directory, directory / "coverage.log", "cov",
                                  delegate="itd_regression_select.py")
        fallback = run_runall(
            ["--targeted", "--quick", "--changed", "no/such/path/in/the/map.py"],
            {"PYTHON": str(interpreter)})
        bounded = run_runall(
            ["--targeted", "--quick", "--changed", "scripts/itd_regression_select.py"],
            {"PYTHON": str(interpreter)})
        check("strict fallback runs the mirror and says how much it covers",
              "TARGETED -> STRICT" in fallback.stdout
              and "MIRROR-COVERAGE" in fallback.stdout,
              "fallback stdout tail: %s" % fallback.stdout.strip()[-200:])
        # Названный профиль обязан совпасть с прогнанным: под --quick это
        # CORE, а не полное зеркало (находка cross-vendor ревьюера).
        check("strict fallback names the profile it actually runs",
              "quick profile" in fallback.stdout
              and "full mirror (nothing is skipped)" not in fallback.stdout,
              "fallback under --quick claimed the full mirror: %s"
              % fallback.stdout.strip()[-200:])
        # Главная гарантия strict: набор НЕ сужается. Названный профиль
        # проверяется выше, но названия мало — сравниваются РЕАЛЬНО запущенные
        # сьюты обычного `--quick` и strict-отката под `--quick`. Они обязаны
        # совпасть: strict означает «не сужать запрошенный профиль», а не
        # «поднять его до полного зеркала» (уточнение после находки
        # cross-vendor ревьюера о расхождении текста критерия и кода).
        plain_log = directory / "plain.log"
        plain_py = fake_python(directory, plain_log, "plain",
                               delegate="itd_regression_select.py")
        run_runall(["--quick"], {"PYTHON": str(plain_py)})
        # Отдельный лог: `coverage.log` накапливает ОБА прогона этого блока
        # (strict-откат и связанный), и сравнение с ним завышало набор на один
        # сьют. Замер обязан видеть ровно один прогон.
        strict_log = directory / "strict-only.log"
        strict_py = fake_python(directory, strict_log, "strictonly",
                                delegate="itd_regression_select.py")
        run_runall(["--targeted", "--quick", "--changed", "no/such/path/in/the/map.py"],
                   {"PYTHON": str(strict_py)})

        def suites_from(log_path: Path) -> set[str]:
            if not log_path.is_file():
                return set()
            names = set()
            for line in log_path.read_text(encoding="utf-8").splitlines():
                for token in line.split():
                    if token.startswith("tests/verify_") and token.endswith(".py"):
                        names.add(Path(token).stem)
            return names

        strict_suites = suites_from(strict_log)
        plain_suites = suites_from(plain_log)
        check("strict never narrows the profile that was requested",
              bool(plain_suites) and strict_suites == plain_suites,
              "quick=%d strict-fallback=%d; only-in-quick=%s"
              % (len(plain_suites), len(strict_suites),
                 sorted(plain_suites - strict_suites)[:5]))

        check("a bounded targeted run does not claim mirror coverage",
              "MIRROR-COVERAGE" not in bounded.stdout,
              "a partial run must not print the full-mirror coverage line")
        # Проверяется ЧИСЛО, а не наличие строки: --quick исполняет только
        # CORE, и сумма CORE+FULL завышала бы покрытие — прежний тест проходил
        # по этому же пути, но счётчик не сверял (находка ревьюера, раунд 4).
        # Считаются ТОЛЬКО verify_-сьюты: знаменатель строки — tests/verify_*.py,
        # и meta_review в него не входит (находка ревьюера, раунд 5).
        core_count = len(re.findall(r"\bverify_[a-z0-9_]+",
                                    re.search(r'^CORE="([^"]*)"$',
                                              text_for_counts,
                                              flags=re.MULTILINE).group(1)))
        quick_line = next((line for line in fallback.stdout.splitlines()
                           if line.startswith("MIRROR-COVERAGE")), "")
        check("the quick profile counts only the suites it actually ran",
              ("(quick profile)" in quick_line
               and quick_line.split()[1] == str(core_count)),
              "quick run claims %r while CORE holds %d suites"
              % (quick_line, core_count))
        full_run = run_runall([], {"PYTHON": str(interpreter)})
        full_line = next((line for line in full_run.stdout.splitlines()
                          if line.startswith("MIRROR-COVERAGE")), "")
        mirror_verify = {name for name in universe if name.startswith("verify_")}
        check("the full mirror counts CORE plus FULL",
              ("(full mirror)" in full_line
               and full_line.split()[1] == str(len(mirror_verify))),
              "full run claims %r while the mirror holds %d verify_ suites"
              % (full_line, len(mirror_verify)))
        check("numerator and denominator count the same set",
              full_line.split()[3] == str(
                  len(list((ROOT / "tests").glob("verify_*.py")))),
              "denominator in %r is not the count of tests/verify_*.py" % full_line)

    # --- 9. Периметр: селектор судит только ЭТОТ репозиторий ----------------
    # Решение владельца 2026-08-24 (`.itd/DECISIONS.md`): ни один публичный
    # вход не называет читаемый селектором файл. Это закрывает класс находок
    # «чужая карта/чужое дерево сужает прогон» целиком, а не по одной за
    # заход. Проверяется ПОВЕДЕНИЕМ (флаг отвергается), а не отсутствием
    # строки в исходнике: строку можно вернуть под другим именем.
    perimeter = _load_selector_module()
    for flag in ("--graph", "--root", "--rules", "--patterns", "--mirror"):
        rejected = run_selector(
            [flag, str(GRAPH), "--changed", "scripts/itd_regression_select.py"])
        check("public input %s cannot name a file the selector reads" % flag,
              rejected.returncode == 2
              and "unrecognized arguments" in rejected.stderr,
              "rc=%d err=%s" % (rejected.returncode,
                                rejected.stderr.strip()[-160:]))
    check("the selector resolves its map from its own location",
          perimeter.DEFAULT_GRAPH == ROOT / ".itd" / "IMPACT_GRAPH.json"
          and perimeter.DEFAULT_PATTERNS == ROOT / ".itd" / "IMPACT_PATTERNS.json"
          and perimeter.RUNALL == RUNALL,
          "map/rules/mirror must be derived from ROOT, not from a caller")

    # --- 9a. Целостность карты: неканоническое ребро обязано уводить в strict
    # `tests/x/../verify_quick_regression.py` проходил ВСЕ прежние проверки:
    # `is_suite` считал его сьютом, а существование сверялось по basename —
    # прогон сужался по битому ребру и выглядел законным.
    with tempfile.TemporaryDirectory(prefix="itd-canonical-") as td:
        corrupt_dir = Path(td)
        base = json.loads(GRAPH.read_text(encoding="utf-8"))
        corruptions = {
            "traversal target": ("generated", "changed.py",
                                 ["tests/x/../verify_quick_regression.py"]),
            "absolute target": ("generated", "changed.py",
                                ["/tests/verify_quick_regression.py"]),
            "backslash target": ("generated", "changed.py",
                                 ["tests\\verify_quick_regression.py"]),
            "dot-segment target": ("generated", "changed.py",
                                   ["tests/./verify_quick_regression.py"]),
        }
        for label, (section, source, targets) in corruptions.items():
            document = json.loads(json.dumps(base))
            document[section][source] = targets
            path = corrupt_dir / ("%s.json" % label.replace(" ", "-"))
            path.write_text(json.dumps(document), encoding="utf-8")
            try:
                perimeter.load_graph(path)
                rejected_map = False
            except perimeter.StrictRequired:
                rejected_map = True
            check("a %s in the map fails closed" % label, rejected_map,
                  "the map bounded a run through a non-canonical edge")
        # Неканонический УЗЕЛ так же опасен: он никогда не совпадёт с
        # изменённым путём, поэтому его сьюты молча выпадут из выбора.
        document = json.loads(json.dumps(base))
        document["generated"]["tests/../scripts/itd_regression_select.py"] = [
            "tests/verify_targeted_regression.py"]
        path = corrupt_dir / "node.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        try:
            perimeter.load_graph(path)
            rejected_node = False
        except perimeter.StrictRequired:
            rejected_node = True
        check("a non-canonical node in the map fails closed", rejected_node,
              "a node that cannot match a changed path silently loses its suites")
        # Обратная сторона: настоящая карта репозитория обязана проходить —
        # иначе проверка выше «зелёная» просто потому, что запрещает всё.
        try:
            perimeter.load_graph(GRAPH)
            live_map_ok = True
        except perimeter.StrictRequired as exc:
            live_map_ok = False
            live_detail = str(exc)
        check("the repository's own map still loads under the canonical rule",
              live_map_ok,
              "" if live_map_ok else live_detail[:200])

    # --- 9b. Путь, начинающийся с дефисов, доходит до селектора ЧЕРЕЗ run-all
    # Находка закрывалась в r29 «по селектору» и осталась открытой в оболочке:
    # внутренний цикл съедал `--` и возвращал остаток внешнему разбору опций,
    # который отвечал «unknown flag». Поэтому проверка идёт тем же путём,
    # каким дефект найдёт независимый ревьюер — через run-all.sh.
    with tempfile.TemporaryDirectory(prefix="itd-dashed-") as td:
        directory = Path(td)
        interpreter = fake_python(directory, directory / "dashed.log", "dash",
                                  delegate="itd_regression_select.py")
        dashed = run_runall(["--targeted", "--quick", "--changed", "--",
                             "--dashed-path.py"], {"PYTHON": str(interpreter)})
        combined = dashed.stdout + dashed.stderr
        check("a changed path starting with dashes reaches the selector",
              "--dashed-path.py" in combined,
              "run-all never passed the operand on: %s" % combined.strip()[:200])
        check("such a path is not reparsed as a run-all flag",
              "unknown flag" not in combined
              and "--changed was given without any path" not in combined,
              "run-all rejected a valid operand: %s" % combined.strip()[:200])
        # Позитивная сторона: после `--` обычный путь по-прежнему сужает
        # прогон, а не уводит в strict — иначе проверка выше проходила бы на
        # реализации, которая просто ломает `--changed` целиком.
        after_dashdash = run_runall(
            ["--targeted", "--quick", "--changed", "--",
             "scripts/itd_regression_select.py"], {"PYTHON": str(interpreter)})
        check("a normal path after `--` still bounds the run",
              "TARGETED:" in after_dashdash.stdout
              and "TARGETED -> STRICT" not in after_dashdash.stdout,
              "stdout tail: %s" % after_dashdash.stdout.strip()[-200:])

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
