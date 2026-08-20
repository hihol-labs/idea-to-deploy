#!/usr/bin/env python3
"""verify_review_evidence.py — прямой контракт skills/_shared/itd_review_evidence.py.

До LPD-002 R5 модуль, решающий судьбу каждого кандидата ревью, не имел
собственного сьюта и покрывался лишь косвенно (tests/verify_independent_review_
efficacy.py:289/304/315/342). Этот файл — первый прямой оракул.

Контракт:
  1. обычный (delivery) кандидат по-прежнему требует СВОЕГО покрытия, и каждая
     прежняя гарантия матрицы держится байт-в-байт (переблокировка);
  2. класс `ledger-close` определён точно: диф = .itd-memory/STATE.json плюс
     контракт, изменённый ТОЛЬКО в activeFollowup.status/closedAt, при закрытом
     followup со всеми критериями passed;
  3. для класса матрица наследует покрытие ЗАКРЫТОГО юнита и честно называет
     источник полем coverageSource;
  4. класс не ослабляет маршрут: minimumIndependentReviewers клампится к >= 1;
  5. любой байт вне точного состава класса возвращает кандидата на обычный
     маршрут (недоблокировка), а закрытый followup с непройденным критерием —
     явный отказ, а не тихое None.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "_shared" / "itd_review_evidence.py"
RUN_ALL_PATH = ROOT / "tests" / "run-all.sh"

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print("PASS  " + name)
        return
    fails.append(name)
    print("FAIL  " + name + ((" — " + detail) if detail else ""))


def load_module(path: Path, name: str) -> types.ModuleType:
    """Компилировать прочитанные байты: кэш байткода той же длины давал вердикт
    о СТАРОМ коде (измерено на R4, tests/verify_independent_review_efficacy.py).
    """
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


evidence = load_module(MODULE_PATH, "itd_review_evidence_under_test")

TREE = "a" * 40
STATE_PATH = ".itd-memory/STATE.json"
CONTRACT_PATH = ".itd/ACCEPTANCE_CONTRACT.json"


def acceptance_fixture(
    *, unit: str = "UNIT", risk: str = "high", minimum: int = 1,
    status: str = "in_progress",
) -> dict:
    followup: dict = {
        "unitId": unit,
        "status": status,
        "reviewPolicy": {
            "mode": "evidence-first",
            "riskTier": risk,
            "requiredImpactClasses": ["correctness", "reconciliation"],
            "minimumIndependentReviewers": minimum,
            "explorer": "isolated-machine-oracle",
            "adjudicator": "sealed-host-union",
        },
    }
    return {
        "version": 2,
        "purpose": "fixture",
        "criteria": [{
            "id": unit + "-AC1",
            "status": "passed",
            "reviewEvidence": {
                "claim": "The delivered behaviour is executable.",
                "impactClasses": ["correctness", "reconciliation"],
                "oracleIds": ["domain-oracle"],
            },
        }],
        "activeFollowup": followup,
    }


def machine_fixture(*, unit: str = "UNIT", risk: str = "high") -> dict:
    return {
        "unitId": unit,
        "riskTier": risk,
        "candidate": {"reviewedTree": TREE},
        "runs": [{"id": "domain-oracle", "exitCode": 0, "executedTree": TREE}],
    }


def closed_pair(*, risk: str = "high", minimum: int = 1) -> tuple[dict, dict]:
    """Контракт кандидата: followup закрыт; контракт базы: он же, но открыт."""
    after = acceptance_fixture(risk=risk, minimum=minimum, status="verified")
    after["activeFollowup"]["closedAt"] = "2026-08-19T11:00:00Z"
    before = copy.deepcopy(after)
    before["activeFollowup"]["status"] = "in_progress"
    before["activeFollowup"].pop("closedAt")
    return after, before


def close_facts(before: dict | None, paths: list[str] | None = None,
                modified: list[str] | None = None,
                state_before: dict | None = None) -> dict:
    changed = list(paths if paths is not None else [STATE_PATH, CONTRACT_PATH])
    return {
        "changedPaths": changed,
        "modifiedPaths": list(modified if modified is not None else changed),
        "contractPath": CONTRACT_PATH,
        "contractBefore": before,
        "stateBefore": state_before,
    }


def matrix_or_error(acceptance, machine, candidate=None):
    """Вернуть матрицу, None, либо строку ошибки — три различимых исхода.

    Любое исключение ВНЕ ReviewEvidenceError — отдельный исход `CRASH`: его
    не ловит `freeze_packet` продюсера, поэтому оно валит маршрут вместо
    отказа. Такое обязано давать именованную красную проверку, а не трейсбек
    самого сьюта.
    """
    try:
        return evidence.coverage_matrix(acceptance, machine, candidate=candidate)
    except evidence.ReviewEvidenceError as exc:
        return "ERROR: " + str(exc)
    except Exception as exc:  # noqa: BLE001 — фиксируем именно неожиданный класс
        return f"CRASH: {type(exc).__name__}: {exc}"


def guard_or_crash(before, after):
    try:
        return evidence._closes_only_the_followup(before, after)
    except Exception as exc:  # noqa: BLE001
        return f"CRASH: {type(exc).__name__}: {exc}"


# --- 1. delivery-кандидат: прежние гарантии держатся (переблокировка) --------

matrix = matrix_or_error(acceptance_fixture(), machine_fixture())
check("active-unit-matrix-is-built",
      isinstance(matrix, dict)
      and matrix.get("unitId") == "UNIT"
      and matrix.get("coverageSource") == "active-unit"
      and matrix.get("minimumIndependentReviewers") == 1
      and [row["criterionId"] for row in matrix.get("criteria", [])] == ["UNIT-AC1"],
      repr(matrix)[:200])

short = acceptance_fixture()
short["criteria"][0]["reviewEvidence"]["impactClasses"] = ["correctness"]
result = matrix_or_error(short, machine_fixture())
check("delivery-candidate-still-needs-its-own-coverage",
      isinstance(result, str) and "required impact evidence is missing" in result,
      repr(result)[:200])

unknown = acceptance_fixture()
unknown["criteria"][0]["reviewEvidence"]["impactClasses"] = ["teleportation"]
check("unknown-impact-class-refused",
      isinstance(matrix_or_error(unknown, machine_fixture()), str))

failed_oracle = machine_fixture()
failed_oracle["runs"][0]["exitCode"] = 1
foreign_tree = machine_fixture()
foreign_tree["runs"][0]["executedTree"] = "b" * 40
check("oracle-must-be-an-exact-pass",
      isinstance(matrix_or_error(acceptance_fixture(), failed_oracle), str)
      and isinstance(matrix_or_error(acceptance_fixture(), foreign_tree), str))

duplicated = acceptance_fixture()
duplicated["criteria"].append(copy.deepcopy(duplicated["criteria"][0]))
check("duplicate-criterion-refused",
      isinstance(matrix_or_error(duplicated, machine_fixture()), str))

unpassed = acceptance_fixture()
unpassed["criteria"][0]["status"] = "pending"
check("unpassed-criterion-refused",
      isinstance(matrix_or_error(unpassed, machine_fixture()), str))

cardinality = []
for risk, minimum, expect_ok in (
    ("low", 0, True), ("low", 1, False),
    ("high", 1, True), ("high", 0, False),
    ("medium", 1, True), ("unknown", 0, False),
):
    outcome = matrix_or_error(
        acceptance_fixture(risk=risk, minimum=minimum),
        machine_fixture(risk=risk),
    )
    cardinality.append(isinstance(outcome, dict) is expect_ok)
check("reviewer-cardinality-rule-holds", all(cardinality), repr(cardinality))

check("malformed-arguments-refused",
      isinstance(matrix_or_error(["not", "a", "dict"], machine_fixture()), str)
      and isinstance(matrix_or_error(acceptance_fixture(), "nope"), str))

closed_acceptance, _ = closed_pair()
check("closed-followup-without-candidate-stays-none",
      matrix_or_error(closed_acceptance, machine_fixture()) is None,
      "прежний контракт: без фактов кандидата закрытый followup отпускает матрицу")


# --- 2. класс ledger-close: наследование покрытия закрытого юнита ------------

after, before = closed_pair()
inherited = matrix_or_error(after, machine_fixture(), close_facts(before))
check("close-class-inherits-closed-unit-coverage",
      isinstance(inherited, dict)
      and inherited.get("coverageSource") == "closed-unit-inherited"
      and inherited.get("unitId") == "UNIT"
      and [row["criterionId"] for row in inherited.get("criteria", [])]
      == ["UNIT-AC1"],
      repr(inherited)[:220])

# Диф без контракта НЕ является закрытием: единственный оставшийся сигнал —
# «в смердженном контракте followup уже закрыт», а это верно для КАЖДОГО
# коммита между закрытием одного юнита и открытием следующего. Такой класс
# отдал бы унаследованное покрытие любой поздней правке STATE.json — а это
# рутинная форма коммита в этом репо (0d6f013, e56284e, 43e661e). Находка
# чекера r2, закрыта требованием перехода контракта в самом дифе.
after_state_only, before_state_only = closed_pair()
check("close-class-refuses-a-state-only-diff",
      matrix_or_error(after_state_only, machine_fixture(),
                      close_facts(before_state_only, [STATE_PATH])) is None,
      "закрытие обязано нести переход контракта, а не только правку STATE")

after_low, before_low = closed_pair(risk="low", minimum=0)
clamped = matrix_or_error(
    after_low, machine_fixture(risk="low"), close_facts(before_low),
)
check("close-class-clamps-reviewers-to-one",
      isinstance(clamped, dict)
      and clamped.get("riskTier") == "low"
      and clamped.get("minimumIndependentReviewers") == 1,
      repr(clamped)[:220])


# --- 3. канарейки на недоблокировку: любой байт вне класса --------------------

for label, paths in (
    ("code", [STATE_PATH, CONTRACT_PATH, "skills/_shared/itd_review_evidence.py"]),
    ("plan-ledger", [STATE_PATH, ".itd-memory/LPD-002_UNIT_PLAN.json"]),
    ("no-state-file", [CONTRACT_PATH]),
):
    after_x, before_x = closed_pair()
    outcome = matrix_or_error(after_x, machine_fixture(), close_facts(before_x, paths))
    check("close-class-refuses-a-third-path/" + label, outcome is None,
          repr(outcome)[:160])

# Класс определяется не только составом путей, но и ТИПОМ строки дифа: закрытие
# правит уже существующий леджер. Кандидат, который его создаёт или уничтожает,
# делает нечто иное и не может подаваться ревьюеру как рутинная бухгалтерия,
# у которой отсутствие покрытия ожидаемо (находка чекера r5, воспроизведена в
# обе стороны — add и delete).
for label, modified in (
    ("state-added", [CONTRACT_PATH]),
    ("state-deleted", [CONTRACT_PATH]),
    ("contract-added", [STATE_PATH]),
    ("nothing-modified", []),
):
    after_t, before_t = closed_pair()
    check("close-class-requires-both-rows-modified/" + label,
          matrix_or_error(after_t, machine_fixture(),
                          close_facts(before_t, modified=modified)) is None,
          "строка дифа не 'M' — это не закрытие леджера")

after_mm, before_mm = closed_pair()
check("malformed-modified-paths-refused",
      isinstance(matrix_or_error(
          after_mm, machine_fixture(),
          {"changedPaths": [STATE_PATH, CONTRACT_PATH],
           "modifiedPaths": "нет", "contractPath": CONTRACT_PATH,
           "contractBefore": before_mm, "stateBefore": None}), str))

after_f, before_f = closed_pair()
before_f["purpose"] = "changed elsewhere"
check("close-class-refuses-a-foreign-contract-key",
      matrix_or_error(after_f, machine_fixture(), close_facts(before_f)) is None)

after_p, before_p = closed_pair()
before_p["activeFollowup"]["reviewPolicy"]["minimumIndependentReviewers"] = 0
check("close-class-refuses-a-foreign-followup-field",
      matrix_or_error(after_p, machine_fixture(), close_facts(before_p)) is None)

after_m, _ = closed_pair()
check("close-class-refuses-a-missing-base-contract",
      matrix_or_error(after_m, machine_fixture(), close_facts(None)) is None)

after_n, before_n = closed_pair()
before_n["activeFollowup"]["status"] = "verified"
before_n["activeFollowup"]["closedAt"] = "2026-08-19T11:00:00Z"
check("close-class-refuses-an-already-closed-followup",
      matrix_or_error(after_n, machine_fixture(), close_facts(before_n)) is None,
      "контракт в дифе, но followup уже был закрыт — закрывать нечего")


# --- 4. открытый followup при close-дифе: класс не признаётся -----------------

open_acceptance = acceptance_fixture()
_, open_before = closed_pair()
open_matrix = matrix_or_error(
    open_acceptance, machine_fixture(), close_facts(open_before),
)
check("open-followup-is-never-a-close",
      isinstance(open_matrix, dict)
      and open_matrix.get("coverageSource") == "active-unit")

open_short = acceptance_fixture()
open_short["criteria"][0]["reviewEvidence"]["impactClasses"] = ["correctness"]
check("open-followup-still-needs-its-own-coverage",
      isinstance(matrix_or_error(open_short, machine_fixture(),
                                 close_facts(open_before)), str))

# coverage_matrix достигает ledger_close_policy только на закрытом followup,
# поэтому собственный гуард функции проверяется прямым вызовом — иначе он
# необнаружимая мёртвая ветка (измерено мутацией open-followup-accepted).
check("ledger-close-policy-refuses-an-open-followup-directly",
      evidence.ledger_close_policy(
          acceptance_fixture(), close_facts(open_before)) is None)
check("ledger-close-policy-accepts-a-closed-followup-directly",
      isinstance(evidence.ledger_close_policy(
          closed_pair()[0], close_facts(closed_pair()[1])), dict))

# Базовая версия контракта приходит из произвольного исторического blob'а:
# её activeFollowup может не быть объектом вообще. Отказ обязан быть тихим
# возвратом на обычный маршрут, а НЕ трейсбеком из followup_is_closed —
# coverage_matrix ловит только ReviewEvidenceError (находка чекера r1).
after_b, before_b = closed_pair()
before_b["activeFollowup"] = None
check("close-class-survives-a-non-object-base-followup",
      matrix_or_error(after_b, machine_fixture(), close_facts(before_b)) is None,
      "None вместо объекта в базовом контракте роняет продюсер трейсбеком")
after_s, before_s = closed_pair()
check("closes-only-the-followup-guards-both-sides",
      guard_or_crash({"activeFollowup": None}, {"activeFollowup": {}}) is False
      and guard_or_crash({"activeFollowup": {}}, {"activeFollowup": None}) is False
      and guard_or_crash(before_s, after_s) is True,
      repr(guard_or_crash({"activeFollowup": None}, {"activeFollowup": {}}))[:120])


# --- 5. закрытый followup с непройденным критерием: явный отказ ---------------

after_u, before_u = closed_pair()
# Критерий не пройден по ОБЕ стороны дифа: сам close-коммит критериев не
# трогает, иначе это уже не чистое закрытие (см. foreign-contract-key).
after_u["criteria"][0]["status"] = "pending"
before_u["criteria"][0]["status"] = "pending"
outcome_u = matrix_or_error(after_u, machine_fixture(), close_facts(before_u))
check("close-class-refuses-an-unpassed-criterion",
      isinstance(outcome_u, str) and "is not passed" in outcome_u,
      repr(outcome_u)[:200])

after_e, before_e = closed_pair()
check("empty-changed-paths-is-malformed-not-a-class",
      isinstance(matrix_or_error(after_e, machine_fixture(),
                                 close_facts(before_e, [])), str),
      "пустой инвентарь дифа — дефект фактов кандидата, а не тихий отказ класса")

after_o, before_o = closed_pair()
failed_close = machine_fixture()
failed_close["runs"][0]["exitCode"] = 1
check("close-class-keeps-the-exact-oracle-binding",
      isinstance(matrix_or_error(after_o, failed_close,
                                 close_facts(before_o)), str))

after_i, before_i = closed_pair()
after_i["activeFollowup"]["reviewPolicy"]["explorer"] = "vibes"
before_i["activeFollowup"]["reviewPolicy"]["explorer"] = "vibes"
check("close-class-refuses-an-invalid-inherited-policy",
      isinstance(matrix_or_error(after_i, machine_fixture(),
                                 close_facts(before_i)), str))

after_c, before_c = closed_pair()
for broken in (["not", "a", "dict"], {"changedPaths": [STATE_PATH]},
               {"changedPaths": [STATE_PATH], "contractPath": CONTRACT_PATH,
                "contractBefore": before_c, "extra": 1}):
    outcome_c = matrix_or_error(after_c, machine_fixture(), broken)
    check("malformed-candidate-facts-refused/" + str(type(broken).__name__)
          + str(len(broken)),
          isinstance(outcome_c, str), repr(outcome_c)[:160])


# --- 6. регистрация сьюта и закрытое множество классов воздействия ------------

core = re.search(r'^CORE="([^"]*)"', RUN_ALL_PATH.read_text(encoding="utf-8"),
                 re.MULTILINE)
check("suite-is-registered-in-run-all",
      bool(core) and "verify_review_evidence" in core.group(1).split(),
      "список CORE ведётся руками — сьют обязан быть в нём")

check("impact-classes-stay-a-closed-set",
      isinstance(evidence.IMPACT_CLASSES, frozenset)
      and "correctness" in evidence.IMPACT_CLASSES
      and "teleportation" not in evidence.IMPACT_CLASSES)

check("ledger-state-path-is-the-canonical-one",
      getattr(evidence, "LEDGER_STATE_PATH", None) == STATE_PATH
      and set(getattr(evidence, "CLOSING_FOLLOWUP_FIELDS", frozenset()))
      == {"status", "closedAt"})


# --- LPD002-A5: леджер-файлы, объявленные в БАЗОВОМ STATE, едут с close ---
PLAN_PATH = ".itd-memory/LPD-002_UNIT_PLAN.json"
DECLARING_STATE = {"ledgerFiles": [PLAN_PATH]}

after_a5, before_a5 = closed_pair()
m = matrix_or_error(after_a5, machine_fixture(),
                    close_facts(before_a5,
                                paths=[STATE_PATH, CONTRACT_PATH, PLAN_PATH],
                                state_before=DECLARING_STATE))
check("a5-declared-plan-file-rides-with-the-close",
      isinstance(m, dict) and m.get("coverageSource") == "closed-unit-inherited",
      str(m)[:120])

after_a5b, before_a5b = closed_pair()
check("a5-undeclared-third-path-still-expelled",
      matrix_or_error(after_a5b, machine_fixture(),
                      close_facts(before_a5b,
                                  paths=[STATE_PATH, CONTRACT_PATH, PLAN_PATH],
                                  state_before={"ledgerFiles": []})) is None)

after_a5c, before_a5c = closed_pair()
check("a5-declaration-must-precede-the-close-no-stateBefore",
      matrix_or_error(after_a5c, machine_fixture(),
                      close_facts(before_a5c,
                                  paths=[STATE_PATH, CONTRACT_PATH, PLAN_PATH],
                                  state_before=None)) is None)

after_a5d, before_a5d = closed_pair()
check("a5-declared-code-path-outside-itd-memory-refused",
      matrix_or_error(after_a5d, machine_fixture(),
                      close_facts(before_a5d,
                                  paths=[STATE_PATH, CONTRACT_PATH, "skills/x.py"],
                                  state_before={"ledgerFiles": ["skills/x.py"]}))
      is None)

after_a5e, before_a5e = closed_pair()
check("a5-declared-traversal-path-refused",
      matrix_or_error(after_a5e, machine_fixture(),
                      close_facts(before_a5e,
                                  paths=[STATE_PATH, CONTRACT_PATH,
                                         ".itd-memory/../secrets"],
                                  state_before={"ledgerFiles":
                                                [".itd-memory/../secrets"]}))
      is None)

after_a5f, before_a5f = closed_pair()
check("a5-extra-file-must-be-a-modification",
      matrix_or_error(after_a5f, machine_fixture(),
                      close_facts(before_a5f,
                                  paths=[STATE_PATH, CONTRACT_PATH, PLAN_PATH],
                                  modified=[STATE_PATH, CONTRACT_PATH],
                                  state_before=DECLARING_STATE)) is None)

after_a5g, before_a5g = closed_pair()
check("a5-two-file-close-unchanged-without-declaration",
      isinstance(matrix_or_error(after_a5g, machine_fixture(),
                                 close_facts(before_a5g)), dict))

# --- LPD002-A1: точная принадлежность критериев юниту ---
after_a1 = acceptance_fixture(unit="R1")
own = copy.deepcopy(after_a1["criteria"][0])
own["id"] = "R1-own"
own["unitId"] = "R1"
foreign = copy.deepcopy(after_a1["criteria"][0])
foreign["id"] = "R1-SCRUB-1"
foreign["status"] = "pending"  # чужой исторический критерий (инцидент R1)
after_a1["criteria"] = [own, foreign]
m = matrix_or_error(after_a1, machine_fixture(unit="R1"))
check("a1-explicit-unitId-excludes-prefix-captured-foreign-criterion",
      isinstance(m, dict)
      and [r["criterionId"] for r in m.get("criteria", [])] == ["R1-own"],
      str(m)[:200])

after_a1b = acceptance_fixture()
m = matrix_or_error(after_a1b, machine_fixture())
check("a1-legacy-contract-without-unitId-keeps-prefix-fallback",
      isinstance(m, dict) and len(m.get("criteria", [])) == 1, str(m)[:120])


if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_review_evidence: all ok")
