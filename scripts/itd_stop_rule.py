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

Правило advisory: оно печатает терминал и основание, решение принимает
владелец. Гейтом оно не является.

Контракт: `.itd/STOP_RULE_POLICY.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / ".itd" / "STOP_RULE_POLICY.json"
HISTORY_SCHEMA = "itd-stop-rule-history-v1"
POLICY_SCHEMA = "itd-stop-rule-policy-v1"

TERMINAL_CLASSES = ("verdict", "precondition", "transport")
EXPECTED_PRECEDENCE = ["ROUTE_DEFECT", "REDESIGN_OR_DISCARD", "RECURRENCE_UNCONFIRMED",
                       "ROUTE_REPAIR", "CLOSE", "CONTINUE"]
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
EXPECTED_POLICY_SCALARS = {
    ("status",): "advisory",
    ("mechanismKey", "mergeOnly"): True,
    ("mechanismKey", "distinctRoundsRequired"): 2,
    ("policyBinding", "requireCriteriaPrefix"): True,
    ("policyBinding", "requireCriteriaStatus"): "passed",
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

    # Статус advisory заморожен картой EXPECTED_POLICY_SCALARS: превращение
    # правила в гейт — отдельное решение владельца, а не правка политики.
    text = json.dumps(document, ensure_ascii=False)
    for forbidden in ("maxRounds", "roundCap", "maxAttempts", "roundLimit"):
        if forbidden in text:
            raise StopRuleError(
                f"policy declares {forbidden!r}: потолок раундов запрещён по "
                f"построению — он останавливает сходящийся маршрут на зелёном"
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


def read_round(entry: dict, index: int, policy: dict, root: Path) -> dict:
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

    record = {
        "id": round_id,
        "terminal": terminal,
        "provenance": provenance_class,
        "verdict": None,
        "findings": [],
        "contentAvailable": provenance_class != "absent",
        "candidate": candidate,
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
        findings = document.get("findings")
        if findings is None:
            findings = []
        if not isinstance(findings, list):
            raise StopRuleError(
                f"round {round_id}: report findings must be a list: {provenance['path']}"
            )
        parsed = []
        for position, finding in enumerate(findings):
            if not isinstance(finding, dict):
                raise StopRuleError(
                    f"round {round_id}: finding #{position} is not an object"
                )
            parsed.append({
                "file": finding.get("file"),
                "category": finding.get("category"),
                "severity": finding.get("severity"),
                "summary": (finding.get("summary") or "")[:400],
            })
        for finding_index, flags in apply_dispositions(entry, len(parsed), round_id):
            parsed[finding_index].update(flags)
        record["verdict"] = document.get("verdict")
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


def decide(history: dict, policy: dict, root: Path) -> dict:
    # Разбор идёт ПЕРВЫМ и всегда: любой раунд любой истории проходит проверку
    # провенанса, исхода и содержания, даже если ниже выяснится, что вердикты
    # этой истории интерпретировать нельзя.
    rounds = [read_round(entry, index, policy, root)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Правило остановки цикла ревью над содержанием находок")
    parser.add_argument("--history", help="путь к записанной истории раундов")
    parser.add_argument("--policy", help="путь к политике (по умолчанию .itd/STOP_RULE_POLICY.json)")
    parser.add_argument("--root", default=str(ROOT), help="корень репозитория")
    parser.add_argument("--check-binding", action="store_true",
                        help="живая проверка приёмочной бухгалтерии активного юнита")
    parser.add_argument("--json", action="store_true", help="машинный вывод")
    args = parser.parse_args(argv)

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

    if args.json:
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(render(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
