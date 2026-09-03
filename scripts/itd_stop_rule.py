#!/usr/bin/env python3
"""Правило остановки цикла независимого ревью — над СОДЕРЖАНИЕМ находок.

Зачем это существует
--------------------
Цикл ревью останавливали «по числу заходов». Замер показал, что число заходов
не измеряет ничего:

* из девяти незакрывшихся заходов публикации LPD-003-1 реальных вердиктов
  ревьюера было два — остальное транспорт и бухгалтерия;
* в S04b пятый раунд дал PASSED, а следующие четыре нашли в том же механизме
  ещё четыре реальных дефекта;
* в R6 тринадцать раундов подряд называли каждый раз НОВЫЙ механизм и сошлись
  на чистом PASS — любой потолок отгрузил бы кандидата с живым эксплойтом.

Сигнал остановки — это ПОВТОР ОДНОГО МЕХАНИЗМА через раунды: если после
попытки фикса тот же механизм даёт находку снова, дефектна форма решения, а не
экземпляр. Число раундов при этом не ограничивается ничем.

Статус правила — decides-with-human-confirmation: оно решает остановку,
печатает терминал и основание, а на терминалах решения владельца составляет
черновик диспозиций ADR-007 (`--emit-dispositions`); класс, основание и
подписант остаются за человеком. Гейтом оно не является.

Контракт: `.itd/STOP_RULE_POLICY.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / ".itd" / "STOP_RULE_POLICY.json"
HISTORY_SCHEMA = "itd-stop-rule-history-v1"
POLICY_SCHEMA = "itd-stop-rule-policy-v1"

TERMINAL_CLASSES = ("verdict", "precondition", "transport")
EXPECTED_PRECEDENCE = ["ROUTE_DEFECT", "REDESIGN_OR_DISCARD", "RECURRENCE_UNCONFIRMED",
                       "SURFACE_TREADMILL", "ROUTE_REPAIR", "CLOSE", "CONTINUE"]
# Улика поверхности (R7): проекция `git diff -U0` база серии -> кандидат раунда.
SURFACE_CLASSES = ("diff-hunks",)
SURFACE_PROJECTIONS = ("full", "hunk-headers")
SURFACE_COMMAND = ("git", "diff", "-U0", "--no-color", "--no-ext-diff")


def git_env() -> dict:
    """Окружение для git: локаль C, чтобы диагностики были стабильны
    (`not a git repository` разбирается по тексту — r16)."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    env["LANGUAGE"] = "C"
    return env
SURFACE_HEADER_PREFIXES = (
    "diff --git ", "--- ", "+++ ", "@@ ", "new file mode ", "deleted file mode ",
    "index ", "similarity ", "dissimilarity ", "rename ", "copy ", "old mode ",
    "new mode ", "Binary files ",
)
# Служебные строки, которые сами по себе делают секцию без ---/+++ законной:
# смена режима, переименование/копия без правок, бинарь, а также пустой
# новый/удалённый файл (git печатает его как `new file mode` + `index` без
# ---/+++). `index` в этом списке НЕТ: сама по себе она сопровождает
# содержательную секцию, и секция из одной `index` неполна (pub1).
SECTION_COMPLETING_PREFIXES = (
    "old mode ", "new mode ", "similarity ", "dissimilarity ", "rename ", "copy ",
    "Binary files ", "new file mode ", "deleted file mode ",
)
# Заякорен с обеих сторон: после закрывающего `@@` — либо конец строки, либо
# пробел и function-context; `@@ ... @@garbage` — не заголовок git (r23).
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
TREE_ID_RE = re.compile(r"[0-9a-f]{40}")
# Практический предел координат hunk: заголовок с миллиардом строк — не
# проекция реального диффа, а подложный архив (r18).
MAX_DIFF_LINE = 100_000_000


def add_interval(intervals: list, start: int, end: int) -> None:
    """Добавить [start, end] к отсортированному списку интервалов файла;
    смежный с последним — сливается. Ничего не материализуется."""
    if intervals and intervals[-1][1] + 1 >= start:
        intervals[-1][1] = max(intervals[-1][1], end)
    else:
        intervals.append([start, end])


def on_added_surface(added: dict, path, line) -> bool:
    """Лежит ли строка файла в добавленных интервалах."""
    if not isinstance(path, str) or not isinstance(line, int):
        return False
    for start, end in added.get(path, ()):
        if start <= line <= end:
            return True
    return False


def surface_lines(added: dict) -> dict:
    """Материализованное множество строк — ТОЛЬКО для малых поверхностей
    (оракул, диагностика); на подложных гигантах не вызывается."""
    return {path: {line for start, end in intervals for line in range(start, end + 1)}
            for path, intervals in added.items()}
# Окно R7 заморожено ПО ЗНАЧЕНИЮ, как и прочие скаляры политики: диапазон
# «3..20» пропускал ослабление 5 -> 3 молча (находка ревьюера, r7).
APPROVED_WINDOW_ROUNDS = 5
# Значения привязки, замороженные ПО ЗНАЧЕНИЮ, а не по непустоте. Проверка
# «строка не пуста» пропускала ослабленную политику: requireCriteriaStatus:
# null делал statusSatisfied тривиально истинным, и критерии в статусе pending
# считались бы выровненными — при том что продюсер отказывает по ним терминалом
# класса precondition. requireCriteriaPrefix вообще был объявлен и не проверен
# (находка независимого ревьюера, раунд r15).
EXPECTED_BINDING_INVARIANTS = {
    "requireCriteriaPrefix": True,
    "requireCriteriaStatus": "passed",
}

# Контрактные скаляры политики, замороженные ПО ЗНАЧЕНИЮ, одной декларативной
# картой (путь -> ожидаемое значение; сравнение по типу И по значению). Форма
# «замораживать поля по одному по мере находок» ломалась дважды: r15 нашёл
# незамороженный policyBinding, r24 — distinctRoundsRequired, принимавший
# любое >= 2 (политика с 3 глушила бы REDESIGN_OR_DISCARD на втором
# различимом раунде вопреки R1). Это повтор одного механизма по нашему же
# правилу, поэтому меняется форма: новый контрактный скаляр добавляется в
# карту, а не в новую if-ветку.
# Терминалы, на которых решение принадлежит владельцу: правило СОСТАВЛЯЕТ
# диспозиции ADR-007 по BLOCKED-квитанции чекера, человек ПОДПИСЫВАЕТ
# (STOPRULE-2). ROUTE_DEFECT — поломка маршрута, а не суждение о находках:
# диспозиций там не бывает.
OWNER_DECISION_TERMINALS = ("REDESIGN_OR_DISCARD", "SURFACE_TREADMILL")


def load_verification_loop():
    """Общая библиотека маршрута — источник дайджеста находки, фразы подписи и
    плейсхолдера черновика; правило их не переопределяет, иначе черновик и
    валидатор разошлись бы (r3: единство по построению, а не по тесту)."""
    shared = ROOT / "skills" / "_shared"
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
    import itd_verification_loop  # noqa: WPS433
    return itd_verification_loop


DRAFT_PLACEHOLDER = load_verification_loop().DRAFT_PLACEHOLDER

EXPECTED_POLICY_SCALARS = {
    ("status",): "decides-with-human-confirmation",
    # Кто составляет и кто подписывает — контракт, а не примечание (r4).
    ("humanConfirmation", "drafts"): "rule",
    ("humanConfirmation", "signs"): "human",
    ("mechanismKey", "mergeOnly"): True,
    ("mechanismKey", "distinctRoundsRequired"): 2,
    ("policyBinding", "requireCriteriaPrefix"): True,
    ("policyBinding", "requireCriteriaStatus"): "passed",
    ("surfaceTreadmill", "evidenceClass"): "diff-hunks",
    ("surfaceTreadmill", "contextLines"): 0,
    ("surfaceTreadmill", "requireBlockedWindow"): True,
    ("surfaceTreadmill", "unlocatedFinding"): "not-on-added-surface",
    ("surfaceTreadmill", "windowRounds"): APPROVED_WINDOW_ROUNDS,
}


def frozen_scalar_violation(document: dict, path: tuple, expected) -> str | None:
    node = document
    for part in path:
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            break
    if type(node) is not type(expected) or node != expected:
        return (f"policy {'.'.join(path)} must be {expected!r}, got {node!r}: "
                f"контрактное значение заморожено по типу и по значению")
    return None

EXPECTED_TERMINAL_VALUES = {
    "verdict": ["PASSED", "PASSED_WITH_WARNINGS", "BLOCKED"],
    "precondition": ["UNVERIFIED"],
    "transport": ["UNAVAILABLE", "TIMEOUT", "ABORTED"],
}
PROVENANCE_CLASSES = ("report", "narrative", "absent")


class StopRuleError(Exception):
    """Fail-closed: вход, о котором нельзя судить, не судится молча."""


# --------------------------------------------------------------------------
# загрузка контрактов
# --------------------------------------------------------------------------

def load_policy(path: Path | None = None) -> dict:
    path = Path(path) if path else POLICY_PATH
    if not path.is_file():
        raise StopRuleError(f"policy is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StopRuleError(f"policy is not valid JSON: {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise StopRuleError(f"policy root must be an object: {path}")
    if document.get("schema") != POLICY_SCHEMA:
        raise StopRuleError(
            f"policy schema must be {POLICY_SCHEMA}, got {document.get('schema')!r}"
        )
    for section in ("terminalClasses", "mechanismKey", "rules", "precedence",
                    "policyBinding", "provenanceClasses"):
        if section not in document:
            raise StopRuleError(f"policy has no {section!r} section")
        # precedence — список; остальные обязательные секции — объекты.
        # Малформленная, но парсибельная политика ({"mechanismKey": null})
        # обязана давать документированный StopRuleError, а не AttributeError
        # с трейсбэком (находка ревьюера, раунд r25).
        expected_shape = list if section == "precedence" else dict
        if not isinstance(document[section], expected_shape):
            raise StopRuleError(
                f"policy section {section!r} must be "
                f"{'a list' if expected_shape is list else 'an object'}"
            )
    key = document["mechanismKey"]
    if key.get("default") != ["file", "category"]:
        raise StopRuleError("policy mechanismKey.default must stay (file, category)")
    for path, expected in EXPECTED_POLICY_SCALARS.items():
        violation = frozen_scalar_violation(document, path, expected)
        if violation is not None:
            raise StopRuleError(violation)

    # Статус decides-with-human-confirmation заморожен картой
    # EXPECTED_POLICY_SCALARS: и откат в advisory, и превращение в гейт —
    # отдельное решение владельца, а не правка политики.
    treadmill = document.get("surfaceTreadmill")
    if not isinstance(treadmill, dict):
        raise StopRuleError("policy has no 'surfaceTreadmill' section")
    if list(treadmill.get("projections") or []) != list(SURFACE_PROJECTIONS):
        raise StopRuleError(
            f"policy surfaceTreadmill.projections must be {list(SURFACE_PROJECTIONS)}"
        )
    text = json.dumps(document, ensure_ascii=False)
    for forbidden in ("maxRounds", "roundCap", "maxAttempts", "roundLimit"):
        if forbidden in text:
            raise StopRuleError(
                f"policy declares {forbidden!r}: потолок раундов запрещён по "
                f"построению — он останавливает сходящийся маршрут на зелёном"
            )
    confirmation = document.get("humanConfirmation")
    if (not isinstance(confirmation, dict)
            or confirmation.get("terminals") != list(OWNER_DECISION_TERMINALS)
            or confirmation.get("placeholder") != DRAFT_PLACEHOLDER):
        raise StopRuleError(
            f"policy humanConfirmation must name terminals {list(OWNER_DECISION_TERMINALS)} "
            f"and placeholder {DRAFT_PLACEHOLDER!r}: на каких терминалах правило "
            f"составляет диспозиции — контракт, а не подсказка"
        )
    if document.get("precedence") != EXPECTED_PRECEDENCE:
        raise StopRuleError(
            f"policy precedence must be {EXPECTED_PRECEDENCE}, got "
            f"{document.get('precedence')!r}"
        )
    for name, expected in EXPECTED_TERMINAL_VALUES.items():
        section = document["terminalClasses"].get(name)
        if not isinstance(section, dict) or list(section.get("values") or []) != expected:
            raise StopRuleError(
                f"policy terminalClasses.{name}.values must be {expected}"
            )
        counts = section.get("counts")
        if counts is not (name == "verdict"):
            raise StopRuleError(
                f"policy terminalClasses.{name}.counts must be {name == 'verdict'}"
            )
    binding = document["policyBinding"]
    for field in ("contractPath", "contractUnitField", "ledgerPath", "ledgerUnitField"):
        if not str(binding.get(field) or "").strip():
            raise StopRuleError(f"policy policyBinding.{field} is missing")
    # requireCriteriaPrefix / requireCriteriaStatus заморожены картой
    # EXPECTED_POLICY_SCALARS выше — вторая копия проверки разошлась бы молча.
    return document


def verdict_values(policy: dict) -> tuple[str, ...]:
    return tuple(policy["terminalClasses"]["verdict"]["values"])


def load_history(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise StopRuleError(f"history is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StopRuleError(f"history is not valid JSON: {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise StopRuleError(f"history root must be an object: {path}")
    if document.get("schema") != HISTORY_SCHEMA:
        raise StopRuleError(
            f"history schema must be {HISTORY_SCHEMA}, got {document.get('schema')!r}"
        )
    for field in ("unit", "orderSource", "rounds"):
        if field not in document:
            raise StopRuleError(f"history has no {field!r}: {path}")
    if not isinstance(document["rounds"], list) or not document["rounds"]:
        raise StopRuleError(f"history rounds must be a non-empty list: {path}")
    supplies_candidate = any(
        isinstance(entry, dict) and entry.get("terminal") == "verdict"
        and str(entry.get("candidate") or "").strip()
        for entry in document["rounds"]
    )
    source = document.get("candidateSource")
    if supplies_candidate and not (isinstance(source, dict) and str(source.get("kind") or "").strip()):
        raise StopRuleError(
            f"history supplies candidate identity without candidateSource: {path}\n"
            f"  WHY: смена кандидата — это то, ради чего повтор вообще считается "
            f"повтором. Две выдуманные строки без объявленного происхождения "
            f"взвели бы REDESIGN_OR_DISCARD на пустом месте.\n"
            f"  FIX: объявить candidateSource как объект с полем kind — из чего "
            f"выведены личности раундов и можно ли их пересчитать."
        )

    gaps = document.get("knownGaps", [])
    if not isinstance(gaps, list):
        raise StopRuleError(f"knownGaps must be a list: {path}")
    for index, gap in enumerate(gaps):
        if (not isinstance(gap, dict)
                or not str(gap.get("id") or "").strip()
                or not str(gap.get("why") or "").strip()):
            raise StopRuleError(
                f"knownGaps[{index}] needs id and why: {path} — раунд, чей класс "
                f"терминала неизвестен, не получает выдуманный класс, но и не "
                f"исчезает из записи молча"
            )
    recorded = document.get("recordedDecision")
    if recorded is not None:
        if not isinstance(recorded, dict):
            raise StopRuleError(f"recordedDecision must be an object: {path}")
        named = recorded.get("atRound")
        if named is not None:
            known = {entry.get("id") for entry in document["rounds"]
                     if isinstance(entry, dict)}
            known |= {gap.get("id") for gap in (document.get("knownGaps") or [])
                      if isinstance(gap, dict)}
            if named not in known:
                raise StopRuleError(
                    f"recordedDecision.atRound {named!r} is not a recorded round or a "
                    f"declared gap in {path} — решение, сославшееся на несуществующий "
                    f"раунд, невоспроизводимо"
                )

    if not str(document.get("orderSource") or "").strip():
        raise StopRuleError(
            f"history must declare orderSource: порядок, восстановленный не из "
            f"артефактов, не переживает клон и обязан быть объявлен: {path}"
        )
    # orderSource — пояснение для человека; машинно проверяется orderProvenance:
    # свободный текст мог цитировать несуществующий источник порядка, и решение
    # опиралось бы на непроверяемое утверждение (находка ревьюера, раунд r34).
    validate_order_provenance_shape(document, path)
    return document


# --------------------------------------------------------------------------
# провенанс раунда
# --------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def validated_outcome(entry: dict, terminal: str, policy: dict, round_id: str):
    """Исход раунда обязан принадлежать словарю своего класса терминала.

    Без этой проверки раунд без сохранённого содержания мог объявить себя
    вердиктом с произвольным исходом и попасть в решение — fail-open ровно в
    том месте, где правило обещает fail-closed.
    """
    outcome = entry.get("outcome")
    allowed = tuple(policy["terminalClasses"][terminal]["values"])
    if outcome not in allowed:
        raise StopRuleError(
            f"round {round_id}: outcome {outcome!r} is not one of {allowed} "
            f"for terminal class {terminal!r}"
        )
    return outcome


def apply_dispositions(entry: dict, count: int, round_id: str):
    """Диспозиции находок объявляются ИСТОРИЕЙ, а не отчётом ревьюера.

    Отчёт — сырая улика и переписыванию не подлежит. Но у находки бывает
    судьба, которой в отчёте нет: она опровергнута фактами (замер R6, PUB8)
    или это регрессия — откат ранее существовавшей гарантии (замер GPG-001,
    MEM-8). Обе снимают находку со счёта повторов, поэтому обязаны быть
    названы явно и с основанием.
    """
    dispositions = entry.get("dispositions", [])
    if not isinstance(dispositions, list):
        raise StopRuleError(f"round {round_id}: dispositions must be a list")
    for position, disposition in enumerate(dispositions):
        if not isinstance(disposition, dict):
            raise StopRuleError(f"round {round_id}: dispositions[{position}] must be an object")
        finding_index = disposition.get("finding")
        if (not isinstance(finding_index, int) or isinstance(finding_index, bool)
                or not 0 <= finding_index < count):
            raise StopRuleError(
                f"round {round_id}: dispositions[{position}].finding must index an "
                f"existing finding (0..{count - 1})"
            )
        flags = {}
        for key in ("regression", "refuted"):
            if key not in disposition:
                continue
            if not isinstance(disposition[key], bool):
                raise StopRuleError(
                    f"round {round_id}: dispositions[{position}].{key} must be a "
                    f"boolean — истинное значение любого типа снимало бы находку "
                    f"со счёта повторов молча"
                )
            if disposition[key]:
                flags[key] = True
        if not flags:
            raise StopRuleError(
                f"round {round_id}: dispositions[{position}] must set regression or refuted"
            )
        if not str(disposition.get("why") or "").strip():
            raise StopRuleError(
                f"round {round_id}: dispositions[{position}] needs why — снятие находки "
                f"со счёта повторов без основания это и есть подкраска"
            )
        yield finding_index, flags


def validate_report_provenance(provenance: dict, round_id: str, root: Path) -> Path:
    """Проверить улику-отчёт: путь внутри репозитория, файл на месте, sha сходится."""
    rel = provenance.get("path")
    if not isinstance(rel, str) or not rel.strip():
        raise StopRuleError(f"round {round_id}: report provenance needs a path")
    artifact = (root / rel).resolve()
    try:
        artifact.relative_to(root.resolve())
    except ValueError as exc:
        raise StopRuleError(
            f"round {round_id}: report path escapes the repository: {rel}"
        ) from exc
    if not artifact.is_file():
        raise StopRuleError(
            f"round {round_id}: report artifact is missing: {rel}\n"
            f"  WHY: раунд объявлен машинной уликой, а улики в дереве нет.\n"
            f"  FIX: вернуть артефакт в дерево либо перевести раунд в "
            f"provenance.class=narrative и пометить его пересказом."
        )
    declared_sha = provenance.get("sha256")
    actual_sha = sha256_of(artifact)
    if not isinstance(declared_sha, str) or declared_sha != actual_sha:
        raise StopRuleError(
            f"round {round_id}: report sha256 mismatch for {rel}\n"
            f"  declared={declared_sha!r}\n  actual={actual_sha!r}"
        )
    return artifact


def validate_narrative_provenance(provenance: dict, round_id: str, root: Path) -> None:
    """Проверить пересказ: документ в дереве и КОНКРЕТНАЯ существующая строка."""
    source = provenance.get("path")
    if not isinstance(source, str) or not source.strip():
        raise StopRuleError(
            f"round {round_id}: narrative provenance needs the recorded document path"
        )
    document_path = (root / source).resolve()
    try:
        document_path.relative_to(root.resolve())
    except ValueError as exc:
        raise StopRuleError(
            f"round {round_id}: narrative path escapes the repository: {source}"
        ) from exc
    if not document_path.is_file():
        raise StopRuleError(
            f"round {round_id}: narrative source document is missing: {source}"
        )
    cited_line = provenance.get("line")
    if not isinstance(cited_line, int) or isinstance(cited_line, bool) or cited_line < 1:
        raise StopRuleError(
            f"round {round_id}: narrative provenance needs a positive cited line in "
            f"{source} — «где-то в этом документе» провенансом не является"
        )
    line_count = sum(1 for _ in document_path.open("r", encoding="utf-8", errors="replace"))
    if cited_line > line_count:
        raise StopRuleError(
            f"round {round_id}: cited line {cited_line} is past the end of {source} "
            f"({line_count} lines)"
        )


def finding_line(value, round_id: str, position: int):
    """Строка находки: None либо целое >= 1. Иное — отказ, а не молчаливый None.

    Строка нужна только критерию поверхности (R7); в ключ механизма она не
    входит (дрейф строк внутри одного механизма — замер S04b).
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StopRuleError(
            f"round {round_id}: finding #{position} line must be a positive "
            f"integer or absent, got {value!r}"
        )
    return value


def repository_artifact(rel, round_id: str, root: Path, what: str) -> Path:
    """Артефакт улики: путь внутри репозитория, файл на месте."""
    if not isinstance(rel, str) or not rel.strip():
        raise StopRuleError(f"round {round_id}: {what} needs a path")
    artifact = (root / rel).resolve()
    try:
        artifact.relative_to(root.resolve())
    except ValueError as exc:
        raise StopRuleError(
            f"round {round_id}: {what} path escapes the repository: {rel}"
        ) from exc
    if not artifact.is_file():
        raise StopRuleError(f"round {round_id}: {what} artifact is missing: {rel}")
    return artifact


GIT_QUOTE_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13,
                     "\\": 92, '"': 34}


def git_unquote(raw: str, where: str) -> str:
    """Снять квотинг git с операнда пути (`"a/f\\tx"`, `\\303\\251` — октали).

    git квотит пути с табами, кавычками, обратной косой и (при обычном
    core.quotePath) не-ASCII байтами; без декодера живые проекции таких путей
    отвергались бы, и критерий поверхности был бы неприменим к ним (r12).
    Неквотированный операнд возвращается как есть.
    """
    if not raw.startswith('"'):
        return raw
    if len(raw) < 2 or not raw.endswith('"'):
        raise StopRuleError(f"{where}: unterminated quoted path operand {raw!r}")
    body = raw[1:-1]
    out = bytearray()
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(body):
            raise StopRuleError(f"{where}: dangling escape in quoted path operand {raw!r}")
        char = body[index]
        if char in GIT_QUOTE_ESCAPES:
            out.append(GIT_QUOTE_ESCAPES[char])
            index += 1
            continue
        octal = body[index:index + 3]
        if len(octal) == 3 and all(digit in "01234567" for digit in octal):
            value = int(octal, 8)
            if value > 0o377:
                # git кодирует байты 000..377; усечение `& 0xFF` нормализовало
                # бы подложный операнд в другой путь (r17).
                raise StopRuleError(
                    f"{where}: octal escape \\{octal} exceeds one byte in quoted path {raw!r}"
                )
            out.append(value)
            index += 3
            continue
        raise StopRuleError(f"{where}: unknown escape in quoted path operand {raw!r}")
    return out.decode("utf-8", errors="surrogateescape")


def swap_diff_side(raw: str, source: str, target: str, where: str) -> str:
    """`b/…` -> `a/…` (и обратно) с сохранением квотинга — для /dev/null-стороны."""
    if raw.startswith('"' + source + "/"):
        return '"' + target + "/" + raw[len(source) + 2:]
    if raw.startswith(source + "/"):
        return target + "/" + raw[len(source) + 1:]
    raise StopRuleError(f"{where}: diff operand {raw!r} does not name the {source}/ side")


def diff_lines(text: str) -> list[str]:
    """Строки диффа — ТОЛЬКО по LF: `str.splitlines()` считает разделителями
    U+0085/U+2028/U+2029 и рвал бы валидную добавленную строку на фантомные
    (r16). Завершающий LF не порождает пустой строки; CR остаётся в строке."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse_diff_surface(text: str, *, projection: str, where: str) -> dict:
    """Добавленные строки НОВОЙ стороны по файлам из вывода `git diff -U0`.

    full — считаются '+'-строки; hunk-headers — новая сторона заголовка
    `@@ -a,b +c,d @@` целиком (при -U0 контекста нет, поэтому весь диапазон
    добавлен либо изменён). Строка контекста в full-проекции — отказ: улика,
    снятая не с -U0, завышала бы добавленную поверхность и взводила бы
    терминал там, где его нет.
    """
    if projection not in SURFACE_PROJECTIONS:
        raise StopRuleError(f"{where}: projection must be one of {SURFACE_PROJECTIONS}")
    added: dict[str, list] = {}   # путь -> отсортированные интервалы [start, end]
    current: str | None = None
    deleted = False          # файл удалён: hunk законен, добавленных строк нет
    in_hunk = False
    new_line: int | None = None
    # Структурная связка вывода git (r10): каждая секция файла обязана идти
    # `diff --git a/X b/X` -> `--- ` -> `+++ ` -> hunks. Архив из одних
    # `+++`/`@@` — не проекция git-вывода, а самоподписанный набор диапазонов,
    # и при недоступных объектах он прошёл бы как «непроверяемый».
    # Из строки `diff --git a/OLD b/NEW` путь НЕ извлекается: git не квотит
    # пробелы, и путь с подстрокой " b/" делал бы разбор неоднозначным (r11).
    # Авторитетны заголовки `---`/`+++`; строка diff --git обязана быть
    # ровно их конкатенацией — это и есть структурная связка секции.
    diff_operands: str | None = None
    minus_target: str | None = None
    seen_plus = False
    section_meta = False   # в секции была хотя бы одна служебная строка
    # Порядок hunks внутри секции: git выдаёт их по возрастанию с обеих
    # сторон и без пересечений. Самоподписанный архив с дублями, перекрытием
    # или обратным порядком помечал бы произвольные строки добавленными (r13).
    prev_old: tuple[int, int] | None = None
    prev_new: tuple[int, int] | None = None
    # Уникальность секций — по декодированному пути КАЖДОЙ стороны, а не по
    # сырой паре операндов: `a/old1 b/t` и `a/old2 b/t` оба добавляли бы
    # диапазоны в t (r14).
    seen_paths: set[str] = set()
    # Счётчики полноты hunk (full-проекция): содержимое обязано дать РОВНО
    # столько старых и новых строк, сколько объявил заголовок. Иначе
    # подложная улика с самоподписанным sha (при недоступных объектах git)
    # могла бы задать произвольные диапазоны недолитым или перелитым hunk (r2).
    old_left = 0
    new_left = 0
    hunk_at = 0

    def close_section(at_line: int) -> None:
        """Секция `diff --git` обязана быть полной: либо `---`+`+++` (с hunks
        или без), либо только служебные строки без hunks (смена режима,
        переименование без правок). Голая секция или `---` без `+++` —
        подложный хвост архива, а не вывод git (r24)."""
        if diff_operands is None:
            return
        if minus_target is not None and not seen_plus:
            raise StopRuleError(
                f"{where}: diff section {diff_operands!r} has '---' without '+++' "
                f"before line {at_line}"
            )
        if not seen_plus and not section_meta:
            raise StopRuleError(
                f"{where}: bare diff section {diff_operands!r} without headers "
                f"before line {at_line} — не проекция вывода git"
            )

    def close_hunk() -> None:
        # Единственная точка проверки полноты: недолив (остаток > 0) и перелив
        # (остаток < 0) ловятся здесь же — отдельные встроенные проверки были
        # бы избыточны и непроверяемы мутацией.
        if projection == "full" and in_hunk and (old_left != 0 or new_left != 0):
            raise StopRuleError(
                f"{where}: hunk at line {hunk_at} does not match its header — "
                f"old lines off by {old_left}, new lines off by {new_left} "
                f"(положительное — недолив, отрицательное — перелив)"
            )

    for number, line in enumerate(diff_lines(text), 1):
        # Внутри недолитого hunk full-проекции строки '+'/'-' — СОДЕРЖИМОЕ,
        # даже если выглядят как заголовок: добавленная строка `++ x` даётся
        # git как `+++ x`, удалённая `-- y` — как `--- y`. Заголовок возможен
        # только когда счётчики hunk исчерпаны — ровно так различает их git (r8).
        if (projection == "full" and in_hunk and (old_left > 0 or new_left > 0)
                and line[:1] in "+-"):
            if line.startswith("+"):
                if current is None or new_line is None:
                    raise StopRuleError(
                        f"{where}: added line inside a deleted file at line {number} — "
                        f"новая сторона удалённого файла пуста"
                    )
                add_interval(added[current], new_line, new_line)
                new_line += 1
                new_left -= 1
            else:
                old_left -= 1
            continue
        if line.startswith("diff --git "):
            close_hunk()
            close_section(number)
            diff_operands = line[len("diff --git "):]
            minus_target = None
            seen_plus = False
            section_meta = False
            prev_old = None
            prev_new = None
            current = None
            deleted = False
            in_hunk = False
            new_line = None
            continue
        if line.startswith("--- "):
            close_hunk()
            if diff_operands is None or minus_target is not None:
                raise StopRuleError(
                    f"{where}: '---' header without its diff --git section at line {number}"
                )
            minus_target = line[4:].split("\t")[0]
            in_hunk = False
            continue
        if line.startswith("+++ "):
            close_hunk()
            if diff_operands is None or minus_target is None or seen_plus:
                raise StopRuleError(
                    f"{where}: '+++' header without the preceding diff --git/--- pair "
                    f"at line {number} — архив не является проекцией вывода git"
                )
            seen_plus = True
            target = line[4:].split("\t")[0]
            if minus_target == "/dev/null" and target == "/dev/null":
                raise StopRuleError(f"{where}: both diff sides are /dev/null at line {number}")
            here = f"{where} line {number}"
            minus_path = git_unquote(minus_target, here) if minus_target != "/dev/null" else None
            plus_path = git_unquote(target, here) if target != "/dev/null" else None
            if minus_path is not None and not minus_path.startswith("a/"):
                raise StopRuleError(f"{where}: '---' operand must start with a/ at line {number}")
            if plus_path is not None and not plus_path.startswith("b/"):
                raise StopRuleError(f"{where}: '+++' operand must start with b/ at line {number}")
            # Строка diff --git сверяется в СЫРОМ (квотированном) виде: git
            # квотит каждый операнд так же, как заголовки ---/+++.
            raw_old = minus_target if minus_path is not None else swap_diff_side(target, "b", "a", here)
            raw_new = target if plus_path is not None else swap_diff_side(minus_target, "a", "b", here)
            for side_path in {path[2:] for path in (minus_path, plus_path) if path is not None}:
                if side_path in seen_paths:
                    raise StopRuleError(
                        f"{where}: path {side_path!r} appears in more than one diff "
                        f"section at line {number}"
                    )
                seen_paths.add(side_path)
            if diff_operands != f"{raw_old} {raw_new}":
                raise StopRuleError(
                    f"{where}: diff --git operands {diff_operands!r} do not match the "
                    f"---/+++ headers ({minus_target!r}, {target!r}) at line {number}"
                )
            if plus_path is None:
                current = None
                deleted = True
            else:
                current = plus_path[2:]
                deleted = False
                added.setdefault(current, [])
            in_hunk = False
            new_line = None
            continue
        if line.startswith("@@"):
            close_hunk()
            match = HUNK_RE.match(line)
            if match is None:
                raise StopRuleError(f"{where}: malformed hunk header at line {number}: {line!r}")
            if not seen_plus:
                raise StopRuleError(f"{where}: hunk before a +++ header at line {number}")
            if current is None and not deleted:
                raise StopRuleError(f"{where}: hunk before a +++ header at line {number}")
            old_start = int(match.group(1))
            old_left = int(match.group(2)) if match.group(2) is not None else 1
            start = int(match.group(3))
            count = int(match.group(4)) if match.group(4) is not None else 1
            for side, side_start, side_count in (("old", old_start, old_left), ("new", start, count)):
                if side_count > 0 and side_start < 1:
                    # `+0,2` невозможен для git: положительный диапазон начинается
                    # с 1; нулевая координата законна только при нулевой длине (r21).
                    raise StopRuleError(
                        f"{where}: hunk at line {number} has an impossible {side}-side "
                        f"start {side_start} for a non-empty range"
                    )
            if max(old_start + old_left, start + count) > MAX_DIFF_LINE:
                raise StopRuleError(
                    f"{where}: hunk at line {number} exceeds the practical line limit "
                    f"{MAX_DIFF_LINE} — это не проекция реального диффа"
                )
            new_left = count
            for label, previous, current_range in (
                ("old", prev_old, (old_start, old_left)),
                ("new", prev_new, (start, count)),
            ):
                if previous is not None:
                    floor = previous[0] + max(previous[1], 1)
                    if current_range[0] < floor:
                        raise StopRuleError(
                            f"{where}: hunk at line {number} is out of order or overlaps "
                            f"the previous one on the {label} side "
                            f"({current_range[0]} < {floor}) — вывод git строго возрастает"
                        )
            prev_old = (old_start, old_left)
            prev_new = (start, count)
            in_hunk = True
            hunk_at = number
            if minus_target == "/dev/null" and old_left:
                # Новый файл: старой стороны нет, `-1,5` невозможен (pub1).
                raise StopRuleError(
                    f"{where}: new file declares {old_left} old line(s) at line {number}"
                )
            if current is None:
                # Удалённый файл: новая сторона пуста (+0,0). Проверяется по
                # заголовку в ЛЮБОЙ проекции: в hunk-headers содержимого нет,
                # и close_hunk этот случай не видит (r9).
                if count:
                    raise StopRuleError(
                        f"{where}: deleted file declares {count} new line(s) at line "
                        f"{number} — новая сторона удалённого файла пуста"
                    )
                new_line = None
            elif projection == "hunk-headers":
                if count:
                    add_interval(added[current], start, start + count - 1)
                new_line = None
            else:
                new_line = start
            continue
        if line.startswith(SURFACE_HEADER_PREFIXES):
            if diff_operands is None:
                raise StopRuleError(
                    f"{where}: metadata line outside a diff section at line {number}"
                )
            close_hunk()
            in_hunk = False
            if line.startswith(SECTION_COMPLETING_PREFIXES):
                section_meta = True
            continue
        if projection == "hunk-headers":
            raise StopRuleError(
                f"{where}: projection hunk-headers must not carry content lines "
                f"(line {number}): {line[:60]!r}"
            )
        if not in_hunk:
            raise StopRuleError(f"{where}: content line outside a hunk at line {number}")
        if line.startswith("+"):
            if current is None or new_line is None:
                raise StopRuleError(
                    f"{where}: added line inside a deleted file at line {number} — "
                    f"новая сторона удалённого файла пуста"
                )
            add_interval(added[current], new_line, new_line)
            new_line += 1
            new_left -= 1
        elif line.startswith("-"):
            old_left -= 1
        elif line.startswith("\\"):
            continue
        else:
            raise StopRuleError(
                f"{where}: context or unrecognised line inside a -U0 diff at line "
                f"{number}: {line[:60]!r} — улика обязана быть снята командой "
                f"{' '.join(SURFACE_COMMAND)}"
            )
    close_hunk()
    close_section(len(diff_lines(text)) + 1)
    return added


def git_repository_present(root: Path) -> bool:
    """Есть ли у корня репозиторий — отвечает сам git (`rev-parse`), а не
    наличие каталога `.git`: в linked worktree `.git` — файл (r14). Любой
    сбой исполнения — контролируемый отказ, как и в cat-file."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=30, env=git_env())
    except (OSError, subprocess.SubprocessError) as exc:
        raise StopRuleError(
            f"git rev-parse could not run in {root}: {exc} — живая проверка не состоялась"
        ) from exc
    if result.returncode == 0:
        answer = result.stdout.strip()
        if answer == "true":
            return True
        # exit 0 с любым другим выводом — не «репозитория нет», а сбой
        # исполнения (обёртка, порча): контролируемый отказ (r15).
        raise StopRuleError(
            f"git rev-parse answered unexpectedly in {root}: {answer[:60]!r}"
        )
    if result.returncode == 128 and "not a git repository" in result.stderr:
        return False
    raise StopRuleError(
        f"git rev-parse failed in {root} (exit {result.returncode}): "
        f"{result.stderr.strip()[:200]}"
    )


def git_object_type(root: Path, oid: str) -> str | None:
    """Тип объекта git; None ТОЛЬКО если репозитория или объекта нет.

    Используется `cat-file --batch-check`: его вывод машинный и не зависит от
    локали и версии — `<oid> missing` для отсутствующего объекта, иначе
    `<oid> <type> <size>` (r6: разбор английской строки stderr был хрупок).
    Сбой исполнения (нет git, таймаут, права, I/O, порча репозитория) — это
    не «объекта нет», а «проверка не состоялась»: контролируемый отказ, иначе
    самоподписанный архив принимался бы как непроверяемый ровно тогда, когда
    проверить его нельзя (r5).
    """
    if not git_repository_present(root):
        return None
    try:
        result = subprocess.run(["git", "-C", str(root), "cat-file", "--batch-check"],
                                input=oid + "\n", capture_output=True, text=True,
                                timeout=30, env=git_env())
    except (OSError, subprocess.SubprocessError) as exc:
        raise StopRuleError(
            f"git cat-file could not run for {oid[:12]}: {exc} — живая проверка "
            f"дерева не состоялась, улика не считается непроверяемой"
        ) from exc
    if result.returncode != 0:
        raise StopRuleError(
            f"git cat-file failed for {oid[:12]} (exit {result.returncode}): "
            f"{result.stderr.strip()[:200]} — репозиторий не отвечает, а не объект отсутствует"
        )
    fields = result.stdout.strip().split()
    if len(fields) == 2 and fields[0] == oid and fields[1] == "missing":
        return None
    if len(fields) == 3 and fields[0] == oid and fields[1]:
        return fields[1]
    raise StopRuleError(
        f"git cat-file --batch-check answered unexpectedly for {oid[:12]}: "
        f"{result.stdout.strip()[:120]!r}"
    )


def require_live_tree(root: Path, oid: str, what: str) -> bool:
    """Живой объект обязан быть ДЕРЕВОМ: коммит или blob с валидным диффом
    подменяли бы личность кандидата (r4). Отсутствующий объект — не отказ, а
    «непроверяемо» (клон без loose-объектов)."""
    kind = git_object_type(root, oid)
    if kind is None:
        return False
    if kind != "tree":
        raise StopRuleError(
            f"{what} {oid[:12]} is a git {kind}, not a tree — деревом кандидата "
            f"может быть только объект типа tree"
        )
    return True


def git_object_exists(root: Path, oid: str) -> bool:
    return git_object_type(root, oid) is not None


def surface_projection(root: Path, base: str, candidate: str, projection: str) -> str:
    """Пересчитать улику поверхности из живых объектов git — байт в байт."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *SURFACE_COMMAND[1:], base, candidate],
            capture_output=True, timeout=120, check=True, env=git_env())
        stdout = result.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        # Байты вне UTF-8 в путях или содержимом — тоже контролируемый отказ,
        # а не трассировка (r10): архив хешируется как UTF-8 текст.
        raise StopRuleError(
            f"surface projection {base[:12]}..{candidate[:12]} could not be "
            f"recomputed from the live trees: {exc}"
        ) from exc
    if projection == "full":
        return stdout
    return project_hunk_headers(stdout)


def project_hunk_headers(full_text: str) -> str:
    """Проекция заголовков из полного `-U0` диффа — с учётом состояния hunk.

    Отбор по одному префиксу строки ошибался на содержимом, похожем на
    заголовок: добавленная строка `++ x` даётся git как `+++ x` и попадала
    бы в проекцию как структурный заголовок (r13). Пока hunk не долит по
    счётчикам, строки '+'/'-' — содержимое и в проекцию не идут.
    """
    kept: list[str] = []
    old_left = 0
    new_left = 0
    in_hunk = False
    for line in diff_lines(full_text):
        if in_hunk and (old_left > 0 or new_left > 0) and line[:1] in "+-":
            if line.startswith("+"):
                new_left -= 1
            else:
                old_left -= 1
            continue
        if line.startswith("@@"):
            match = HUNK_RE.match(line)
            if match is None:
                raise StopRuleError(f"live diff has a malformed hunk header: {line!r}")
            old_left = int(match.group(2)) if match.group(2) is not None else 1
            new_left = int(match.group(4)) if match.group(4) is not None else 1
            in_hunk = True
            kept.append(line)
            continue
        if line.startswith("\\"):
            continue
        if line.startswith(SURFACE_HEADER_PREFIXES):
            in_hunk = False
            kept.append(line)
            continue
        raise StopRuleError(f"live diff has an unexpected line outside hunks: {line[:60]!r}")
    if not kept:
        # Идентичные деревья: git выдаёт ноль байт, и проекция обязана быть
        # ровно пустой — иначе пустая улика не сверится байт в байт (r20).
        return ""
    return "\n".join(kept) + "\n"


def validate_surface_evidence(surface, round_id: str, root: Path,
                              baseline_tree: str | None) -> dict | None:
    """Улика поверхности раунда: класс, проекция, деревья, sha, разбор hunks.

    Если оба дерева живы в объектной базе — проекция пересчитывается и
    сверяется с архивом; расхождение — отказ. Без объектов улика
    непроверяема (клон без loose-объектов), и это считается отдельно.
    """
    if surface is None:
        return None
    if not isinstance(surface, dict):
        raise StopRuleError(f"round {round_id}: surface must be an object")
    if surface.get("class") not in SURFACE_CLASSES:
        raise StopRuleError(
            f"round {round_id}: surface.class must be one of {SURFACE_CLASSES}"
        )
    projection = surface.get("projection")
    if projection not in SURFACE_PROJECTIONS:
        raise StopRuleError(
            f"round {round_id}: surface.projection must be one of {SURFACE_PROJECTIONS}"
        )
    for field in ("baseTree", "candidateTree"):
        value = surface.get(field)
        if not isinstance(value, str) or not TREE_ID_RE.fullmatch(value):
            raise StopRuleError(
                f"round {round_id}: surface.{field} must be a 40-hex git tree id"
            )
    if baseline_tree is None:
        raise StopRuleError(
            f"round {round_id}: surface evidence needs history.surfaceBaseline.tree — "
            f"без базы серии «добавленная поверхность» не определена"
        )
    if surface["baseTree"] != baseline_tree:
        raise StopRuleError(
            f"round {round_id}: surface.baseTree {surface['baseTree'][:12]} is not the "
            f"series baseline {baseline_tree[:12]} — диффы от разных баз несравнимы"
        )
    rel = surface.get("path")
    artifact = repository_artifact(rel, round_id, root, "surface evidence")
    declared_sha = surface.get("sha256")
    # Байты читаются ОДИН раз: хеш, пересчёт и разбор судят один и тот же
    # буфер — повторное открытие давало окно подмены между ними (pub1).
    payload = artifact.read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if not isinstance(declared_sha, str) or declared_sha != actual_sha:
        raise StopRuleError(
            f"round {round_id}: surface sha256 mismatch for {rel}\n"
            f"  declared={declared_sha!r}\n  actual={actual_sha!r}"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Байты вне UTF-8 — отказ, а не подмена «replacement»-символами:
        # подменённая проекция участвовала бы в сопоставлении путей (r14).
        raise StopRuleError(
            f"round {round_id}: surface evidence {rel} is not valid UTF-8: {exc}"
        ) from exc
    added = parse_diff_surface(text, projection=projection,
                               where=f"round {round_id} surface {rel}")
    verified = None
    # Оба объекта судятся НЕЗАВИСИМО (без короткого замыкания): отсутствующая
    # база не освобождает дерево кандидата от проверки типа (r6, контур).
    base_live = require_live_tree(root, surface["baseTree"], f"round {round_id} surface.baseTree")
    candidate_live = require_live_tree(root, surface["candidateTree"],
                                       f"round {round_id} surface.candidateTree")
    if base_live and candidate_live:
        recomputed = surface_projection(root, surface["baseTree"],
                                        surface["candidateTree"], projection)
        if hashlib.sha256(recomputed.encode("utf-8")).hexdigest() != actual_sha:
            raise StopRuleError(
                f"round {round_id}: surface evidence {rel} does not match the "
                f"projection recomputed from the live trees — архив подложен "
                f"или снят другой командой"
            )
        verified = True
    else:
        verified = False
    return {
        "added": added,
        "projection": projection,
        "path": rel,
        "candidateTree": surface["candidateTree"],
        "verifiedAgainstTrees": verified,
    }


def report_findings(document: dict, round_id: str, rel: str) -> tuple[list, object]:
    """Находки и вердикт отчёта — плоского или иерархического.

    Иерархический маршрут продюсера пишет `unitCalls[].report` и
    `integrationReport`; находки объединяются и дедуплицируются по
    (file, line, category, summary), вердикт берётся из интеграции.
    Проход интеграции не имеет права стирать улику юнита — union, не выбор.
    """
    if "unitCalls" in document or "integrationReport" in document:
        integration = document.get("integrationReport")
        if not isinstance(integration, dict):
            raise StopRuleError(
                f"round {round_id}: hierarchical report needs integrationReport as an "
                f"object: {rel}"
            )
        calls = document.get("unitCalls")
        if not isinstance(calls, list):
            raise StopRuleError(
                f"round {round_id}: hierarchical report needs unitCalls as a list: {rel}"
            )
        sources = [("integrationReport", integration)]
        for index, call in enumerate(calls):
            if not isinstance(call, dict) or not isinstance(call.get("report"), dict):
                raise StopRuleError(
                    f"round {round_id}: unitCalls[{index}].report must be an object: {rel}"
                )
            sources.append((f"unitCalls[{index}].report", call["report"]))
        merged: list = []
        seen: set = set()
        for label, report in sources:
            findings = report.get("findings")
            if findings is None:
                findings = []
            if not isinstance(findings, list):
                raise StopRuleError(
                    f"round {round_id}: {label}.findings must be a list: {rel}"
                )
            for position, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    raise StopRuleError(
                        f"round {round_id}: {label} finding #{position} is not an object"
                    )
                line_value = finding.get("line")
                # Тип входит в ключ: Python считает True == 1, и невалидная
                # булева строка пряталась бы за валидной единицей (r1).
                key = (finding.get("file"), type(line_value).__name__, line_value,
                       finding.get("category"), finding.get("summary"))
                try:
                    hash(key)
                except TypeError as exc:
                    raise StopRuleError(
                        f"round {round_id}: {label} finding #{position} has "
                        f"unhashable fields"
                    ) from exc
                if key in seen:
                    continue
                seen.add(key)
                merged.append(finding)
        return merged, integration.get("verdict")
    findings = document.get("findings")
    if findings is None:
        findings = []
    if not isinstance(findings, list):
        raise StopRuleError(
            f"round {round_id}: report findings must be a list: {rel}"
        )
    return findings, document.get("verdict")


def validate_provenance(provenance: dict, terminal: str, round_id: str,
                        root: Path) -> Path | None:
    """Единственная точка проверки провенанса — ДО ветвления по классу терминала.

    Прежняя форма разводила проверки по отдельным ранним выходам для каждой
    комбинации (терминал x провенанс), и каждая новая комбинация давала новую
    щель: пересказ без строки, нев-вердиктный раунд с классом report, он же с
    классом narrative. Три находки независимого ревьюера в одном классе — это
    отказ формы, а не три отдельных дефекта, поэтому проверка сведена в одно
    место, а ветвление ниже решает только, ЧТО извлекать.
    """
    provenance_class = provenance.get("class")
    # Членство проверяется и ЗДЕСЬ, а не только в read_round: внутренняя функция
    # не имеет права полагаться на дисциплину вызывающего. Находка r19 про класс
    # "forged" не воспроизвелась через публичный вход (read_round отвергает до
    # этой точки), но её defense-in-depth часть честна — без этой проверки новый
    # вызывающий унаследовал бы открытую else-ветку.
    if provenance_class not in PROVENANCE_CLASSES:
        raise StopRuleError(
            f"round {round_id}: provenance.class must be one of {PROVENANCE_CLASSES}"
        )
    if provenance_class == "absent":
        if terminal == "verdict":
            raise StopRuleError(
                f"round {round_id}: a verdict round cannot have absent provenance — "
                f"вердикт это суждение о содержании кандидата, и он обязан быть "
                f"опёрт хотя бы на цитату записи. Если содержание раунда не "
                f"сохранилось, объяви пересказ с документом и строкой и пометь "
                f"contentRecorded=false с основанием."
            )
        return None
    if terminal != "verdict":
        if provenance_class == "report":
            raise StopRuleError(
                f"round {round_id}: terminal class {terminal!r} cannot claim report "
                f"provenance — машинной уликой является отчёт ревьюера, а суждения "
                f"о кандидате в этом раунде нет"
            )
        # Пересказ у нев-вердиктного раунда допустим (журнал сессии описывает и
        # срывы маршрута), но проверяется ровно так же строго.
        validate_narrative_provenance(provenance, round_id, root)
        return None
    if provenance_class == "report":
        return validate_report_provenance(provenance, round_id, root)
    validate_narrative_provenance(provenance, round_id, root)
    return None


def read_round(entry: dict, index: int, policy: dict, root: Path,
               baseline_tree: str | None = None) -> dict:
    """Разобрать один раунд, вернув нормализованную запись.

    Всё, что нельзя проверить, останавливает разбор: молчаливый пропуск
    раунда — это тот же false-green, только в бухгалтерии ревью.
    """
    if not isinstance(entry, dict):
        raise StopRuleError(f"round #{index} is not an object")
    round_id = entry.get("id")
    if not isinstance(round_id, str) or not round_id.strip():
        raise StopRuleError(f"round #{index} has no id")

    terminal = entry.get("terminal")
    if terminal not in TERMINAL_CLASSES:
        raise StopRuleError(
            f"round {round_id}: terminal must be one of {TERMINAL_CLASSES}, "
            f"got {terminal!r} — смешанный подсчёт заходов запрещён по построению"
        )

    provenance = entry.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("class") not in PROVENANCE_CLASSES:
        raise StopRuleError(
            f"round {round_id}: provenance.class must be one of {PROVENANCE_CLASSES}"
        )
    provenance_class = provenance["class"]

    candidate = entry.get("candidate")
    if candidate is not None and (
            not isinstance(candidate, str) or not CANDIDATE_IDENTITY_RE.fullmatch(candidate)):
        # Любая непустая строка личностью не является: две выдуманные строки
        # выглядели бы как доказанная смена кандидата и ложно взводили бы
        # REDESIGN_OR_DISCARD (находка ревьюера, раунд r19). Формат — ровно то,
        # что печатает candidate_identity_from_ledger: 16 строчных hex.
        raise StopRuleError(
            f"round {round_id}: candidate identity must be 16 lowercase hex digits "
            f"(the exact output of candidate_identity_from_ledger), got {candidate!r}"
        )

    # Провенанс судится один раз, для любого раунда, до всякого ветвления.
    artifact = validate_provenance(provenance, terminal, round_id, root)
    surface_entry = entry.get("surface")
    if surface_entry is not None and terminal != "verdict":
        raise StopRuleError(
            f"round {round_id}: terminal class {terminal!r} cannot carry surface "
            f"evidence — поверхность судится только в вердикт-раунде"
        )
    surface = validate_surface_evidence(surface_entry, round_id, root, baseline_tree)

    record = {
        "id": round_id,
        "terminal": terminal,
        "provenance": provenance_class,
        "verdict": None,
        "findings": [],
        "contentAvailable": provenance_class != "absent",
        "candidate": candidate,
        "surface": surface,
        "note": entry.get("note", ""),
    }

    if provenance_class == "absent" or terminal != "verdict":
        # Содержания либо нет в записи, либо суждения о кандидате в этом раунде
        # не было. Исход всё равно судится по словарю СВОЕГО класса.
        record["verdict"] = validated_outcome(entry, terminal, policy, round_id)
        return record

    if artifact is not None:
        try:
            document = json.loads(artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StopRuleError(
                f"round {round_id}: report is not valid JSON: {provenance['path']}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise StopRuleError(
                f"round {round_id}: report root must be an object: {provenance['path']}"
            )
        findings, verdict = report_findings(document, round_id, provenance["path"])
        parsed = []
        for position, finding in enumerate(findings):
            if not isinstance(finding, dict):
                raise StopRuleError(
                    f"round {round_id}: finding #{position} is not an object"
                )
            parsed.append({
                "file": finding.get("file"),
                "line": finding_line(finding.get("line"), round_id, position),
                "category": finding.get("category"),
                "severity": finding.get("severity"),
                "summary": (finding.get("summary") or "")[:400],
            })
        for finding_index, flags in apply_dispositions(entry, len(parsed), round_id):
            parsed[finding_index].update(flags)
        record["verdict"] = verdict
        record["findings"] = parsed
    else:
        declared = entry.get("declared")
        if not isinstance(declared, dict):
            raise StopRuleError(
                f"round {round_id}: narrative provenance needs a declared verdict block"
            )
        record["verdict"] = declared.get("verdict")
        content_recorded = declared.get("contentRecorded", True)
        if not isinstance(content_recorded, bool):
            raise StopRuleError(
                f"round {round_id}: declared.contentRecorded must be a boolean"
            )
        if not content_recorded:
            if not str(declared.get("why") or "").strip():
                raise StopRuleError(
                    f"round {round_id}: contentRecorded=false needs why — почему "
                    f"содержание раунда не сохранилось"
                )
            if declared.get("mechanisms"):
                raise StopRuleError(
                    f"round {round_id}: contentRecorded=false cannot also declare "
                    f"mechanisms — либо содержание есть, либо его нет"
                )
            record["contentAvailable"] = False
            allowed = verdict_values(policy)
            if record["verdict"] not in allowed:
                raise StopRuleError(
                    f"round {round_id}: verdict {record['verdict']!r} is not one of {allowed}"
                )
            return record
        mechanisms = declared.get("mechanisms")
        if not isinstance(mechanisms, list):
            raise StopRuleError(
                f"round {round_id}: narrative round must declare mechanisms as a list"
            )
        for position, mechanism in enumerate(mechanisms):
            if (not isinstance(mechanism, dict)
                    or not str(mechanism.get("surface") or "").strip()
                    or not str(mechanism.get("defectClass") or "").strip()):
                raise StopRuleError(
                    f"round {round_id}: mechanism #{position} needs surface and defectClass"
                )
            for flag in ("regression", "refuted"):
                if flag not in mechanism:
                    continue
                if not isinstance(mechanism[flag], bool):
                    raise StopRuleError(
                        f"round {round_id}: mechanism #{position} field {flag!r} "
                        f"must be a boolean"
                    )
                if mechanism[flag] and not str(mechanism.get("why") or "").strip():
                    raise StopRuleError(
                        f"round {round_id}: mechanism #{position} sets {flag} without "
                        f"why — снятие находки со счёта повторов без основания это "
                        f"и есть подкраска"
                    )
            record["findings"].append({
                "file": mechanism["surface"],
                "line": finding_line(mechanism.get("line"), round_id, position),
                "category": mechanism["defectClass"],
                "severity": mechanism.get("severity"),
                "summary": (mechanism.get("summary") or "")[:400],
                "narrative": True,
                "regression": bool(mechanism.get("regression")),
                "refuted": bool(mechanism.get("refuted")),
            })

    allowed = verdict_values(policy)
    if record["verdict"] not in allowed:
        raise StopRuleError(
            f"round {round_id}: verdict {record['verdict']!r} is not one of {allowed}"
        )
    if record["verdict"] == "BLOCKED" and not record["findings"]:
        raise StopRuleError(
            f"round {round_id}: BLOCKED without findings — нечего классифицировать"
        )
    return record


ORDER_PROVENANCE_CLASSES = ("artifact-list", "recorded-document")


def validate_order_provenance_shape(document: dict, where) -> dict:
    """Форма orderProvenance — одна проверка для load_history и decide.

    decide() принимает и не сериализованные истории (реплей, синтетика
    оракула), поэтому полагаться только на load_history нельзя: история,
    пришедшая мимо него, обходила бы требование машинного источника порядка.
    """
    order = document.get("orderProvenance")
    if not isinstance(order, dict) or order.get("class") not in ORDER_PROVENANCE_CLASSES:
        raise StopRuleError(
            f"history must declare orderProvenance.class as one of "
            f"{ORDER_PROVENANCE_CLASSES}: {where}\n"
            f"  artifact-list — порядок зафиксирован самим списком rounds, чьи "
            f"артефакты лежат в дереве и проверяются пораундовым провенансом;\n"
            f"  recorded-document — порядок восстановлен вне артефактов (например "
            f"из host-local mtime) и зафиксирован списком, а записанный документ "
            f"серии объявляется полями path/line и проверяется машинно."
        )
    if order["class"] == "recorded-document":
        if not isinstance(order.get("path"), str) or not order["path"].strip():
            raise StopRuleError(
                f"orderProvenance.class=recorded-document needs path: {where}"
            )
        if not isinstance(order.get("line"), int) or isinstance(order.get("line"), bool):
            raise StopRuleError(
                f"orderProvenance.class=recorded-document needs an integer line: {where}"
            )
    return order

DIFF_MARKERS = ("REVIEW DIFF", "DIFF UNIT")


def require_unit_identifier(value, what: str) -> str:
    """Идентификатор юнита обязан быть непустой строкой — ОДНИМ валидатором.

    Класс «поле привязки не типизировано» ломался дважды: r25 нашёл его на
    replay-пути (check_policy_binding принимал произвольные равные строки),
    r32 — на live-пути (str(None) давал "None", и критерий с id "None"
    выравнивал привязку без активного юнита). По собственному правилу это
    повтор механизма, поэтому меняется форма: оба пути зовут этот валидатор,
    и новый путь чтения привязки не может пропустить типизацию иначе как
    мимо него.
    """
    if not isinstance(value, str) or not value.strip():
        raise StopRuleError(f"{what} must be a non-empty string, got {value!r}")
    return value


def read_json_document(path: Path, what: str) -> dict:
    """Единственная точка чтения JSON-документов правила — fail-closed.

    Класс «точка чтения входа не завёрнута» ломался дважды: r25 нашёл
    незащищённое разыменование секций в load_policy, r31 — сырые json.loads в
    live_policy_binding, ронявшие --check-binding трейсбэком на битом файле.
    По собственному правилу это повтор механизма, поэтому меняется форма:
    каждое чтение идёт через эту функцию, и новая точка чтения не может
    появиться незавёрнутой иначе как мимо неё.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StopRuleError(f"{what} is unreadable: {path}: {exc}") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StopRuleError(f"{what} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise StopRuleError(f"{what} root must be an object: {path}")
    return document

CANDIDATE_IDENTITY_RE = re.compile(r"[0-9a-f]{16}")

LEDGER_SUFFIXES = ("-prompt.md.ledger.jsonl", "-prompt-1.md.ledger.jsonl",
                   "-prompt-2.md.ledger.jsonl")


def round_ledger_path(source: dict, round_id: str, root: Path) -> Path | None:
    """Журнал промптов раунда по объявленному candidateSource, если он на хосте.

    Одна реализация на правило и оракул: две копии поиска разошлись бы молча,
    и сверка личностей смотрела бы не в те файлы, что пересчёт.
    """
    prefix = str(source.get("prefix") or "").strip()
    directories = source.get("directories")
    if not prefix or not isinstance(directories, list):
        return None
    resolved_root = root.resolve()
    for directory in directories:
        if not isinstance(directory, str) or not directory.strip():
            continue
        for suffix in LEDGER_SUFFIXES:
            probe = (root / directory / f"{prefix}-{round_id}{suffix}").resolve()
            # Каталоги и префикс приходят из НЕДОВЕРЕННОЙ истории: абсолютный
            # путь или traversal читал бы и хешировал файлы вне репозитория —
            # та же граница, что у report/narrative-провенанса (находка
            # ревьюера, раунд r33).
            try:
                probe.relative_to(resolved_root)
            except ValueError as exc:
                raise StopRuleError(
                    f"candidateSource escapes the repository root: {probe}"
                ) from exc
            if probe.is_file():
                return probe
    return None


def verify_declared_candidates(history: dict, root: Path) -> dict:
    """Сверить объявленные личности кандидатов с журналами промптов на хосте.

    Несовпадение — отказ, а не предупреждение: объявленная личность, которую
    журнал опровергает, означает подложную или протухшую запись, и решение о
    повторе по ней было бы решением по выдумке (находка ревьюера, раунд r19).
    Отсутствие журнала отказом НЕ является: журналы принадлежат хосту и
    git-ignored, в изолированном дереве машинной ноги их нет по построению —
    требовать их значило бы сделать реплей false-red (класс LPD-003-1).
    Счёт проверенных и непроверяемых личностей возвращается и печатается.
    """
    source = history.get("candidateSource")
    counts = {"declared": 0, "verified": 0, "unverifiable": 0}
    if isinstance(source, dict) and source.get("kind") == "reviewed-tree":
        return verify_reviewed_tree_candidates(history, root, counts)
    if not isinstance(source, dict) or source.get("kind") != "prompt-ledger-diff-sha256":
        return counts
    for entry in history.get("rounds") or []:
        if not isinstance(entry, dict):
            continue
        declared = entry.get("candidate")
        if not isinstance(declared, str) or not declared.strip():
            # Вердикт-раунд БЕЗ объявленной личности при ДОСТУПНОМ журнале —
            # отказ: журнал доказывает личность, и умолчание истории тихо
            # деградировало бы доказуемый повтор в RECURRENCE_UNCONFIRMED
            # (находка ревьюера, раунд r26). Нев-вердиктные раунды личность
            # не несут по построению.
            if entry.get("terminal") == "verdict":
                withheld = round_ledger_path(source, str(entry.get("id")), root)
                if withheld is not None:
                    raise StopRuleError(
                        f"round {entry.get('id')}: a prompt ledger is available "
                        f"({withheld}) but the history declares no candidate "
                        f"identity — бухгалтерия неконсистентна"
                    )
            continue
        counts["declared"] += 1
        ledger = round_ledger_path(source, str(entry.get("id")), root)
        if ledger is None:
            counts["unverifiable"] += 1
            continue
        computed = candidate_identity_from_ledger(ledger)
        if computed != declared:
            raise StopRuleError(
                f"round {entry.get('id')}: declared candidate identity {declared!r} "
                f"does not match the ledger-derived {computed!r} from {ledger}"
            )
        counts["verified"] += 1
    return counts


def verify_reviewed_tree_candidates(history: dict, root: Path, counts: dict) -> dict:
    """Личность кандидата = 16-hex префикс reviewedTree машинной квитанции.

    Она обязана совпадать с surface.candidateTree того же раунда — иначе
    бухгалтерия внутренне противоречива. Живое дерево в объектной базе
    подтверждает личность; на клоне без loose-объектов она непроверяема,
    и это считается, а не замалчивается.
    """
    for entry in history.get("rounds") or []:
        if not isinstance(entry, dict):
            continue
        declared = entry.get("candidate")
        if not isinstance(declared, str) or not declared.strip():
            if isinstance(entry.get("surface"), dict):
                # Улика поверхности несёт candidateTree, значит личность
                # выводима — умолчание было бы несогласованной бухгалтерией (pub1).
                raise StopRuleError(
                    f"round {entry.get('id')}: surface evidence names a candidateTree "
                    f"but the round declares no candidate identity"
                )
            continue
        counts["declared"] += 1
        if not CANDIDATE_IDENTITY_RE.fullmatch(declared):
            # Проверяется и здесь, не только в read_round: функция не имеет
            # права полагаться на дисциплину вызывающего (класс r19).
            raise StopRuleError(
                f"round {entry.get('id')}: candidate identity must be 16 lowercase "
                f"hex digits, got {declared!r}"
            )
        surface = entry.get("surface")
        tree = surface.get("candidateTree") if isinstance(surface, dict) else None
        if not isinstance(tree, str) or not tree.startswith(declared):
            raise StopRuleError(
                f"round {entry.get('id')}: candidate identity {declared!r} is not the "
                f"prefix of the round's surface.candidateTree {tree!r} — личность "
                f"kind=reviewed-tree выводится из улики поверхности, а не объявляется"
            )
        if require_live_tree(root, tree, f"round {entry.get('id')} surface.candidateTree"):
            counts["verified"] += 1
        else:
            counts["unverifiable"] += 1
    return counts


def candidate_identity_from_ledger(path: Path, digits: int = 16) -> str | None:
    """Личность кандидата = хеш ТОЛЬКО участков диффа в журнале промптов.

    Хешировать журнал целиком нельзя: в нём лежит и обёртка промпта —
    инструкции ревьюеру, схема вердикта, объявления покрытия. Обёртка меняется
    от правок маршрута, а не кандидата, и тогда неизменный кандидат выглядел бы
    изменившимся, а невыясненный повтор ложно взводил бы REDESIGN_OR_DISCARD
    (находка независимого ревьюера, раунд r14).

    Берутся байты между BEGIN/END UNTRUSTED <маркер> в порядке следования
    записей; записи-интеграции диффа не несут и в хеш не входят. None, если
    журнала нет или в нём не нашлось ни одного участка диффа: выдумывать
    личность из пустоты правило не станет.
    """
    if not path.is_file():
        return None
    segments: list[str] = []
    for line in path.open("r", encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return None
        prompt = entry.get("prompt")
        if not isinstance(prompt, str):
            continue
        # Оба вида маркеров ищутся ОДНИМ сканом по позиции появления: обход
        # «сначала все REVIEW DIFF, потом все DIFF UNIT» дал бы журналу со
        # смешанными формами другой порядок сегментов и другую личность —
        # контракт «хеш сегментов в порядке следования» нарушался бы молча
        # (находка ревьюера, раунд r31).
        cursor = 0
        while True:
            found = None
            for marker in DIFF_MARKERS:
                opening = f"BEGIN UNTRUSTED {marker}\n"
                start = prompt.find(opening, cursor)
                if start >= 0 and (found is None or start < found[0]):
                    found = (start, marker, opening)
            if found is None:
                break
            start, marker, opening = found
            start += len(opening)
            closing = f"END UNTRUSTED {marker}\n"
            end = prompt.find(closing, start)
            if end < 0:
                # Открывающий маркер без закрывающего — отказ, а не обрыв
                # набора: хеш частичного набора связывал бы личность не со
                # всем кандидатом, а молчаливый None превращал бы порчу
                # журнала в «личность не установлена» и пропускал сверку
                # (находка ревьюера, раунд r24).
                raise StopRuleError(
                    f"prompt ledger {path} has an unterminated "
                    f"BEGIN UNTRUSTED {marker} segment"
                )
            segments.append(prompt[start:end])
            cursor = end + len(closing)
    if not segments:
        return None
    digest = hashlib.sha256()
    for segment in segments:
        digest.update(segment.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:digits]


def canonical_key_part(value: str, *, fold: bool) -> str:
    """Каноническая форма составляющей ключа механизма.

    Обрезаются краевые пробелы и схлопываются внутренние: ключ обязан зависеть
    от НАЗВАННОГО механизма, а не от того, как ревьюер расставил пробелы.
    Категория дополнительно приводится к нижнему регистру — это ярлык класса
    дефекта, и `Security` с `security` называют одно и то же. Путь файла НЕ
    сворачивается по регистру: на регистрозависимой файловой системе `A.py` и
    `a.py` — разные файлы, и склеивать их значило бы объявлять повтор там, где
    его нет.

    Нормализация всегда СЛИВАЕТ написания и никогда не разделяет — то же
    направление, что у mergeKeys, поэтому обойти повтор перезаписью нельзя.
    """
    collapsed = " ".join(value.split())
    return collapsed.casefold() if fold else collapsed


def normalized_key(file_part: str, category_part: str) -> tuple[str, str]:
    """Единственная точка построения ключа — и для находок, и для mergeKeys.

    Две копии этой нормализации разошлись бы молча: объявленное слияние
    перестало бы совпадать с ключом находки, и повтор снова стал бы невидим.
    """
    return (canonical_key_part(file_part, fold=False),
            canonical_key_part(category_part, fold=True))


def raw_key(finding: dict) -> tuple[str, str] | None:
    """Ключ механизма или None, если находка не назвала ни поверхность, ни класс.

    Безымянные находки НЕ склеиваются в один псевдо-механизм: иначе несколько
    отчётов без file/category давали бы ложный повтор и правило остановило бы
    маршрут на пустом месте (замер: пять таких отчётов в серии GPG-001
    broker-policy).

    Возвращается КАНОНИЧЕСКАЯ форма. Прежняя версия проверяла непустоту через
    `.strip()`, но отдавала строки как есть, поэтому `" security"` и
    `"security"` были разными механизмами и повтор не опознавался — вместо
    REDESIGN_OR_DISCARD правило говорило CONTINUE (находка ревьюера, раунд r18).
    """
    file_part = finding.get("file")
    category_part = finding.get("category")
    if not isinstance(file_part, str) or not file_part.strip():
        return None
    if not isinstance(category_part, str) or not category_part.strip():
        return None
    return normalized_key(file_part, category_part)


def build_merge_map(history: dict) -> dict:
    """Объединения ключей — только СЛИЯНИЕ, никогда разделение.

    Разделение позволило бы снять повтор переименованием категории, то есть
    ровно тем действием, против которого правило и написано.
    """
    groups = history.get("mergeKeys") or []
    if not isinstance(groups, list):
        raise StopRuleError("mergeKeys must be a list of groups")
    mapping: dict[tuple[str, str], str] = {}
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise StopRuleError(f"mergeKeys[{index}] must be an object")
        label = group.get("label")
        members = group.get("members")
        if not isinstance(label, str) or not label.strip():
            raise StopRuleError(f"mergeKeys[{index}] needs a label")
        if not isinstance(members, list) or len(members) < 2:
            raise StopRuleError(
                f"mergeKeys[{index}] ({label}) needs at least two members: "
                f"группа из одного ключа — это переименование, а не слияние"
            )
        seen_members: set[tuple[str, str]] = set()
        for member in members:
            if (not isinstance(member, list) or len(member) != 2
                    or not all(isinstance(part, str) and part.strip() for part in member)):
                raise StopRuleError(
                    f"mergeKeys[{index}] ({label}) member must be a [file, category] pair"
                )
            # Та же каноническая форма, что у находок: иначе объявленный член
            # `" security"` не совпал бы с ключом находки `"security"`, и
            # слияние молча не применилось бы. Проверка повтора членов идёт
            # ПОСЛЕ нормализации — два написания одного ключа группой из двух
            # не делают.
            key = normalized_key(member[0], member[1])
            if key in seen_members:
                raise StopRuleError(
                    f"mergeKeys[{index}] ({label}) repeats member {key} — повтор "
                    f"одного ключа не делает группу слиянием двух"
                )
            seen_members.add(key)
            if key in mapping and mapping[key] != label:
                raise StopRuleError(
                    f"mechanism key {key} is claimed by two groups "
                    f"({mapping[key]!r} and {label!r}) — это РАЗДЕЛЕНИЕ ключа, "
                    f"а политика допускает только слияние"
                )
            mapping[key] = label
    return mapping


def mechanism_of(finding: dict, merge_map: dict) -> str | None:
    key = raw_key(finding)
    if key is None:
        return None
    if key in merge_map:
        return merge_map[key]
    return f"{key[0]}::{key[1]}"


def is_regression(finding: dict) -> bool:
    return bool(finding.get("regression"))


def is_refuted(finding: dict) -> bool:
    """Опровергнутая находка не свидетельствует ни о чём и в повторы не идёт."""
    return bool(finding.get("refuted"))


# --------------------------------------------------------------------------
# решение
# --------------------------------------------------------------------------

def check_policy_binding(history: dict, policy: dict, root: Path) -> dict | None:
    """R3: вердикты, вынесенные по политике чужого юнита, не свидетельство.

    Для реплея записанной истории привязка объявлена в самой истории; для
    живого прогона она читается из двух леджеров.
    """
    binding = history.get("policyBinding")
    if binding is None:
        return None
    if not isinstance(binding, dict):
        raise StopRuleError("policyBinding must be an object")
    for field in ("ledgerUnit", "contractUnit", "criteriaPresent"):
        if field not in binding:
            raise StopRuleError(f"policyBinding has no {field!r}")
    for field in ("ledgerUnit", "contractUnit"):
        require_unit_identifier(binding[field], f"policyBinding.{field}")
    # Привязка обязана называть юнит СВОЕЙ истории: без этой сверки история
    # активного юнита могла объявить пару одинаковых чужих строк с
    # criteriaPresent=true и обойти ROUTE_DEFECT — вердикты чужой бухгалтерии
    # интерпретировались бы как свои (находка ревьюера, раунд r25).
    history_unit = str(history.get("unit") or "")
    ledger_unit = binding["ledgerUnit"]
    # Имя истории — либо сам юнит, либо серия юнита (<unitId>-<суффикс>): та же
    # дефисная граница, что у критериев приёмки. Голый startswith считал бы
    # историю LPD003-30 серией юнита LPD003-3.
    if history_unit != ledger_unit and not history_unit.startswith(ledger_unit + "-"):
        raise StopRuleError(
            f"policyBinding.ledgerUnit {ledger_unit!r} does not name this "
            f"history's unit {history_unit!r} (ни сам юнит, ни его серия)"
        )
    if not isinstance(binding["criteriaPresent"], bool):
        raise StopRuleError(
            "policyBinding.criteriaPresent must be a boolean — истинное значение "
            "любого типа (непустая строка, список) подавляло бы ROUTE_DEFECT, "
            "ничего не устанавливая"
        )
    mismatch = binding["ledgerUnit"] != binding["contractUnit"]
    missing = not binding["criteriaPresent"]
    if not (mismatch or missing):
        return None
    reasons = []
    if mismatch:
        reasons.append(
            f"контракт приёмки вёл ревью по юниту {binding['contractUnit']!r}, "
            f"а активным был {binding['ledgerUnit']!r}"
        )
    if missing:
        reasons.append(
            f"критериев с префиксом активного юнита в контракте не существовало"
        )
    return {
        "why": "; ".join(reasons),
        "contractUnit": binding["contractUnit"],
        "ledgerUnit": binding["ledgerUnit"],
    }


def live_policy_binding(policy: dict, root: Path) -> dict:
    """Живая проверка привязки: два леджера читаются с диска."""
    binding_policy = policy["policyBinding"]
    contract_path = root / binding_policy["contractPath"]
    ledger_path = root / binding_policy["ledgerPath"]
    if not contract_path.is_file():
        raise StopRuleError(f"acceptance contract is missing: {contract_path}")
    if not ledger_path.is_file():
        raise StopRuleError(f"state ledger is missing: {ledger_path}")
    contract = read_json_document(contract_path, "acceptance contract")
    ledger = read_json_document(ledger_path, "state ledger")
    contract_unit = require_unit_identifier(
        (contract.get("activeFollowup") or {}).get("unitId"),
        "activeFollowup.unitId")
    ledger_unit = require_unit_identifier(
        (ledger.get("currentUnit") or {}).get("id"),
        "currentUnit.id")
    # Префикс сравнивается по границе идентификатора: голый startswith считал бы
    # критерии юнита LPD003-30 своими для активного LPD003-3.
    unit_prefix = ledger_unit
    criteria = [c for c in (contract.get("criteria") or [])
                if str(c.get("id", "")) == unit_prefix
                or str(c.get("id", "")).startswith(unit_prefix + "-")]
    # Значение заморожено load_policy; читается отсюда, чтобы объявленное в
    # политике и применяемое в коде оставались ОДНИМ фактом, а не двумя.
    wanted = binding_policy["requireCriteriaStatus"]
    passed = [c for c in criteria if c.get("status") == wanted]
    # Требуемый статус критериев объявлен политикой и потому обязан входить в
    # вердикт привязки: продюсер отказывает терминалом класса precondition, если
    # критерий активного юнита ещё pending, — значит «выровнено» при pending
    # было бы обещанием, которого маршрут не сдержит.
    status_satisfied = bool(criteria) and len(passed) == len(criteria)
    return {
        "ledgerUnit": ledger_unit,
        "contractUnit": contract_unit,
        "criteriaPresent": bool(criteria),
        "criteriaMatchingStatus": len(passed),
        "criteriaTotal": len(criteria),
        "requiredCriteriaStatus": wanted,
        "statusSatisfied": status_satisfied,
        "aligned": contract_unit == ledger_unit and bool(criteria) and status_satisfied,
    }


def count_terminals(rounds: list[dict]) -> tuple[dict, dict]:
    """Счётчики классов по УЖЕ разобранным раундам.

    Отдельного облегчённого прохода больше нет. Он существовал ради истории с
    дефектом привязки, где содержание раундов не интерпретируется, — и ровно
    поэтому создавал щель: `decide()` возвращал ROUTE_DEFECT, ни разу не
    проверив провенанс. Разбор и ИНТЕРПРЕТАЦИЯ — разные вещи: судится всегда
    всё, а не используется — только то, что имеет смысл использовать.
    """
    counters = {"verdict": 0, "precondition": 0, "transport": 0}
    provenance_counters = {"report": 0, "narrative": 0, "absent": 0}
    for record in rounds:
        counters[record["terminal"]] += 1
        provenance_counters[record["provenance"]] += 1
    return counters, provenance_counters


def surface_baseline(history: dict) -> str | None:
    baseline = history.get("surfaceBaseline")
    if baseline is None:
        return None
    if not isinstance(baseline, dict):
        raise StopRuleError("surfaceBaseline must be an object")
    tree = baseline.get("tree")
    if not isinstance(tree, str) or not TREE_ID_RE.fullmatch(tree):
        raise StopRuleError("surfaceBaseline.tree must be a 40-hex git tree id")
    return tree


def evaluate_surface_treadmill(rounds: list[dict], policy: dict) -> dict:
    """R7: окно последних windowRounds вердикт-раундов с содержанием.

    Критерий взводится, только если каждый раунд окна BLOCKED, у каждого есть
    улика поверхности и КАЖДАЯ засчитанная находка (не regression, не refuted)
    имеет строку, лежащую в добавленных диапазонах своей улики. Любая
    недостающая улика или находка на исходной поверхности снимает критерий —
    fail-closed в сторону CONTINUE. Числа печатаются всегда.
    """
    window = int(policy["surfaceTreadmill"]["windowRounds"])
    per_round: list[dict] = []
    for record in rounds:
        if record["terminal"] != "verdict":
            continue
        # Раунд без сохранённого содержания ОСТАЁТСЯ в хронологическом окне:
        # выкинуть его значило бы подтянуть в хвост более старый BLOCKED и
        # взвести терминал мимо свежего PASSED (r9). Улики у него нет.
        surface = record.get("surface") if record["contentAvailable"] else None

        def locatable(finding: dict) -> bool:
            return (isinstance(finding.get("line"), int)
                    and isinstance(finding.get("file"), str))

        def on_surface(finding: dict) -> bool:
            return (surface is not None
                    and on_added_surface(surface["added"], finding.get("file"), finding.get("line")))

        findings = record["findings"] if record["contentAvailable"] else []
        # Диагностика считается по ВСЕМ находкам (знаменатель не зависит от
        # диспозиций — замер серии не переписывается опровержением), а
        # поддержка R7 — только по живым (не refuted, не regression).
        located = [finding for finding in findings if locatable(finding)]
        on_added = sum(1 for finding in located if on_surface(finding))
        live = [finding for finding in findings
                if not is_refuted(finding) and not is_regression(finding)]
        live_unlocated = sum(1 for finding in live if not locatable(finding))
        live_off_surface = sum(1 for finding in live
                               if locatable(finding) and not on_surface(finding))
        per_round.append({
            "round": record["id"],
            "verdict": record["verdict"],
            "content": record["contentAvailable"],
            "evidence": surface is not None,
            "projection": surface["projection"] if surface else None,
            "verifiedAgainstTrees": surface["verifiedAgainstTrees"] if surface else None,
            "counted": len(live),
            "located": len(located),
            "onAdded": on_added,
            "liveUnlocated": live_unlocated,
            "liveOffSurface": live_off_surface,
            "narrativeLines": bool(
                record["provenance"] == "narrative"
                and any(locatable(finding) for finding in findings)),
        })
    report = {
        "windowRounds": window,
        "rounds": per_round,
        "evaluated": False,
        "terminalArmed": False,
        "atRound": None,
        "why": "",
    }
    tail = per_round[-window:]
    if len(tail) < window:
        report["why"] = (
            f"вердикт-раундов с содержанием {len(per_round)} — меньше окна {window}"
        )
        return report
    missing = [item["round"] for item in tail if not item["evidence"]]
    if missing:
        report["why"] = (
            f"нет улики поверхности (или содержания) у раундов окна "
            f"{', '.join(missing)} — критерий не проверяем"
        )
        return report
    not_blocked = [item["round"] for item in tail if item["verdict"] != "BLOCKED"]
    if not_blocked:
        report["why"] = (
            f"в окне есть не-BLOCKED раунды {', '.join(not_blocked)} — поток "
            f"доходил до нуля, это не treadmill"
        )
        return report
    report["evaluated"] = True
    empty = [item["round"] for item in tail if item["counted"] == 0]
    off_surface = [
        f"{item['round']} {item['onAdded']}/{item['located']}"
        for item in tail
        if item["counted"] and (item["liveUnlocated"] or item["liveOffSurface"])
    ]
    if empty or off_surface:
        reasons = []
        if empty:
            reasons.append(
                f"без засчитанных находок (все опровергнуты или регрессии): "
                f"{', '.join(empty)} — потока в этом раунде нет"
            )
        if off_surface:
            reasons.append(
                f"находки вне добавленной поверхности или без строки: "
                f"{', '.join(off_surface)} — серия ещё судит исходный код"
            )
        report["why"] = "; ".join(reasons)
        return report
    report["terminalArmed"] = True
    report["atRound"] = tail[-1]["round"]
    report["why"] = (
        f"последние {window} вердиктов ({', '.join(item['round'] for item in tail)}) "
        f"все BLOCKED, и каждая их находка лежит в коде, добавленном самой серией"
    )
    return report


def decide(history: dict, policy: dict, root: Path) -> dict:
    # Разбор идёт ПЕРВЫМ и всегда: любой раунд любой истории проходит проверку
    # провенанса, исхода и содержания, даже если ниже выяснится, что вердикты
    # этой истории интерпретировать нельзя.
    baseline_tree = surface_baseline(history)
    rounds = [read_round(entry, index, policy, root, baseline_tree)
              for index, entry in enumerate(history["rounds"])]
    seen_ids: set[str] = set()
    for record in rounds:
        if record["id"] in seen_ids:
            raise StopRuleError(f"duplicate round id: {record['id']}")
        seen_ids.add(record["id"])
    counters, provenance_counters = count_terminals(rounds)
    attempts = len(rounds)
    # Сверка объявленных личностей с журналами — ДО интерпретации повторов:
    # решение о смене кандидата по опровергнутой журналом личности было бы
    # решением по выдумке. Несовпадение роняет разбор; отсутствие журнала —
    # host-owned класс, только счёт.
    identity_counts = verify_declared_candidates(history, root)
    order_provenance = validate_order_provenance_shape(history, history.get("unit"))
    if order_provenance.get("class") == "recorded-document":
        # Тот же валидатор, что у пересказа раундов: документ в дереве,
        # строка существует — источник порядка проверяется машинно, а не
        # принимается на слово (находка ревьюера, раунд r34).
        validate_narrative_provenance(
            {"class": "narrative", "path": order_provenance["path"],
             "line": order_provenance["line"]},
            "orderProvenance", root)

    decision = {
        "unit": history["unit"],
        "counters": counters,
        "provenance": provenance_counters,
        "candidateIdentities": identity_counts,
        "attempts": attempts,
        "orderSource": history["orderSource"],
        "regressions": [],
        "refuted": [],
        "unkeyable": [],
        "recurring": [],
        "contentMissing": [],
        "knownGaps": [dict(gap) for gap in history.get("knownGaps", [])],
        "terminal": None,
        "atRound": None,
        "why": "",
        "fix": "",
    }

    # R3 идёт первым: если ревью судило по политике чужого юнита, содержание
    # раундов о кандидате не свидетельствует и разбирать его нечестно.
    # Цифры поверхности считаются ВСЕГДА и печатаются при любом терминале,
    # включая ROUTE_DEFECT: это замер серии, а не только условие R7. Сам
    # терминал R7 применяется ниже, на своём месте в прецеденте.
    decision["surface"] = evaluate_surface_treadmill(rounds, policy)
    route_defect = check_policy_binding(history, policy, root)
    if route_defect is not None:
        decision["terminal"] = "ROUTE_DEFECT"
        decision["why"] = (
            "Приёмочная бухгалтерия не принадлежала активному юниту: "
            + route_defect["why"]
            + ". Вердикты этой истории вынесены по чужой политике ревью и о "
              "кандидате не свидетельствуют — раунды не разбираются."
        )
        decision["fix"] = (
            "Привести activeFollowup.unitId в .itd/ACCEPTANCE_CONTRACT.json к "
            "активному юниту леджера, завести критерии с его префиксом и "
            "перезапустить ревью. Прошлые раунды в счёт не идут."
        )
        decision["policyBinding"] = route_defect
        return decision

    decision["contentMissing"] = [
        record["id"] for record in rounds
        if record["terminal"] == "verdict" and not record["contentAvailable"]
    ]

    merge_map = build_merge_map(history)

    # ключ механизма -> упорядоченный список раундов, где он давал находки
    mechanism_rounds: dict[str, list[str]] = {}
    mechanism_candidates: dict[str, list[str | None]] = {}
    armed_at: str | None = None
    armed_mechanism: str | None = None
    unconfirmed_mechanism: str | None = None

    for record in rounds:
        if record["terminal"] != "verdict" or record["verdict"] != "BLOCKED":
            continue
        if not record["contentAvailable"]:
            continue
        seen_here: set[str] = set()
        for finding in record["findings"]:
            key = raw_key(finding)
            if is_refuted(finding):
                decision["refuted"].append({
                    "round": record["id"],
                    "surface": key[0] if key else None,
                    "class": key[1] if key else None,
                })
                continue
            if is_regression(finding):
                decision["regressions"].append({
                    "round": record["id"],
                    "surface": key[0] if key else None,
                    "class": key[1] if key else None,
                })
                continue
            mechanism = mechanism_of(finding, merge_map)
            if mechanism is None:
                decision["unkeyable"].append({
                    "round": record["id"],
                    "severity": finding.get("severity"),
                })
                continue
            if mechanism in seen_here:
                # Дубль внутри одного отчёта повтором не является.
                continue
            seen_here.add(mechanism)
            bucket = mechanism_rounds.setdefault(mechanism, [])
            bucket.append(record["id"])
            candidates = mechanism_candidates.setdefault(mechanism, [])
            candidates.append(record["candidate"])
            if len(bucket) < int(policy["mechanismKey"]["distinctRoundsRequired"]):
                continue
            # Сигналом является повтор ПОСЛЕ попытки фикса. Два независимых
            # ревью одного и того же неисправленного кандидата — это не повтор
            # механизма, а два взгляда на одну находку. Различие кандидатов
            # берётся из записи; если запись его не устанавливает, правило
            # обязано сказать это, а не выдать вердикт, которого не заслужило.
            distinct = {value for value in candidates if value}
            if len(distinct) >= 2:
                if armed_at is None:
                    armed_at = record["id"]
                    armed_mechanism = mechanism
            elif unconfirmed_mechanism is None and armed_at is None:
                unconfirmed_mechanism = mechanism

    decision["recurring"] = sorted(
        ({"mechanism": mechanism, "rounds": bucket,
          "distinctCandidates": len({value for value in mechanism_candidates[mechanism]
                                     if value})}
         for mechanism, bucket in mechanism_rounds.items() if len(bucket) >= 2),
        key=lambda item: item["mechanism"],
    )

    if armed_at is not None:
        decision["terminal"] = "REDESIGN_OR_DISCARD"
        decision["atRound"] = armed_at
        decision["mechanism"] = armed_mechanism
        rounds_of_armed = mechanism_rounds[armed_mechanism]
        decision["why"] = (
            f"Механизм {armed_mechanism} дал находки в раундах "
            f"{', '.join(rounds_of_armed)} — то есть после попытки фикса тот же "
            f"механизм сломался снова. Дефектна форма решения, а не экземпляр."
        )
        decision["fix"] = (
            "Остановиться и вынести решение владельцу: переделать механизм "
            "другой формой или выбросить правку целиком. Следующий раунд "
            "того же вида — это оплата того же дефекта ещё раз."
        )
        return decision

    if unconfirmed_mechanism is not None:
        decision["terminal"] = "RECURRENCE_UNCONFIRMED"
        decision["mechanism"] = unconfirmed_mechanism
        decision["atRound"] = mechanism_rounds[unconfirmed_mechanism][-1]
        decision["why"] = (
            f"Механизм {unconfirmed_mechanism} дал находки в раундах "
            f"{', '.join(mechanism_rounds[unconfirmed_mechanism])}, но запись не "
            f"устанавливает, что между ними менялся кандидат. Повтор ПОСЛЕ попытки "
            f"фикса и два взгляда на один неисправленный кандидат — разные вещи, и "
            f"по этой записи их не различить."
        )
        decision["fix"] = (
            "Дать раундам личность кандидата (поле candidate) из улик маршрута и "
            "перепрогнать правило. Пока её нет, решение принимает человек, глядя "
            "на сами находки."
        )
        return decision

    surface_report = decision["surface"]
    if surface_report["terminalArmed"]:
        decision["terminal"] = "SURFACE_TREADMILL"
        decision["atRound"] = surface_report["atRound"]
        decision["why"] = (
            "Ни один механизм не повторился, но " + surface_report["why"]
            + ": поток находок стабилен, а поверхность растёт с каждой правкой — "
              "серия оплачивает дефекты собственных правок, а не кандидата."
        )
        decision["fix"] = (
            "Остановиться: правило составляет диспозиции ADR-007 по BLOCKED-"
            "квитанции чекера (`--emit-dispositions <checker-receipt> --out "
            "<file>`), владелец заполняет класс и основание каждой и подписывает "
            "одной закрытой фразой; затем `checker --accept-adjudicated-route` и "
            "`adjudicate --dispositions <file>`. Без подписи ничего не чеканится. "
            "Альтернатива: переделать последнюю правку формой, не добавляющей "
            "поверхности. Следующий раунд того же вида купит следующую находку "
            "в следующей правке."
        )
        return decision
    verdict_rounds = [r for r in rounds if r["terminal"] == "verdict"]
    last_verdict = verdict_rounds[-1] if verdict_rounds else None

    # F1: классы precondition/transport не участвуют в повторах, но у них есть
    # СВОЙ исход — починить маршрут. Раньше такая история проваливалась в
    # CONTINUE, то есть звала на новый раунд вместо ремонта того, что сломалось.
    broken_route = [r for r in rounds if r["terminal"] != "verdict"]
    trailing_break = rounds[-1] if rounds and rounds[-1]["terminal"] != "verdict" else None
    # Закрытие — свойство ПОСЛЕДНЕГО раунда, а не последнего вердикта. Срыв
    # маршрута после зелёного означает, что маршрут не доигран: объявлять его
    # закрытым значило бы прятать оставшуюся работу за более ранним PASSED.
    final_round = rounds[-1] if rounds else None
    closing_pass = (final_round is not None
                    and final_round["terminal"] == "verdict"
                    and final_round["verdict"] == "PASSED")
    if broken_route and (last_verdict is None or trailing_break is not None):
        blocker = trailing_break or broken_route[-1]
        klass = blocker["terminal"]
        decision["terminal"] = "ROUTE_REPAIR"
        decision["atRound"] = blocker["id"]
        decision["why"] = (
            f"Последним сорвался маршрут, а не суждение о кандидате: раунд "
            f"{blocker['id']} — класс {klass}, исход {blocker['verdict']!r}. "
            + ("Вердиктов ревьюера в этой истории нет вовсе, судить не о чем."
               if last_verdict is None else
               "Новый раунд ревью здесь чинит не то, что сломалось.")
        )
        decision["fix"] = str(policy["terminalClasses"][klass].get("action") or
                              "Починить маршрут и повторить заход.")
        return decision

    if closing_pass:
        decision["terminal"] = "CLOSE"
        decision["atRound"] = last_verdict["id"]
        decision["why"] = (
            f"Раунд {last_verdict['id']} дал чистый PASSED, и ни один механизм "
            f"не повторился: маршрут сошёлся."
        )
        decision["fix"] = "Публиковать по обычному маршруту."
        return decision

    decision["terminal"] = "CONTINUE"
    decision["why"] = (
        f"Каждый вердикт называл ранее не встречавшийся механизм "
        f"({len(mechanism_rounds)} различных за {counters['verdict']} вердиктов): "
        f"маршрут сходится на предмете. Потолок раундов не применяется."
    )
    decision["fix"] = (
        "Закрыть находки корнем и идти в следующий раунд. Останавливать "
        "сходящийся маршрут по счётчику — значит отгружать кандидата с живыми "
        "дефектами."
    )
    return decision


# --------------------------------------------------------------------------
# вывод
# --------------------------------------------------------------------------

def render(decision: dict) -> str:
    lines = [
        f"UNIT      {decision['unit']}",
        f"TERMINAL  {decision['terminal']}"
        + (f"  (раунд {decision['atRound']})" if decision.get("atRound") else ""),
        f"WHY       {decision['why']}",
        f"FIX       {decision['fix']}",
    ]
    counters = decision["counters"]
    lines.append(
        "ЗАХОДЫ    всего {attempts}: вердиктов {v}, предусловие {p}, транспорт {t}".format(
            attempts=decision["attempts"], v=counters["verdict"],
            p=counters["precondition"], t=counters["transport"])
    )
    non_verdict = counters["precondition"] + counters["transport"]
    if non_verdict:
        lines.append(
            "  В решении участвовали только {v} вердикта(ов); остальные {n} "
            "захода(ов) — поломки маршрута, а не суждения о кандидате.".format(
                v=counters["verdict"], n=non_verdict)
        )
    provenance = decision["provenance"]
    if provenance["narrative"]:
        lines.append(
            "ПРОВЕНАНС машинных отчётов {r}, ПЕРЕСКАЗА {n} — раунды пересказа не "
            "являются машинной уликой".format(r=provenance["report"], n=provenance["narrative"])
        )
    else:
        lines.append(f"ПРОВЕНАНС машинных отчётов {provenance['report']}")
    surface = decision.get("surface")
    if surface is not None:
        evidenced = [item for item in surface["rounds"] if item["evidence"]]
        figures = (", ".join(f"{item['round']} {item['onAdded']}/{item['located']}"
                             for item in evidenced)
                   if evidenced else "улик поверхности нет ни у одного раунда")
        lines.append(
            "ПОВЕРХНОСТЬ окно {w}: ".format(w=surface["windowRounds"]) + figures
            + (f" — {surface['why']}" if surface["why"] and not surface["terminalArmed"] else "")
        )
        unverified = [item["round"] for item in evidenced
                      if item["verifiedAgainstTrees"] is False]
        if unverified:
            lines.append(
                "  улика поверхности раундов {ids} не пересчитана: деревьев нет в "
                "объектной базе — архив проверен только по sha256".format(
                    ids=", ".join(unverified))
            )
        narrative = [item["round"] for item in evidenced if item["narrativeLines"]]
        if narrative:
            lines.append(
                "  строки находок раундов {ids} переписаны из журнала — не "
                "машинная улика".format(ids=", ".join(narrative))
            )
    for gap in decision.get("knownGaps", []):
        lines.append(
            f"ПРОБЕЛ    {gap['id']}: {gap['why']} — класс терминала неизвестен, "
            f"поэтому раунд не попал ни в один счётчик"
        )
    if decision.get("contentMissing"):
        lines.append(
            "  Без содержания в записи: {ids} — артефакт не сохранён и не "
            "пересказан, механизмы этих раундов правилу не видны.".format(
                ids=", ".join(decision["contentMissing"]))
        )
    for item in decision.get("recurring", []):
        lines.append(
            "ПОВТОР    {m}: раунды {r} (различимых кандидатов: {c})".format(
                m=item["mechanism"], r=", ".join(item["rounds"]),
                c=item["distinctCandidates"])
        )
    if decision.get("unkeyable"):
        rounds_named = sorted({item["round"] for item in decision["unkeyable"]})
        lines.append(
            "БЕЗ КЛЮЧА {n} находка(ок) в раундах {ids} не назвали ни поверхность, "
            "ни класс — в повторы не засчитаны, склеивать их в один механизм "
            "было бы ложным повтором".format(
                n=len(decision["unkeyable"]), ids=", ".join(rounds_named))
        )
    for item in decision.get("refuted", []):
        lines.append(
            f"ОПРОВЕРГНУТА {item['round']}: {item['surface']} / {item['class']} — "
            f"в повторы не засчитана"
        )
    for item in decision.get("regressions", []):
        lines.append(
            f"РЕГРЕССИЯ {item['round']}: {item['surface']} / {item['class']} — "
            f"чинится в корне, в повторы не засчитана"
        )
    return "\n".join(lines)


def emit_dispositions(decision: dict, checker_path: Path, history_label: str) -> dict:
    """Черновик диспозиций ADR-007 по BLOCKED-квитанции чекера.

    Правило СОСТАВЛЯЕТ строки — по одной на каждую находку и каждый пункт
    unverified, дайджест тот же, что у валидатора маршрута; класс, основание
    и подписанта заполняет ЧЕЛОВЕК. Плейсхолдер не является классом, поэтому
    незаполненный черновик адъюдикация отвергает сама (fail-closed).
    """
    terminal = decision.get("terminal")
    if terminal not in OWNER_DECISION_TERMINALS:
        raise StopRuleError(
            f"dispositions are drafted only on {list(OWNER_DECISION_TERMINALS)}, "
            f"decision is {terminal!r}: на терминале продолжения правило не "
            f"подсказывает «принять как компромисс»"
        )
    loop = load_verification_loop()
    if not checker_path.is_file():
        raise StopRuleError(f"checker receipt is missing: {checker_path}")
    payload = checker_path.read_bytes()
    try:
        receipt = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StopRuleError(f"checker receipt {checker_path} is not JSON: {exc}") from exc
    if not isinstance(receipt, dict) or receipt.get("verdict") != "BLOCKED":
        raise StopRuleError(
            f"checker receipt {checker_path} is not a BLOCKED verdict: чистый "
            f"вердикт в диспозициях не нуждается"
        )
    for field in ("findings", "unverified"):
        if field in receipt and not isinstance(receipt[field], list):
            # dict/число/строка молча дали бы «находки» из ключей или символов (r3).
            raise StopRuleError(
                f"checker receipt {checker_path}: {field} must be a list, got "
                f"{type(receipt[field]).__name__}"
            )
    targets = list(receipt.get("findings") or []) + list(receipt.get("unverified") or [])
    if not targets:
        raise StopRuleError(
            f"checker receipt {checker_path} carries no findings to disposition"
        )
    # Хеш и разбор — один буфер; подпись владельца привязывается к этим байтам.
    sha = hashlib.sha256(payload).hexdigest()
    basis = f"терминал {terminal} на раунде {decision.get('atRound')}; история {history_label}"
    rows = []
    seen: set[str] = set()
    for item in targets:
        digest = loop.finding_digest(item)
        if digest in seen:
            # Валидатор требует ровно одну диспозицию на дайджест.
            continue
        seen.add(digest)
        rows.append({
            "findingSha256": digest,
            "finding": item,
            "class": DRAFT_PLACEHOLDER,
            "rationale": f"{DRAFT_PLACEHOLDER}: класс и основание — решение владельца; {basis}",
            "evidence": f"{DRAFT_PLACEHOLDER} при refuted-by-evidence / fixed",
        })
    return {
        "confirmedBy": DRAFT_PLACEHOLDER,
        "confirmation": loop.CONFIRMATION_TEMPLATE.format(sha256=sha),
        "checkerReceiptSha256": sha,
        "dispositions": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Правило остановки цикла ревью над содержанием находок")
    parser.add_argument("--history", help="путь к записанной истории раундов")
    parser.add_argument("--policy", help="путь к политике (по умолчанию .itd/STOP_RULE_POLICY.json)")
    parser.add_argument("--root", default=str(ROOT), help="корень репозитория")
    parser.add_argument("--check-binding", action="store_true",
                        help="живая проверка приёмочной бухгалтерии активного юнита")
    parser.add_argument("--json", action="store_true", help="машинный вывод")
    parser.add_argument("--emit-dispositions", metavar="CHECKER_RECEIPT",
                        help="составить черновик диспозиций ADR-007 по BLOCKED-квитанции "
                             "чекера (только на терминале решения владельца)")
    parser.add_argument("--out", help="куда писать черновик диспозиций")
    args = parser.parse_args(argv)
    if bool(args.emit_dispositions) != bool(args.out):
        parser.error("--emit-dispositions и --out задаются вместе")

    root = Path(args.root).resolve()
    try:
        # Политика по умолчанию берётся от --root, а не от расположения этого
        # файла: --root /fixture судил бы чужие леджеры по политике вызывающего
        # репозитория и мог дать ложное «выровнено» (находка ревьюера, r33).
        policy = load_policy(
            Path(args.policy) if args.policy
            else Path(args.root) / ".itd" / "STOP_RULE_POLICY.json")
        if args.check_binding:
            binding = live_policy_binding(policy, root)
            if args.json:
                print(json.dumps(binding, ensure_ascii=False, sort_keys=True))
            else:
                state = "ALIGNED" if binding["aligned"] else "ROUTE_DEFECT"
                print(f"BINDING   {state}")
                print(f"  леджер:  {binding['ledgerUnit']}")
                print(f"  контракт:{binding['contractUnit']}")
                print(f"  критериев {binding['criteriaTotal']}, "
                      f"в статусе passed {binding['criteriaMatchingStatus']}")
                if not binding["aligned"]:
                    if binding["contractUnit"] != binding["ledgerUnit"] or not binding["criteriaPresent"]:
                        print("  WHY: ревью пойдёт по политике чужого юнита и о "
                              "кандидате не будет свидетельствовать.")
                        print("  FIX: привести activeFollowup.unitId к активному "
                              "юниту и завести его критерии.")
                    else:
                        print(f"  WHY: критерии юнита есть, но не все в статусе "
                              f"{binding['requiredCriteriaStatus']!r} "
                              f"({binding['criteriaMatchingStatus']} из "
                              f"{binding['criteriaTotal']}); продюсер вернёт "
                              f"UNVERIFIED ещё до ревьюера.")
                        print("  FIX: довести критерии активного юнита до "
                              "требуемого статуса и повторить.")
            return 0 if binding["aligned"] else 2
        if not args.history:
            parser.error("нужен --history или --check-binding")
        history = load_history(Path(args.history))
        decision = decide(history, policy, root)
    except StopRuleError as exc:
        print(f"STOP-RULE INPUT REJECTED: {exc}", file=sys.stderr)
        return 2

    if args.emit_dispositions:
        try:
            draft = emit_dispositions(decision, Path(args.emit_dispositions).resolve(),
                                      Path(args.history).name)
        except StopRuleError as exc:
            print(render(decision))
            print(f"DISPOSITIONS REFUSED: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out)
        out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(render(decision))
        print(f"DISPOSITIONS DRAFT: {len(draft['dispositions'])} строк(и) -> {out}")
        print(f"  подпись владельца = точная фраза: {draft['confirmation']}")
        print(f"  заполнить: confirmedBy, class, rationale (evidence для refuted/fixed)")
        return 0
    if args.json:
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(render(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
