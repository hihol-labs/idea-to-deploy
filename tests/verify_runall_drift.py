#!/usr/bin/env python3
"""verify_runall_drift.py — дрифт-гард tests/run-all.sh ↔ CI-workflow (v1.79.1).

Упражнение «knowledge visibility gap» (2026-07-10) закрыло гэп «как прогнать
всё локально» скриптом tests/run-all.sh, зеркалящим оба workflow. Зеркало,
синхронизируемое руками, молча протухает: тест добавили в workflow — локальный
«DONE fails:none» перестаёт означать зелёный CI. Этот гард делает протухание
ГРОМКИМ: каждая verify-проверка, на которую ссылаются
.github/workflows/{meta-review,windows-verify}.yml, обязана присутствовать в
tests/run-all.sh.

Направление строгое одно: CI ⊆ run-all (обратное — run-all строже CI —
допустимо и лишь репортится). Anti-rot: парсер, ничего не нашедший, — это
false-green, поэтому минимальные счётчики распарсенного зашиты assert'ами.

Консолидация LPD003-4: этот же гард держит инварианты слияния сьютов по
impact-карте (пары с идентичным покрытием, целиком в зеркале): донор удалён из
дерева, из run-all и из CI; хранитель существует, исполняется зеркалом и
привязан в карте; замер .itd-memory/measurements/LPD003-4-consolidation.json
согласован с деревом и картой. Возврат донора или потеря хранителя — красный.

Stdlib-only, кросс-платформенный (гоняется и в windows-verify).
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [
    ROOT / ".github" / "workflows" / "meta-review.yml",
    ROOT / ".github" / "workflows" / "windows-verify.yml",
]
RUNALL = ROOT / "tests" / "run-all.sh"

# Скрипты, чей запуск в run-all.sh оформлен не именем в CORE/FULL, а явной
# строкой — маппинг «имя из workflow» → регэксп присутствия в run-all.sh.
SPECIAL = {
    "verify_skill_profiles": r"scripts/verify_skill_profiles\.py",
    "verify-sync-to-active": r"scripts/verify-sync-to-active\.sh",
    "verify_snapshot": r"tests/verify_snapshot\.py --all",
    "meta_review": r"\bmeta_review\b",
}

# Осознанно НЕ требуем в run-all.sh (недоступно/не имеет смысла локально):
EXCLUDED: set = set()

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    print("%s  %s%s" % ("PASS" if cond else "FAIL", name,
                        ("  [%s]" % detail) if detail and not cond else ""))
    if cond:
        passed += 1
    else:
        failed += 1


def ci_referenced() -> set:
    """Имена проверок (без .py), которые реально запускают workflow'ы."""
    names: set = set()
    rx = re.compile(
        r"run:\s*(?:python3?|py -3)?\s*"
        r"(?:bash\s+)?((?:tests|scripts)/[\w./-]+?\.(?:py|sh))")
    for wf in WORKFLOWS:
        text = wf.read_text(encoding="utf-8")
        for m in rx.finditer(text):
            stem = Path(m.group(1)).name
            stem = stem[:-3] if stem.endswith(".py") else stem[:-3]
            names.add(stem)
    return names - EXCLUDED


def runall_covered() -> set:
    """Имена проверок, которые запускает tests/run-all.sh."""
    text = RUNALL.read_text(encoding="utf-8")
    names = set(re.findall(r"\bverify_\w+\b", text))
    names.add("meta_review")
    for name, pat in SPECIAL.items():
        if re.search(pat, text):
            names.add(name)
    return names


def main() -> int:
    ci = ci_referenced()
    local = runall_covered()

    # anti-rot: парсер обязан находить нетривиальные множества
    check("parser: CI references >= 25 checks", len(ci) >= 25,
          "parsed only %d" % len(ci))
    check("parser: run-all covers >= 30 checks", len(local) >= 30,
          "parsed only %d" % len(local))

    missing = sorted(ci - local)
    check("every CI check is present in tests/run-all.sh", not missing,
          "missing from run-all.sh: %s" % missing)

    extra = sorted(local - ci)
    if extra:
        print("[info] run-all.sh runs extra (stricter than CI, OK):", extra)

    # самореференс: гард сам зарегистрирован и в CI, и в run-all
    check("this guard is wired into CI", "verify_runall_drift" in ci)
    check("this guard is wired into run-all.sh", "verify_runall_drift" in local)

    consolidation_invariants(ci, local)
    out_of_mirror_invariants(local)

    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


# --- N7/ORACLE-DEBT: закрытый реестр сьютов вне зеркала ----------------------
# Пока класс существует, «DONE fails:none» не равно «прогнано всё». Реестр
# делает исключение ИМЕНОВАННЫМ: у каждого внезеркального сьюта обязаны быть
# класс из закрытого перечня, причина и команда воспроизведения. Новый сьют,
# не попавший ни в зеркало, ни в реестр, валит этот оракул — тихого выпадения
# из покрытия больше нет.
OUT_OF_MIRROR = ROOT / "tests" / "OUT_OF_MIRROR.json"
# Политика владельца от 2026-08-28: ровно четыре причины быть вне зеркала.
APPROVED_CLASSES = {"phase-required", "candidate-bound",
                    "external-evidence-absent", "mirror-runner"}
ROW_FIELDS = {"suite", "class", "why", "reproduce", "pinnedCandidate",
              "measuredEvidence", "precondition"}


def mirror_executed() -> tuple[set, list[str]]:
    """Имена сьютов, которые зеркало РЕАЛЬНО исполняет, и нечитаемые строки.

    Общий парсер runall_covered() ловит любое слово verify_* в файле, включая
    комментарии, — для реестра этого мало: упоминание в комментарии не есть
    прогон, и такая нестрогость прятала бы настоящую дыру в покрытии.

    Хвостовые проверки берутся ТОЛЬКО из исполняемых вызовов, разобранных
    shlex'ом с comments=True. Отбрасывать одни лишь строки-комментарии
    недостаточно: строчный комментарий вида `cmd  # tests/verify_new.py`
    объявил бы сьют прогоняемым и обошёл бы гард неклассифицированных
    (находка ревьюера r4). Строка, которую shlex не разобрал, не игнорируется
    молча — она возвращается наверх и краснеет, если называет сьют.
    """
    text = RUNALL.read_text(encoding="utf-8")
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


def out_of_mirror_invariants(local: set) -> None:
    tests_dir = ROOT / "tests"
    executed, unparsed = mirror_executed()
    check("out-of-mirror: every run-all line that names a suite is parseable",
          not unparsed, "unparseable: %s" % unparsed[:3])
    check("out-of-mirror: the strict mirror parser finds a non-trivial set",
          len(executed) >= 30, "parsed only %d" % len(executed))
    check("out-of-mirror: strict parser never exceeds the loose one",
          executed <= local, "not covered by the loose parser: %s"
          % sorted(executed - local))
    local = executed
    on_disk = {p.name for p in tests_dir.glob("verify_*.py")}
    outside = {name for name in on_disk if name[:-3] not in local}
    try:
        registry = json.loads(OUT_OF_MIRROR.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail-closed на битом реестре
        check("out-of-mirror: registry readable", False, str(exc))
        return
    check("out-of-mirror: registry version is pinned", registry.get("version") == 1)
    classes = registry.get("classes")
    # Перечень классов пинится ЗДЕСЬ, а не берётся из самого реестра: иначе
    # достаточно было бы дописать в реестр новый класс и увести под него любой
    # исключённый сьют — политика владельца проверялась бы сама собой
    # (находка ревьюера r5). Расширение перечня — правка этого оракула.
    check("out-of-mirror: the class vocabulary is exactly the approved one",
          isinstance(classes, dict) and set(classes) == APPROVED_CLASSES,
          "registry=%s" % sorted(classes) if isinstance(classes, dict) else repr(classes)[:80])
    rows = registry.get("suites")
    check("out-of-mirror: registry lists suites", isinstance(rows, list) and bool(rows))
    if not isinstance(rows, list) or not isinstance(classes, dict):
        return
    registered: set = set()
    for row in rows:
        if not isinstance(row, dict):
            check("out-of-mirror: every row is an object", False, repr(row)[:120])
            continue
        suite = str(row.get("suite") or "")
        name = Path(suite).name
        check(f"out-of-mirror: {suite} exists in the tree",
              suite.startswith("tests/") and (ROOT / suite).is_file())
        check(f"out-of-mirror: {suite} names a class from the approved vocabulary",
              row.get("class") in APPROVED_CLASSES)
        check(f"out-of-mirror: {suite} carries only known fields",
              set(row) <= ROW_FIELDS, "unexpected: %s" % sorted(set(row) - ROW_FIELDS))
        # Непустой reproduce ещё ничего не воспроизводит: строка вида
        # `--phase <phase>` проходила проверку на непустоту и обещала зелёный
        # результат шаблоном, который не исполняется (находка ревьюера r7).
        reproduce = str(row.get("reproduce") or "").strip()
        check(f"out-of-mirror: {suite} states a reason and a reproduce command",
              bool(str(row.get("why") or "").strip()) and bool(reproduce))
        check(f"out-of-mirror: {suite} reproduce is executable, not a placeholder",
              "<" not in reproduce and ">" not in reproduce
              and name in reproduce,
              "reproduce: %s" % reproduce[:120])
        if row.get("class") == "phase-required":
            phase = reproduce.split("--phase", 1)[-1].strip().split()[0] \
                if "--phase" in reproduce else ""
            check(f"out-of-mirror: {suite} names a concrete phase",
                  bool(phase) and phase.isidentifier(),
                  "phase token: %r" % phase)
        check(f"out-of-mirror: {suite} is not silently also in the mirror",
              name[:-3] not in local)
        check(f"out-of-mirror: {suite} is listed once", name not in registered)
        registered.add(name)
    unclassified = sorted(outside - registered)
    check("out-of-mirror: every suite outside the mirror is classified",
          not unclassified, "unclassified: %s" % unclassified)
    stale = sorted(registered - outside)
    check("out-of-mirror: the registry names no suite the mirror already runs",
          not stale, "stale rows: %s" % stale)


# --- LPD003-4: инварианты консолидации сьютов по impact-карте ---------------
# Пары «хранитель <- донор» с ИДЕНТИЧНЫМ множеством покрытия по сгенерированной
# карте на entry-дереве 5b6e50f; обе стороны каждой пары жили в зеркале.
CONSOLIDATED = {
    "verify_signal_attribution": "verify_completion_ledger",
    "verify_observed_token_telemetry": "verify_cost_tracker",
    "verify_otel_export": "verify_otel_semconv",
    "verify_no_bare_python3": "verify_py_launcher_encoding",
    "verify_goal_tools": "verify_work_deadline_runtime",
}
MEASUREMENT = ROOT / ".itd-memory" / "measurements" / "LPD003-4-consolidation.json"
IMPACT_MAP = ROOT / ".itd" / "IMPACT_GRAPH.json"


def consolidation_invariants(ci: set, local: set) -> None:
    tests_dir = ROOT / "tests"
    try:
        generated = json.loads(IMPACT_MAP.read_text(encoding="utf-8"))["generated"]
    except Exception as exc:  # noqa: BLE001 — fail-closed на битой карте
        generated = None
        check("consolidation: impact map readable", False, str(exc))
    attached = set()
    if generated is not None:
        for suites in generated.values():
            attached.update(Path(s).name[:-3] for s in suites)

    for keeper, donor in CONSOLIDATED.items():
        check(f"consolidation: donor {donor} stays deleted",
              not (tests_dir / f"{donor}.py").is_file())
        check(f"consolidation: donor {donor} absent from run-all and CI",
              donor not in local and donor not in ci)
        check(f"consolidation: keeper {keeper} exists and runs in the mirror",
              (tests_dir / f"{keeper}.py").is_file() and keeper in local)
        if generated is not None:
            check(f"consolidation: keeper {keeper} attached in the impact map",
                  keeper in attached)

    # Замер до/после — коммитнутый артефакт; сверяем fail-closed с деревом.
    try:
        m = json.loads(MEASUREMENT.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        check("consolidation: measurement artifact readable", False, str(exc))
        return
    pairs = {p["keeper"]: p["donor"] for p in m.get("pairs", [])}
    check("consolidation: measurement records exactly these pairs",
          pairs == CONSOLIDATED, str(pairs))
    on_disk = len(list(tests_dir.glob("verify_*.py")))
    recorded = m.get("post", {}).get("suitesOnDisk")
    # Замер — ИСТОРИЧЕСКОЕ post-состояние того юнита, а не потолок дерева:
    # равенство с текущим деревом запрещало бы добавить сьют вообще, и любая
    # новая гарантия валила бы зеркало. Отмену самой консолидации ловят
    # проверки доноров и узлового множества выше, поэтому здесь остаётся
    # монотонность: число сьютов не имеет права УПАСТЬ ниже замеренного.
    check("consolidation: the tree never falls below the measured post-state",
          # type(...) is int, а не isinstance: bool наследует int, и
          # значение true в артефакте прошло бы как валидный счёт.
          type(recorded) is int and recorded >= 0 and on_disk >= recorded,
          "recorded=%s actual=%d" % (recorded, on_disk))
    check("consolidation: node set preserved (pre == post)",
          m.get("pre", {}).get("nodeSetSha256") == m.get("post", {}).get("nodeSetSha256")
          and bool(m.get("pre", {}).get("nodeSetSha256")))
    # Живая сверка замера с картой (находка pub2: равенство строк ВНУТРИ
    # артефакта не доказывает соответствие карте — сфабрикованный артефакт
    # прошёл бы). Предмет клейма «без потери покрытия» сверяется с ЖИВОЙ
    # generated-секцией: каждый узел покрытия каждой пары обязан существовать
    # в карте и быть покрыт именно хранителем этой пары. Полный node-set
    # намеренно НЕ замораживается (карта легитимно растёт с деревом —
    # анти-friction урок LPD003-2); замороженная часть — ровно слитое покрытие.
    if generated is not None:
        for p in m.get("pairs", []):
            keeper_path = "tests/%s.py" % p.get("keeper")
            nodes = p.get("coverage") or []
            live_ok = bool(nodes) and all(
                keeper_path in (generated.get(node) or []) for node in nodes)
            check("consolidation: live map keeps %s covering %d merged node(s)"
                  % (p.get("keeper"), len(nodes)), live_ok,
                  "missing: %s" % [n for n in nodes
                                   if keeper_path not in (generated.get(n) or [])])


if __name__ == "__main__":
    sys.exit(main())
