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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / ".itd" / "STOP_RULE_POLICY.json"
HISTORY_SCHEMA = "itd-stop-rule-history-v1"
POLICY_SCHEMA = "itd-stop-rule-policy-v1"

TERMINAL_CLASSES = ("verdict", "precondition", "transport")
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
    key = document["mechanismKey"]
    if key.get("default") != ["file", "category"]:
        raise StopRuleError("policy mechanismKey.default must stay (file, category)")
    if key.get("mergeOnly") is not True:
        raise StopRuleError("policy mechanismKey.mergeOnly must stay true")
    if int(key.get("distinctRoundsRequired", 0)) < 2:
        raise StopRuleError("policy mechanismKey.distinctRoundsRequired must be >= 2")
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
    if supplies_candidate and not str(document.get("candidateSource") or "").strip():
        raise StopRuleError(
            f"history supplies candidate identity without candidateSource: {path}\n"
            f"  WHY: смена кандидата — это то, ради чего повтор вообще считается "
            f"повтором. Две выдуманные строки без объявленного происхождения "
            f"взвели бы REDESIGN_OR_DISCARD на пустом месте.\n"
            f"  FIX: объявить candidateSource — из чего выведены личности раундов."
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
    provenance_class = provenance["class"]
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
    if candidate is not None and (not isinstance(candidate, str) or not candidate.strip()):
        raise StopRuleError(
            f"round {round_id}: candidate identity must be a non-empty string"
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


def raw_key(finding: dict) -> tuple[str, str] | None:
    """Ключ механизма или None, если находка не назвала ни поверхность, ни класс.

    Безымянные находки НЕ склеиваются в один псевдо-механизм: иначе несколько
    отчётов без file/category давали бы ложный повтор и правило остановило бы
    маршрут на пустом месте (замер: пять таких отчётов в серии GPG-001
    broker-policy).
    """
    file_part = finding.get("file")
    category_part = finding.get("category")
    if not isinstance(file_part, str) or not file_part.strip():
        return None
    if not isinstance(category_part, str) or not category_part.strip():
        return None
    return (file_part, category_part)


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
        for member in members:
            if (not isinstance(member, list) or len(member) != 2
                    or not all(isinstance(part, str) and part.strip() for part in member)):
                raise StopRuleError(
                    f"mergeKeys[{index}] ({label}) member must be a [file, category] pair"
                )
            key = (member[0], member[1])
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
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    contract_unit = ((contract.get("activeFollowup") or {}).get("unitId"))
    ledger_unit = ((ledger.get("currentUnit") or {}).get("id"))
    # Префикс сравнивается по границе идентификатора: голый startswith считал бы
    # критерии юнита LPD003-30 своими для активного LPD003-3.
    unit_prefix = str(ledger_unit)
    criteria = [c for c in (contract.get("criteria") or [])
                if str(c.get("id", "")) == unit_prefix
                or str(c.get("id", "")).startswith(unit_prefix + "-")]
    wanted = binding_policy.get("requireCriteriaStatus")
    passed = [c for c in criteria if c.get("status") == wanted]
    # Требуемый статус критериев объявлен политикой и потому обязан входить в
    # вердикт привязки: продюсер отказывает терминалом класса precondition, если
    # критерий активного юнита ещё pending, — значит «выровнено» при pending
    # было бы обещанием, которого маршрут не сдержит.
    status_satisfied = wanted is None or (bool(criteria) and len(passed) == len(criteria))
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

    decision = {
        "unit": history["unit"],
        "counters": counters,
        "provenance": provenance_counters,
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
    closing_pass = last_verdict is not None and last_verdict["verdict"] == "PASSED"
    if broken_route and (last_verdict is None or (trailing_break is not None and not closing_pass)):
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
        policy = load_policy(Path(args.policy) if args.policy else None)
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
