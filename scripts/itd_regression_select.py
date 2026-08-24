#!/usr/bin/env python3
"""itd_regression_select.py — targeted-профиль регрессии по карте воздействия.

Замер G0: полный `tests/run-all.sh` — 82% машинного слоя, и он же объявлен
входом по умолчанию для ЛЮБОЙ правки, включая однофайловую. Этот селектор
отвечает на один вопрос: какие сьюты карта связывает с изменёнными файлами.

Границы гарантии объявлены честно:

* **Полнота.** Отбор — транзитивное замыкание по `.itd/IMPACT_GRAPH.json`,
  отфильтрованное до `tests/verify_*.py`. Карта уже судится машинно операцией
  `impact-audit` (`skills/_shared/itd_verification_profiles.py`): каждый сьют
  достижим, каждый `skills/_shared/*.py` и `hooks/*.sh` имеет владеющий сьют.
  Полнота ОТБОРА не сильнее полноты КАРТЫ — селектор не выводит рёбра сам.
* **Fail-closed.** Изменённый путь, которого нет в карте как узла и который не
  является сьютом, уводит в strict, а не молча сужает набор. Strict — это
  «не сужать запрошенный профиль», а не «поднять его до полного зеркала»:
  под `--quick` целиком прогоняется CORE, и run-all называет тот профиль,
  который реально будет прогнан.
  Тот же исход при отсутствующей/битой карте.
* **Не гейт.** Селектор ничего не «проходит»: он печатает выбор и объяснение.
  Приёмка остаётся за Verification Loop.
* **Периметр.** Селектор судит ТОЛЬКО тот репозиторий, в котором лежит сам:
  карта, правила и зеркало берутся от `ROOT` (расположение этого файла), и ни
  один публичный флаг не называет читаемый файл. Единственный внешний вход —
  список изменённых путей. Решение и его цена — `.itd/DECISIONS.md`,
  запись 2026-08-24.

Коды выхода: 0 — выбор напечатан; 3 — strict required (запрошенный профиль
целиком, без сужения);
2 — ошибка входа. Stdlib-only, кросс-платформенный.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / ".itd" / "IMPACT_GRAPH.json"
RUNALL = ROOT / "tests" / "run-all.sh"
DEFAULT_PATTERNS = ROOT / ".itd" / "IMPACT_PATTERNS.json"

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_STRICT = 3


class StrictRequired(Exception):
    """The bounded selection cannot be trusted; run the full mirror."""

    def __init__(self, why: str, fix: str) -> None:
        super().__init__(why)
        self.why = why
        self.fix = fix


def _is_canonical(value: object) -> bool:
    """Путь в карте обязан быть каноническим repo-relative POSIX-путём.

    Карта — вход ДОВЕРЕННЫЙ (репозиторный, судится `impact-audit`), но не
    непроверяемый: испорченный генератор или неудачный мерж могут записать
    `tests/x/../verify_quick_regression.py`. Такое ребро `is_suite`
    классифицирует как сьют, а проверка существования смотрит только на
    basename — прогон сузился бы по НЕканоническому ребру и выглядел бы
    законным (находка cross-vendor ревьюера). Это инвариант целостности
    карты, а не защита периметра: чужих карт у селектора больше нет.
    """
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip() or "\\" in value or value.startswith("/"):
        return False
    if ":" in value.split("/")[0]:  # C:/... — не repo-relative
        return False
    return all(part and part not in (".", "..") for part in value.split("/"))


def load_graph(path: Path) -> dict[str, list[str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StrictRequired(
            "impact map %s is unreadable: %s" % (path, exc),
            "Regenerate it with `python3 tests/build_impact_graph.py` and retry, "
            "or run the full mirror `bash tests/run-all.sh`.",
        ) from exc
    if not isinstance(document, dict):
        raise StrictRequired(
            "impact map %s is not a JSON object" % path,
            "Regenerate the map; do not narrow the run against a malformed one.",
        )
    edges: dict[str, list[str]] = {}
    for section in ("declared", "generated"):
        # `or {}` глотал ложные значения: секция `[]` или `""` выглядела как
        # отсутствующая и проходила валидацию (находка cross-vendor ревьюера).
        block = document[section] if section in document else {}
        if block is None:
            block = {}
        if not isinstance(block, dict):
            raise StrictRequired(
                "impact map section %r is not an object" % section,
                "Regenerate the map with the generator that owns its schema.",
            )
        for source, targets in block.items():
            if not _is_canonical(source):
                raise StrictRequired(
                    "impact map node %r is not a canonical repository-relative "
                    "path" % (source,),
                    "Regenerate the map with `python3 tests/build_impact_graph.py`; "
                    "a node that is not canonical cannot be matched against the "
                    "changed paths, so the run it bounds proves nothing.",
                )
            if not isinstance(targets, list):
                raise StrictRequired(
                    "impact map edge list for %r is not a list" % source,
                    "Regenerate the map; a malformed edge cannot be walked.",
                )
            bucket = edges.setdefault(source, [])
            for target in targets:
                if not _is_canonical(target):
                    # Нестроковая или неканоническая цель прежде проходила:
                    # первая отбрасывалась молча (испорченная карта выглядела
                    # валидной и теряла рёбра), вторая — `tests/x/../verify_*.py`
                    # — доходила до прогона, потому что существование сьюта
                    # проверялось по basename.
                    raise StrictRequired(
                        "impact map edge %r -> %r is not a canonical "
                        "repository-relative path" % (source, target),
                        "Regenerate the map with its generator; a map with "
                        "malformed edges cannot bound a run.",
                    )
                if target not in bucket:
                    bucket.append(target)
    if not edges:
        raise StrictRequired(
            "impact map %s declares no edges" % path,
            "An empty map cannot bound a run; use the full mirror.",
        )
    return edges


def changed_from_git(root: Path, base: str) -> tuple[list[str], dict[str, str]]:
    probes = (
        ("committed-ahead-of-base",
         ["git", "-C", str(root), "diff", "--name-only", base + "...HEAD"]),
        ("staged", ["git", "-C", str(root), "diff", "--name-only", "--cached"]),
        ("unstaged", ["git", "-C", str(root), "diff", "--name-only"]),
        # Новый, ещё не добавленный в индекс файл не виден ни одной из
        # diff-проб: `git diff` про untracked молчит. Без этой пробы targeted
        # пропускал бы только что созданный сьют или скрипт (находка
        # cross-vendor ревьюера).
        ("untracked", ["git", "-C", str(root), "ls-files", "--others",
                       "--exclude-standard"]),
    )
    # Все четыре пробы объединяются НАМЕРЕННО. Ветка с уже сделанными коммитами
    # плюс новые staged/unstaged правки — обычный режим работы в этом репо;
    # «первая непустая проба выигрывает» отдавала бы только коммиты и молча
    # теряла новый файл вместе со всеми связанными с ним сьютами (находка
    # независимого ревьюера, LPD-003-1). Расширение набора — безопасная
    # сторона, и оно НЕ молчаливое: источник каждого пути возвращается в
    # ``changedSources``.
    changed: list[str] = []
    sources: dict[str, str] = {}
    for label, argv in probes:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            # Упавшая проба — НЕ пустой ответ: типичный случай, когда база
            # (`origin/main`) недостижима в изолированном чекауте. Молчаливое
            # продолжение сузило бы срез до staged/unstaged и потеряло всё,
            # что лежит в коммитах ветки (находка cross-vendor ревьюера).
            raise StrictRequired(
                "git probe %s failed (rc=%d): %s"
                % (label, result.returncode, (result.stderr or "").strip()[:200]),
                "Fetch the base ref or pass --changed explicitly; a failed probe "
                "is unknown impact, never an empty change set.",
            )
        for line in result.stdout.splitlines():
            # Только перевод строки: `.strip()` калечил валидные Git-имена с
            # ведущим или хвостовым пробелом — путь превращался в другой путь
            # (находка cross-vendor ревьюера).
            value = line.rstrip("\r\n")
            if not value:
                continue
            if value not in changed:
                changed.append(value)
                sources[value] = label
    if not changed:
        raise StrictRequired(
            "no changed paths could be derived from Git",
            "Pass --changed <paths> explicitly, or run the full mirror.",
        )
    return changed, sources


def mirror_suites() -> set[str]:
    """Имена сьютов, которые гоняет полное зеркало run-all.sh этого дерева.

    Карта покрывает ВСЕ tests/verify_*.py, зеркало — только то, что гоняет CI.
    Разница не безобидна: сьют вне зеркала сегодня не гоняет никто. Targeted
    его НАЗЫВАЕТ (`outsideMirror`), но не гоняет — безусловный прогон дал бы
    false-red, тихий пропуск — false-green. Нечитаемое зеркало — не пустое
    множество, а strict: пустое делало бы проверку вакуумной.
    """
    try:
        text = RUNALL.read_text(encoding="utf-8")
    except OSError as exc:
        raise StrictRequired(
            "run-all mirror is unreadable at %s: %s" % (RUNALL, exc),
            "Restore tests/run-all.sh; an unknown mirror cannot bound a run.",
        ) from exc
    names: set[str] = set()
    for key in ("CORE", "FULL"):
        match = re.search(r'^%s="((?:[^"\\]|\\.)*)"$' % key, text,
                          flags=re.MULTILINE | re.DOTALL)
        if match:
            names.update(match.group(1).replace("\\\n", " ").split())
    if not names:
        # Зеркало прочиталось, но его форма больше не разбирается: пустое
        # множество здесь означало бы «всё внутри зеркала» и делало проверку
        # outsideMirror вакуумной (находка cross-vendor ревьюера).
        raise StrictRequired(
            "run-all mirror at %s declares no suites in CORE/FULL" % RUNALL,
            "The mirror's shape changed and can no longer be parsed; fix the "
            "parser or run the full mirror. An unparsed mirror is unknown "
            "coverage, not full coverage.",
        )
    return names


def load_patterns(path: Path) -> list[dict[str, object]]:
    """Правила для путей, которые НЕЛЬЗЯ перечислить узлами.

    Контракты юнитов, записи live-прогонов, квитанции — создаются на каждый
    юнит/прогон, поэтому статическим узлом карты не станут никогда. Без правил
    любая реальная правка тащит за собой такой путь и уводит маршрут в strict,
    то есть targeted не применяется НИКОГДА (замер на 20 последних коммитах:
    2 из 3 юнитов). Обоснованность правил проверяется машинно оракулом
    tests/verify_targeted_regression.py против сгенерированной карты.
    """
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StrictRequired(
            "impact rules %s are unreadable: %s" % (path, exc),
            "Repair the rules file or run the full mirror.",
        ) from exc
    # Корень обязан быть объектом — ровно как в `load_graph`. Без этой
    # проверки `document.get()` на корне-массиве/строке/null давал
    # AttributeError и exit 1 вместо strict с WHY+FIX: нечитаемые правила
    # выглядели бы как поломка инструмента, а не как «сузить нельзя»
    # (находка cross-vendor ревьюера).
    if not isinstance(document, dict):
        raise StrictRequired(
            "impact rules %s are not a JSON object" % path,
            "Restore the rules file schema, or run the full mirror; rules that "
            "cannot be read are unknown impact, not an empty rule set.",
        )
    rules = document.get("rules")
    if not isinstance(rules, list):
        raise StrictRequired(
            "impact rules %s declare no rule list" % path,
            "Restore the rules file schema, or run the full mirror.",
        )
    for rule in rules:
        if (not isinstance(rule, dict)
                or not isinstance(rule.get("pattern"), str)
                or rule.get("effect") not in {"suites", "no-impact"}
                or not isinstance(rule.get("why"), str) or not rule["why"]
                or (rule["effect"] == "suites"
                    and not (isinstance(rule.get("suites"), list)
                             and rule["suites"]))):
            raise StrictRequired(
                "impact rule is malformed: %r" % (rule,),
                "Every rule needs pattern, effect (suites|no-impact), why, and "
                "a non-empty suites list for effect=suites.",
            )
        if rule["effect"] == "suites":
            # Имя сьюта проверяется против дерева: правило, называющее
            # несуществующий или переименованный сьют, молча расширяло бы
            # выбор пустотой и выглядело бы как покрытие (находка
            # cross-vendor ревьюера).
            # Сьюты ищутся в ЭТОМ дереве: селектор судит только тот
            # репозиторий, в котором лежит сам (override-флагов нет по
            # решению владельца — они порождали класс дефектов вокруг
            # чужих/поддельных деревьев, недостижимый с автоматического
            # маршрута и никем не используемый).
            suites_root = ROOT / "tests"
            unknown = [name for name in rule["suites"]
                       if not isinstance(name, str)
                       or not (suites_root / ("%s.py" % name)).is_file()]
            if unknown:
                raise StrictRequired(
                    "impact rule %r names suites that do not exist: %s"
                    % (rule["pattern"], ", ".join(map(str, unknown))),
                    "Point the rule at real tests/<suite>.py files, or drop it; "
                    "a rule naming a missing suite proves nothing.",
                )
            # Сьют вне зеркала правило назвать может, но тогда targeted его НЕ
            # прогонит (он уйдёт в outsideMirror), и правило обещало бы
            # покрытие, которого нет (находка cross-vendor ревьюера).
            outside_mirror = [name for name in rule["suites"]
                              if name not in mirror_suites()]
            if outside_mirror:
                raise StrictRequired(
                    "impact rule %r names suites the mirror never runs: %s"
                    % (rule["pattern"], ", ".join(outside_mirror)),
                    "Name suites the mirror can run, or close the debt that "
                    "keeps them outside it; a rule pointing outside the mirror "
                    "promises coverage the targeted run will not deliver.",
                )
    return rules


def _segment_match(path: str, pattern: str) -> bool:
    """Сопоставление по СЕГМЕНТАМ пути: `*` внутри одного, `**` — через любое их число.

    Ручные эвристики здесь дважды дали дефект (`fnmatch` пропускал `/` через
    `*`; префиксная проверка вокруг `**` матчила по подстроке, из-за чего
    `a/**/b.md` ловил `a/xb.md`). Поэтому используется обычный рекурсивный
    разбор списков сегментов — тот же приём, что в стандартных glob-движках:
    `**` съедает ноль или более СЕГМЕНТОВ ЦЕЛИКОМ, остальные сегменты
    сравниваются `fnmatch`-ом по отдельности и границу `/` не пересекают.
    """
    path_parts = [part for part in path.split("/") if part not in ("", ".")]
    pattern_parts = [part for part in pattern.split("/") if part not in ("", ".")]

    seen: set[tuple[int, int]] = set()

    def walk(pi: int, si: int) -> bool:
        # Мемоизация по (позиция в шаблоне, позиция в пути): без неё шаблон с
        # несколькими `**` уходит в комбинаторный перебор (замер ревьюера:
        # 12 токенов против 20 сегментов не завершались за 120 с).
        if (pi, si) in seen:
            return False
        seen.add((pi, si))
        while pi < len(pattern_parts):
            token = pattern_parts[pi]
            if token == "**":
                if pi + 1 == len(pattern_parts):
                    return True
                for skip in range(si, len(path_parts) + 1):
                    if walk(pi + 1, skip):
                        return True
                return False
            if si >= len(path_parts):
                return False
            if not fnmatch.fnmatch(path_parts[si], token):
                return False
            pi += 1
            si += 1
        return si == len(path_parts)

    return walk(0, 0)


def match_rule(path: str, rules: list[dict[str, object]]) -> dict[str, object] | None:
    # Единственный источник истины — сегментный матчер. Прежние префиксные
    # эвристики остались тут после переписывания и расходились с ним:
    # `a/*/**/c.md` ловил `a/b`, потому что fallback игнорировал всё, что
    # стоит после `**` (находка cross-vendor ревьюера).
    for rule in rules:
        if _segment_match(path, str(rule["pattern"])):
            return rule
    return None


def is_suite(node: str) -> bool:
    return (node.startswith("tests/") and node.endswith(".py")
            and Path(node).name.startswith("verify_"))


def select(changed: list[str], edges: dict[str, list[str]],
           rules: list[dict[str, object]] | None = None) -> dict[str, object]:
    rules = rules or []
    if not changed:
        raise StrictRequired(
            "changed must be a non-empty list of repository-relative paths",
            "Name the changed files explicitly before narrowing the run.",
        )
    normalized: list[str] = []
    for raw in changed:
        value = raw.replace("\\", "/").rstrip("\r\n")
        if not value or value.startswith("/") or ".." in Path(value).parts:
            raise StrictRequired(
                "changed path %r is not a normalized repository-relative path" % raw,
                "Pass paths relative to the repository root.",
            )
        if value not in normalized:
            normalized.append(value)

    ruled_suites: list[str] = []
    ruled_out: list[str] = []
    unmapped: list[str] = []
    for value in normalized:
        if value in edges or is_suite(value):
            continue
        rule = match_rule(value, rules)
        if rule is None:
            unmapped.append(value)
        elif rule["effect"] == "suites":
            for name in rule["suites"]:  # type: ignore[union-attr]
                if name not in ruled_suites:
                    ruled_suites.append(str(name))
        else:
            ruled_out.append(value)
    if unmapped:
        raise StrictRequired(
            "changed paths are absent from the impact map: %s" % ", ".join(unmapped),
            "Regenerate the map (`python3 tests/build_impact_graph.py`) so the "
            "path owns its suites, or run the full mirror `bash tests/run-all.sh`. "
            "An unmapped path is unknown impact, never zero impact.",
        )

    seen: set[str] = set()
    order: list[str] = []
    queue = list(normalized)
    while queue:
        node = queue.pop(0)
        if node in seen:
            continue
        seen.add(node)
        order.append(node)
        queue.extend(edges.get(node, []))

    suites = sorted({Path(node).stem for node in order if is_suite(node)}
                    | set(ruled_suites))
    if not suites:
        if ruled_out and len(ruled_out) == len(normalized):
            raise StrictRequired(
                "every changed path is explained by a no-impact rule, so the "
                "bounded run would execute zero suites: %s" % ", ".join(ruled_out),
                "A green result with no suite executed is not evidence. Run the "
                "full mirror `bash tests/run-all.sh`, or, if such a change truly "
                "needs no regression, say so in the unit's own record rather "
                "than by an empty run.",
            )
        raise StrictRequired(
            "the map links the changed paths to no suite at all",
            "Zero suites is unknown impact, not proven safety: regenerate the "
            "map or run the full mirror.",
        )
    # Сьюты, пришедшие ИЗ КАРТЫ, проверяются так же строго, как названные
    # правилами: стейл-ребро на исчезнувший сьют иначе молча расширяло бы
    # выбор пустотой (находка cross-vendor ревьюера).
    missing_suites = [name for name in suites
                      if not (ROOT / "tests" / ("%s.py" % name)).is_file()]
    if missing_suites:
        raise StrictRequired(
            "impact map links these paths to suites that do not exist: %s"
            % ", ".join(missing_suites),
            "Regenerate the map (`python3 tests/build_impact_graph.py`); an edge "
            "to a missing suite proves nothing.",
        )
    mirror = mirror_suites()
    outside = sorted(name for name in suites if mirror and name not in mirror)
    runnable = sorted(name for name in suites if name not in set(outside))
    if not runnable:
        raise StrictRequired(
            "every suite the map links to these paths lives outside the run-all "
            "mirror: %s" % ", ".join(outside),
            "Run those suites with their own context, or use the full mirror; "
            "an empty runnable set is not a green result.",
        )
    return {
        "status": "SELECTED",
        "changed": normalized,
        "suites": runnable,
        # Замыкание карты минус то, что зеркало умеет запускать без контекста.
        # Эти сьюты НЕ гоняются здесь по построению (нужен свой флаг, свой
        # кандидат или свой пин — прогон «просто так» дал бы false-red), но
        # они НАЗВАНЫ: тихий пропуск был бы false-green.
        "outsideMirror": outside,
        "closureSuites": suites,
        # Пути, чьё правило говорит «влияния нет»: НАЗВАНЫ поимённо, потому что
        # молчаливое исключение и есть тихое сужение.
        "ruledNoImpact": sorted(ruled_out),
        "closure": len(order),
        "note": ("selection is as complete as the audited map; suites outside "
                 "the run-all mirror are named, not run, and are not evidence; "
                 "this is not a gate and does not replace release evidence"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select the regression suites impacted by the changed paths.")
    # `nargs="*"` вместе с позиционным хвостом даёт `--` как честный конец
    # опций: путь, начинающийся с двух дефисов, иначе не передать
    # (находка cross-vendor ревьюера).
    parser.add_argument("--changed", nargs="*", default=None,
                        help="repository-relative changed paths; use `--` before "
                             "a path that itself starts with dashes")
    parser.add_argument("extra_changed", nargs="*", default=[],
                        help=argparse.SUPPRESS)
    parser.add_argument("--changed-from-git", action="store_true",
                        help="derive changed paths from the working tree/index")
    parser.add_argument("--base", default="origin/main",
                        help="base ref for --changed-from-git (default origin/main)")
    # Флага, называющего читаемый файл, здесь нет намеренно (решение владельца
    # 2026-08-24, `.itd/DECISIONS.md`): карта, правила и зеркало берутся из
    # ЭТОГО репозитория по расположению самого скрипта. Публичный override
    # порождал неисчерпаемый класс находок «чужая карта сужает прогон»;
    # мутационные тесты ходят внутренним швом `load_graph()`/`select()`.
    parser.add_argument("--format", choices=("names", "json"), default="names")
    args = parser.parse_args(argv)

    # Сравнивается ФАКТ передачи флага, а не пустота списка: `--changed --
    # --dashed-path.py` отдаёт пути в позиционный хвост, и проверка по
    # непустоте отвергала бы законный вызов.
    if (args.changed is not None) == bool(args.changed_from_git):
        print("WHY: exactly one of --changed or --changed-from-git is required",
              file=sys.stderr)
        print("FIX: name the changed paths, or ask Git for them.", file=sys.stderr)
        return EXIT_INPUT

    try:
        edges = load_graph(DEFAULT_GRAPH)
        rules = load_patterns(DEFAULT_PATTERNS)
        explicit = list(args.changed or []) + list(args.extra_changed or [])
        if args.changed is not None:
            if not explicit:
                print("WHY: --changed was given without any path", file=sys.stderr)
                print("FIX: name at least one path, or drop --changed.", file=sys.stderr)
                return EXIT_INPUT
            changed, sources = explicit, {}
        else:
            changed, sources = changed_from_git(ROOT, args.base)
        payload = select(changed, edges, rules)
        payload["changedSources"] = sources
    except StrictRequired as exc:
        print("STRICT REQUIRED: %s" % exc.why, file=sys.stderr)
        print("FIX: %s" % exc.fix, file=sys.stderr)
        return EXIT_STRICT
    except subprocess.SubprocessError as exc:
        print("WHY: Git probe failed: %s" % exc, file=sys.stderr)
        print("FIX: run from a working checkout or pass --changed.", file=sys.stderr)
        return EXIT_INPUT

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for name in payload["suites"]:  # type: ignore[index]
            print(name)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
