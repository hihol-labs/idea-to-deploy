#!/usr/bin/env python3
"""Оракул правила остановки над содержанием находок (LPD-003-3).

Три слоя проверок:

1. КОНТРАКТ — политика заморожена в тех местах, ослабление которых вернуло бы
   правило к счётчику раундов или разрешило бы снимать повтор переименованием.
2. РЕПЛЕЙ — каждая записанная история прогоняется правилом, и терминал
   сверяется с тем, что записано: либо с фактическим решением владельца, либо
   с явно объявленным расхождением.
3. МУТАЦИИ — на каждую гарантию своя обратная мутация; гарантия, которая не
   умирает от мутации, не проверена, а заявлена.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import itd_stop_rule as rule  # noqa: E402

# Пути перечислены литералами намеренно: генератор impact-карты
# (tests/build_impact_graph.py) выводит рёбра из литеральных путей в тексте
# сьюта. Собранный из переменных путь картой не виден, и targeted-профиль
# уводил бы прогон в strict на каждой правке этих файлов.
POLICY_FILE = ".itd/STOP_RULE_POLICY.json"
HISTORY_FILES = {
    "s04b": "tests/references/stop-rule/s04b.json",
    "r6": "tests/references/stop-rule/r6.json",
    "gpg-001-broker-policy": "tests/references/stop-rule/gpg-001-broker-policy.json",
    "lpd003-1-publication": "tests/references/stop-rule/lpd003-1-publication.json",
    "lpd003-1-2026-08-23": "tests/references/stop-rule/lpd003-1-2026-08-23.json",
    "pilot-p02": "tests/references/stop-rule/pilot-p02.json",
}
# Улики, на которые опираются истории, перечислены литералами по той же
# причине — и заодно это отдельная гарантия: набор улик ОБЪЯВЛЕН, а не
# подразумевается. Сослаться на артефакт, которого нет в этом списке, нельзя.
EVIDENCE_FILES = (
    ".itd-memory/session_2026-08-20.md",
    ".itd-memory/session_2026-08-23.md",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB1-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB10-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB2-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB3-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB4-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB5-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB6-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB7-report.json",
    "tests/references/stop-rule/evidence/GENG-S04B-PUB8-report.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-0f48da57.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-2085c448.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-235cc16c.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-309e5101.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-320973bf.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-328e5ebc.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-416680d8.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-5486ed5c.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-6d1ab178.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-785a6c8b.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-803dd506.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-88919fcf.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-a080cd62.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-af1fbafa.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-cdfbd912.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-ce56f703.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-da49c6d6.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-deb080b6.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra-f63bfa1a.json",
    "tests/references/stop-rule/evidence/GPG-001-broker-policy-terra.json",
    "tests/references/stop-rule/evidence/LPD003-1-pub-r10-report.json",
    "tests/references/stop-rule/evidence/LPD003-1-pub-r2-report.json",
    "tests/references/stop-rule/evidence/LPD003-1-pub-r3-report.json",
    "tests/references/stop-rule/evidence/PILOT-P02-r6.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r10.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r14.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r15.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r19.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r23.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r28.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r38.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r41.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r44.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r47.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r51.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r53.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r58.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r59.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r62.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r65.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-r70.surface",
    "tests/references/stop-rule/evidence/PILOT-P02-transcript-findings.json",
)

# Документы, на которые истории ссылаются как на ЗАПИСЬ решения. Тоже
# литералами: иначе impact-карта видит один цитируемый журнал и не видит
# другой, и targeted-прогон пропускает оракул при правке второго.
SOURCE_FILES = (
    ".itd/DECISIONS.md",
    ".itd-memory/session_2026-08-01_3.md",
    ".itd-memory/session_2026-08-20.md",
    ".itd-memory/session_2026-08-23.md",
)

FIXTURES = ROOT / "tests" / "references" / "stop-rule"

checks = 0
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name}{(': ' + detail) if detail else ''}")


def rejects(name: str, history: dict, policy: dict) -> None:
    """История должна быть отвергнута fail-closed, а не разобрана молча."""
    global checks
    checks += 1
    try:
        rule.decide(history, policy, ROOT)
    except rule.StopRuleError:
        return
    failures.append(f"{name}: вход принят, хотя обязан быть отвергнут")


def load(name: str) -> dict:
    return rule.load_history(ROOT / HISTORY_FILES[name])


def synthetic(rounds: list[dict], **extra) -> dict:
    document = {
        "schema": rule.HISTORY_SCHEMA,
        "unit": "synthetic",
        "orderSource": "синтетическая история оракула",
        "orderProvenance": {"class": "artifact-list"},
        "candidateSource": {"kind": "synthetic",
                            "note": "id раунда — синтетические раунды моделируют перечеканенного кандидата"},
        "rounds": rounds,
    }
    document.update(extra)
    return document


# Синтетические раунды цитируют реальную строку реального документа: у helper'а
# не может быть послаблений, которых нет у настоящей истории — иначе форма без
# цитаты осталась бы проходимой.
SYNTHETIC_SOURCE = "tests/verify_stop_rule.py"
SYNTHETIC_LINE = 1


def narrative_round(round_id: str, verdict: str, mechanisms: list[dict],
                    candidate: str | None = None) -> dict:
    # По умолчанию личность кандидата производится от id раунда: синтетические
    # раунды моделируют обычный маршрут, где каждый заход идёт по перечеканенному
    # кандидату. Тесты на невыясненный повтор передают candidate явно.
    return {
        "id": round_id,
        "terminal": "verdict",
        "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                       "line": SYNTHETIC_LINE},
        # Каноническая форма личности: 16 hex, детерминированно из подписи.
        "candidate": candidate if candidate is not None
        else hashlib.sha256(f"cand-{round_id}".encode()).hexdigest()[:16],
        "declared": {"verdict": verdict, "mechanisms": mechanisms},
    }


def mechanism(surface: str, defect_class: str, **extra) -> dict:
    item = {"surface": surface, "defectClass": defect_class}
    item.update(extra)
    return item


# ---------------------------------------------------------------------------
# 1. контракт политики
# ---------------------------------------------------------------------------

policy = rule.load_policy(ROOT / POLICY_FILE)
binding = rule.live_policy_binding(policy, ROOT)

check("policy: статус advisory объявлен",
      policy.get("status") == "advisory", str(policy.get("status")))
check("policy: ключ механизма — (file, category)",
      policy["mechanismKey"]["default"] == ["file", "category"])
check("policy: слияние ключей разрешено, разделение — нет",
      policy["mechanismKey"]["mergeOnly"] is True)
check("policy: повтор считается по РАЗНЫМ раундам, минимум два",
      int(policy["mechanismKey"]["distinctRoundsRequired"]) == 2)
check("policy: у класса verdict счёт включён, у precondition и transport — выключен",
      policy["terminalClasses"]["verdict"]["counts"] is True
      and policy["terminalClasses"]["precondition"]["counts"] is False
      and policy["terminalClasses"]["transport"]["counts"] is False)
check("policy: R3 проверяет привязку бухгалтерии первым",
      policy["precedence"][0] == "ROUTE_DEFECT", str(policy["precedence"]))
check("policy: REDESIGN_OR_DISCARD раньше CLOSE — иначе зелёный сэмпл закрывал бы взведённый повтор",
      policy["precedence"].index("REDESIGN_OR_DISCARD") < policy["precedence"].index("CLOSE"))

policy_text = json.dumps(policy, ensure_ascii=False)
for forbidden in ("maxRounds", "roundCap", "maxAttempts", "roundLimit"):
    check(f"policy: потолка раундов нет ({forbidden})", forbidden not in policy_text)

# Ослабление контракта обязано отвергаться загрузчиком.
for name, mutate in (
    ("mergeOnly=false", lambda p: p["mechanismKey"].__setitem__("mergeOnly", False)),
    ("distinctRounds=1", lambda p: p["mechanismKey"].__setitem__("distinctRoundsRequired", 1)),
    ("ключ по severity", lambda p: p["mechanismKey"].__setitem__("default", ["file", "severity"])),
    ("схема подменена", lambda p: p.__setitem__("schema", "something-else")),
    ("статус не advisory", lambda p: p.__setitem__("status", "gate")),
    ("введён потолок раундов", lambda p: p.__setitem__("maxRounds", 3)),
    ("потолок спрятан в примечании",
     lambda p: p.__setitem__("note", "roundCap is 5")),
    ("порядок применения переставлен",
     lambda p: p.__setitem__("precedence", ["CLOSE", "ROUTE_DEFECT",
                                            "REDESIGN_OR_DISCARD",
                                            "RECURRENCE_UNCONFIRMED",
                                            "ROUTE_REPAIR", "CONTINUE"])),
    ("вердикт объявлен транспортом",
     lambda p: p["terminalClasses"]["transport"].__setitem__(
         "values", ["UNAVAILABLE", "TIMEOUT", "ABORTED", "BLOCKED"])),
    ("транспорт объявлен считаемым",
     lambda p: p["terminalClasses"]["transport"].__setitem__("counts", True)),
    ("вердикты объявлены несчитаемыми",
     lambda p: p["terminalClasses"]["verdict"].__setitem__("counts", False)),
    ("привязка бухгалтерии обезоружена",
     lambda p: p["policyBinding"].__setitem__("ledgerPath", "")),
    # Ослабление привязки ПО ЗНАЧЕНИЮ: проверка непустоты строки это пропускала,
    # и критерии в статусе pending считались бы выровненными — при том что
    # продюсер отказывает по ним терминалом класса precondition.
    ("требуемый статус критериев ослаблен до pending",
     lambda p: p["policyBinding"].__setitem__("requireCriteriaStatus", "pending")),
    ("требуемый статус критериев обнулён",
     lambda p: p["policyBinding"].__setitem__("requireCriteriaStatus", None)),
    ("требуемый статус критериев убран",
     lambda p: p["policyBinding"].pop("requireCriteriaStatus", None)),
    ("требование префикса выключено",
     lambda p: p["policyBinding"].__setitem__("requireCriteriaPrefix", False)),
    ("требование префикса подменено истинным не-булевым",
     lambda p: p["policyBinding"].__setitem__("requireCriteriaPrefix", 1)),
    ("требование префикса убрано",
     lambda p: p["policyBinding"].pop("requireCriteriaPrefix", None)),
):
    checks += 1
    mutated = copy.deepcopy(policy)
    mutate(mutated)
    # Временные файлы живут ВНЕ проверяемого дерева: оракул не имеет права
    # трогать кандидата, которого судит (изолированный прогон машинной ноги
    # ловит это как мутацию), а фиксированные имена внутри дерева ещё и
    # сталкивали бы параллельные прогоны.
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-") as scratch:
        written = Path(scratch) / "mutated-policy.json"
        written.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        try:
            rule.load_policy(written)
        except rule.StopRuleError:
            pass
        else:
            failures.append(f"мутация политики принята: {name}")


# ---------------------------------------------------------------------------
# 2. реплей записанных историй
# ---------------------------------------------------------------------------

HISTORIES = tuple(HISTORY_FILES)
# Грубая группировка ключа — не вторая история, а тот же R6 под другим ключом.
# Хранить её отдельным файлом значило бы держать почти дословную копию записи:
# два источника правды об одних и тех же раундах расходятся молча.
COARSE_OVERLAY = "tests/references/stop-rule/r6-coarse-grouping.derived.json"


def coarse_r6() -> dict:
    overlay = json.loads((ROOT / COARSE_OVERLAY).read_text(encoding="utf-8"))
    document = load("r6")
    document = copy.deepcopy(document)
    document["unit"] = overlay["unit"]
    document["subject"] = overlay["subject"]
    document["mergeKeys"] = overlay["mergeKeys"]
    document["expected"] = overlay["expected"]
    document.pop("antiGoodhart", None)
    return document

decisions: dict[str, dict] = {}
for name in HISTORIES:
    history = load(name)
    decision = rule.decide(history, policy, ROOT)
    decisions[name] = decision
    expected = history.get("expected") or {}
    check(f"{name}: терминал совпадает с записанным ожиданием",
          decision["terminal"] == expected.get("terminal"),
          f"{decision['terminal']} != {expected.get('terminal')}")
    if expected.get("atRound"):
        check(f"{name}: раунд срабатывания совпадает",
              decision["atRound"] == expected["atRound"],
              f"{decision['atRound']} != {expected['atRound']}")
    if expected.get("counters"):
        check(f"{name}: счётчики классов терминалов совпадают",
              decision["counters"] == expected["counters"],
              json.dumps(decision["counters"], ensure_ascii=False))
    recorded = history.get("recordedDecision") or {}
    if recorded.get("terminal") and decision["terminal"] != recorded["terminal"]:
        check(f"{name}: расхождение с решением владельца объявлено явно",
              bool(history.get("divergence") or expected.get("note")),
              "терминал разошёлся с записанным решением, а расхождение не объявлено")

# S04b: правило обязано воспроизвести фактическое решение владельца по D1
# и отдельно назвать второй, не признанный тогда повтор.
s04b = decisions["s04b"]
check("s04b: механизм D1 назван поимённо",
      s04b.get("mechanism", "").endswith("::security"), str(s04b.get("mechanism")))
recurring = {item["mechanism"]: item["rounds"] for item in s04b["recurring"]}
check("s04b: второй повтор (агрегация пре-флайта) тоже назван",
      any(key.endswith("::correctness") and len(rounds) >= 4
          for key, rounds in recurring.items()),
      json.dumps(recurring, ensure_ascii=False))
check("s04b: пробел в записи назван, а не замолчан",
      [gap["id"] for gap in s04b["knownGaps"]] == ["PUB9"])

# LPD-003-1: девять «незакрывшихся» заходов — это три вердикта.
pub = decisions["lpd003-1-publication"]
check("lpd003-1: вердиктов ровно три при десяти заходах",
      pub["counters"]["verdict"] == 3 and pub["attempts"] == 10,
      json.dumps(pub["counters"], ensure_ascii=False))
check("lpd003-1: транспорт и предусловие не попали в вердикты",
      pub["counters"]["transport"] == 5 and pub["counters"]["precondition"] == 2)

# GPG-001: безымянные находки не склеены в один псевдо-механизм.
gpg = decisions["gpg-001-broker-policy"]
check("gpg-001: находки без поверхности и класса не засчитаны в повтор",
      len(gpg["unkeyable"]) == 5, str(len(gpg["unkeyable"])))
check("gpg-001: повторы названы по реальным ключам, без ключей-заглушек",
      all("::" in item["mechanism"] and "unnamed" not in item["mechanism"]
          for item in gpg["recurring"]),
      json.dumps([item["mechanism"] for item in gpg["recurring"]], ensure_ascii=False))

# R6: пересказ помечен пересказом.
r6 = decisions["r6"]
check("r6: ни один раунд не выдан за машинную улику",
      r6["provenance"]["report"] == 0 and r6["provenance"]["narrative"] == 12,
      json.dumps(r6["provenance"], ensure_ascii=False))
check("r6: опровергнутая находка не засчитана в повтор",
      len(r6["refuted"]) == 1, str(r6["refuted"]))

# Чувствительность к зернистости ключа измерена, а не спрятана.
coarse_document = coarse_r6()
coarse_decision = rule.decide(coarse_document, policy, ROOT)
decisions["r6-coarse-grouping"] = coarse_decision
check("r6: грубая группировка переворачивает терминал — и это объявлено",
      coarse_decision["terminal"] == coarse_document["expected"]["terminal"] == "REDESIGN_OR_DISCARD"
      and r6["terminal"] == "CLOSE", coarse_decision["terminal"])
check("грубая группировка срабатывает на объявленном раунде",
      coarse_decision["atRound"] == coarse_document["expected"]["atRound"],
      f"{coarse_decision['atRound']} != {coarse_document['expected']['atRound']}")
check("расхождение грубой группировки с записанным решением объявлено",
      bool(str(coarse_document["expected"].get("note") or "").strip()))


# ---------------------------------------------------------------------------
# 3. поведенческие гарантии
# ---------------------------------------------------------------------------

# Анти-Goodhart: потолок раундов остановил бы R6 на живых дефектах, правило — нет.
r6_history = load("r6")
verdict_rounds = [r for r in r6_history["rounds"] if r["terminal"] == "verdict"]
for cap in (3, 8):
    truncated = synthetic(verdict_rounds[:cap], unit=f"r6-cap-{cap}")
    decision = rule.decide(truncated, policy, ROOT)
    check(f"анти-Goodhart: на первых {cap} раундах R6 правило говорит CONTINUE",
          decision["terminal"] == "CONTINUE", decision["terminal"])

# Терминалы ПОВТОРА не зависят от порядка раундов (повтор — свойство
# множества); терминалы ЗАКРЫТИЯ зависят от ХВОСТА по построению — CLOSE
# требует, чтобы последним суждением был чистый PASSED, и это проверено выше
# («срыв маршрута ПОСЛЕ зелёного не закрывает маршрут»). Прежняя формулировка
# «терминал не зависит от порядка» переобещала (находка ревьюера r28).
gpg_history = load("gpg-001-broker-policy")
shuffled = copy.deepcopy(gpg_history)
shuffled["rounds"] = list(reversed(shuffled["rounds"]))
shuffled_decision = rule.decide(shuffled, policy, ROOT)
check("порядок раундов не меняет терминал повтора",
      shuffled_decision["terminal"] == gpg["terminal"])
check("порядок раундов меняет только раунд срабатывания",
      shuffled_decision["atRound"] != gpg["atRound"],
      f"{shuffled_decision['atRound']} == {gpg['atRound']}")

# Поломки маршрута не влияют на решение.
pub_history = load("lpd003-1-publication")
without_noise = copy.deepcopy(pub_history)
without_noise["rounds"] = [r for r in without_noise["rounds"] if r["terminal"] == "verdict"]
check("транспорт и предусловие не меняют терминал",
      rule.decide(without_noise, policy, ROOT)["terminal"] == pub["terminal"])

# Дубль внутри одного отчёта повтором не является.
duplicate_round = narrative_round("only", "BLOCKED", [
    mechanism("одна поверхность", "correctness"),
    mechanism("одна поверхность", "correctness"),
])
check("дубль находки внутри одного раунда не взводит повтор",
      rule.decide(synthetic([duplicate_round]), policy, ROOT)["terminal"] == "CONTINUE")

# Тот же ключ в двух раундах — взводит.
two_rounds = [
    narrative_round("a", "BLOCKED", [mechanism("одна поверхность", "correctness")]),
    narrative_round("b", "BLOCKED", [mechanism("одна поверхность", "correctness")]),
]
check("тот же ключ в двух раундах взводит REDESIGN_OR_DISCARD",
      rule.decide(synthetic(two_rounds), policy, ROOT)["terminal"] == "REDESIGN_OR_DISCARD")

# И зелёный сэмпл его не снимает (R5).
armed_then_pass = two_rounds + [narrative_round("c", "PASSED", [])]
armed_decision = rule.decide(synthetic(armed_then_pass), policy, ROOT)
check("PASSED не закрывает маршрут при взведённом повторе",
      armed_decision["terminal"] == "REDESIGN_OR_DISCARD", armed_decision["terminal"])

# PASSED_WITH_WARNINGS не закрытие ни при каких условиях.
warned = [narrative_round("a", "BLOCKED", [mechanism("s", "correctness")]),
          narrative_round("b", "PASSED_WITH_WARNINGS", [])]
check("PASSED_WITH_WARNINGS не закрывает маршрут",
      rule.decide(synthetic(warned), policy, ROOT)["terminal"] == "CONTINUE")

# Регрессия чинится в корне и в повторы не идёт.
regression_rounds = [
    narrative_round("a", "BLOCKED", [mechanism("s", "correctness", regression=True, why="откат ранее существовавшей гарантии")]),
    narrative_round("b", "BLOCKED", [mechanism("s", "correctness", regression=True, why="откат ранее существовавшей гарантии")]),
]
regression_decision = rule.decide(synthetic(regression_rounds), policy, ROOT)
check("регрессии не взводят повтор механизма",
      regression_decision["terminal"] == "CONTINUE", regression_decision["terminal"])
check("регрессии названы отдельным списком",
      len(regression_decision["regressions"]) == 2)

# Опровергнутая находка тоже не взводит.
refuted_rounds = [
    narrative_round("a", "BLOCKED", [mechanism("s", "correctness", refuted=True, why="опровергнута фактами")]),
    narrative_round("b", "BLOCKED", [mechanism("s", "correctness", refuted=True, why="опровергнута фактами")]),
]
check("опровергнутые находки не взводят повтор",
      rule.decide(synthetic(refuted_rounds), policy, ROOT)["terminal"] == "CONTINUE")

# Слияние ключей срабатывает раньше, чем раздельные ключи.
merged = synthetic([
    narrative_round("a", "BLOCKED", [mechanism("глоб A", "security")]),
    narrative_round("b", "BLOCKED", [mechanism("глоб B", "correctness")]),
], mergeKeys=[{"label": "глоб", "members": [["глоб A", "security"], ["глоб B", "correctness"]]}])
check("объявленное слияние ключей взводит правило раньше",
      rule.decide(merged, policy, ROOT)["terminal"] == "REDESIGN_OR_DISCARD")


# ---------------------------------------------------------------------------
# 4. мутации: fail-closed вход
# ---------------------------------------------------------------------------

rejects("раунд без класса терминала",
        synthetic([{"id": "x", "provenance": {"class": "absent"}}]), policy)
rejects("раунд с выдуманным классом терминала",
        synthetic([{"id": "x", "terminal": "maybe", "provenance": {"class": "absent"}}]), policy)
rejects("раунд без провенанса",
        synthetic([{"id": "x", "terminal": "verdict"}]), policy)
rejects("два раунда с одним id",
        synthetic([narrative_round("a", "PASSED", []), narrative_round("a", "PASSED", [])]), policy)
rejects("BLOCKED без находок",
        synthetic([narrative_round("a", "BLOCKED", [])]), policy)
rejects("пересказ без объявленных механизмов",
        synthetic([{"id": "a", "terminal": "verdict",
                    "provenance": {"class": "narrative", "path": "tests/verify_stop_rule.py"},
                    "declared": {"verdict": "BLOCKED"}}]), policy)
rejects("пересказ без документа-источника",
        synthetic([{"id": "a", "terminal": "verdict",
                    "provenance": {"class": "narrative", "path": "tests/does-not-exist.md"},
                    "declared": {"verdict": "BLOCKED",
                                 "mechanisms": [{"surface": "s", "defectClass": "c"}]}}]), policy)
rejects("механизм без класса дефекта",
        synthetic([narrative_round("a", "BLOCKED", [{"surface": "s"}])]), policy)
rejects("вердикт вне словаря политики",
        synthetic([narrative_round("a", "MAYBE", [])]), policy)
rejects("группа слияния из повторённого ключа",
        synthetic([narrative_round("a", "PASSED", [])],
                  mergeKeys=[{"label": "x", "members": [["f", "c"], ["f", "c"]]}]), policy)
check("политика объявляет личность кандидата необязательной и называет цену отсутствия",
      policy["candidateIdentity"].get("optional") is True
      and "requiredFor" not in policy["candidateIdentity"]
      and bool(str(policy["candidateIdentity"].get("optionalNote") or "").strip()))
rejects("группа слияния из одного ключа",
        synthetic([narrative_round("a", "PASSED", [])],
                  mergeKeys=[{"label": "x", "members": [["f", "c"]]}]), policy)
rejects("РАЗДЕЛЕНИЕ ключа между двумя группами",
        synthetic([narrative_round("a", "PASSED", [])],
                  mergeKeys=[{"label": "x", "members": [["f", "c"], ["g", "c"]]},
                             {"label": "y", "members": [["f", "c"], ["h", "c"]]}]), policy)
rejects("criteriaPresent непустой строкой вместо булева",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic",
                                 "criteriaPresent": "да"}), policy)
rejects("criteriaPresent числом",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic",
                                 "criteriaPresent": 1}), policy)
rejects("дефект привязки не отменяет проверку провенанса раундов",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "d0f631ca1ddba8db",
                    "provenance": {"class": "report", "path": EVIDENCE_FILES[0],
                                   "sha256": "0" * 64}}],
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "other-unit",
                                 "criteriaPresent": True}), policy)
rejects("дефект привязки не отменяет проверку исхода раунда",
        synthetic([{"id": "a", "terminal": "transport", "outcome": "LOOKS_FINE",
                    "provenance": {"class": "absent"}}],
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "other-unit",
                                 "criteriaPresent": True}), policy)
rejects("привязка политики без поля criteriaPresent",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic"}), policy)

# Диспозиции находок: снятие со счёта повторов обязано быть обоснованным.
s04b_for_dispositions = load("s04b")
first_report = next(r for r in s04b_for_dispositions["rounds"]
                    if r["provenance"]["class"] == "report")

for name, disposition in (
    ("диспозиция без основания", {"finding": 0, "refuted": True}),
    ("диспозиция без флага", {"finding": 0, "why": "потому что"}),
    ("диспозиция на несуществующую находку", {"finding": 99, "refuted": True, "why": "x"}),
    ("диспозиция не объект", "refuted"),
):
    mutated_history = copy.deepcopy(s04b_for_dispositions)
    for entry in mutated_history["rounds"]:
        if entry["id"] == first_report["id"]:
            entry["dispositions"] = [disposition]
    rejects(name, mutated_history, policy)

# Обоснованная диспозиция действительно снимает находку со счёта повторов.
disposed = synthetic(two_rounds)
disposed["rounds"] = copy.deepcopy(two_rounds)
disposed["rounds"][1]["declared"]["mechanisms"][0]["refuted"] = True
disposed["rounds"][1]["declared"]["mechanisms"][0]["why"] = "опровергнута фактами"
check("обоснованное опровержение снимает второй раунд со счёта повтора",
      rule.decide(disposed, policy, ROOT)["terminal"] == "CONTINUE")

# Провенанс пересказа обязан цитировать существующую строку.
rejects("пересказ без цитируемой строки",
        synthetic([{"id": "a", "terminal": "verdict",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE},
                    "declared": {"verdict": "BLOCKED",
                                 "mechanisms": [{"surface": "s", "defectClass": "c"}]}}]), policy)
for bad_line in (0, -1, 10 ** 9, "12", True):
    rejects(f"пересказ с негодной строкой {bad_line!r}",
            synthetic([{"id": "a", "terminal": "verdict",
                        "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                       "line": bad_line},
                        "declared": {"verdict": "BLOCKED",
                                     "mechanisms": [{"surface": "s", "defectClass": "c"}]}}]),
            policy)
rejects("пересказ с путём за пределы репозитория",
        synthetic([{"id": "a", "terminal": "verdict",
                    "provenance": {"class": "narrative", "path": "../../etc/passwd", "line": 1},
                    "declared": {"verdict": "BLOCKED",
                                 "mechanisms": [{"surface": "s", "defectClass": "c"}]}}]), policy)

# Раунд без сохранённого содержания судится по словарю СВОЕГО класса терминала.
rejects("раунд без содержания с выдуманным исходом",
        synthetic([{"id": "a", "terminal": "precondition", "outcome": "LOOKS_FINE",
                    "provenance": {"class": "absent"}}]), policy)
rejects("вердикт без всякой опоры на запись",
        synthetic([{"id": "a", "terminal": "verdict", "outcome": "BLOCKED",
                    "provenance": {"class": "absent"}}]), policy)
rejects("транспортный раунд с вердиктным исходом",
        synthetic([{"id": "a", "terminal": "transport", "outcome": "PASSED",
                    "provenance": {"class": "absent"}}]), policy)
rejects("раунд предусловия с транспортным исходом",
        synthetic([{"id": "a", "terminal": "precondition", "outcome": "UNAVAILABLE",
                    "provenance": {"class": "absent"}}]), policy)
# Вердикт, чьё содержание не сохранилось, остаётся законным — но только с
# цитатой записи и объявленной причиной.
unrecorded_verdict = synthetic([{
    "id": "a", "terminal": "verdict", "candidate": "985299dad5005202",
    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE, "line": SYNTHETIC_LINE},
    "declared": {"verdict": "BLOCKED", "contentRecorded": False,
                 "why": "отчёт не сохранён"}}])
check("вердикт с цитатой и объявленной утратой содержания принимается и виден отдельно",
      rule.decide(unrecorded_verdict, policy, ROOT)["contentMissing"] == ["a"])
rejects("утрата содержания без основания",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "2e7d2c03a9507ae2",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "contentRecorded": False}}]), policy)
rejects("утрата содержания вместе с объявленными механизмами",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "2e7d2c03a9507ae2",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "contentRecorded": False,
                                 "why": "нет", "mechanisms": [{"surface": "s",
                                                               "defectClass": "c"}]}}]),
        policy)
rejects("contentRecorded нелогического типа",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "2e7d2c03a9507ae2",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "contentRecorded": "no"}}]), policy)

# Пересказ не может снять находку со счёта дешевле, чем отчёт.
rejects("пересказ снимает находку без основания",
        synthetic([narrative_round("a", "BLOCKED",
                                   [mechanism("s", "correctness", refuted=True)])]), policy)
rejects("пересказ помечает регрессию без основания",
        synthetic([narrative_round("a", "BLOCKED",
                                   [mechanism("s", "correctness", regression=True)])]), policy)
rejects("нелогический флаг диспозиции в пересказе",
        synthetic([narrative_round("a", "BLOCKED",
                                   [mechanism("s", "correctness", refuted="yes",
                                              why="основание")])]), policy)

# Повтор без установленной смены кандидата вердикта не выносит.
same_candidate = [
    narrative_round("a", "BLOCKED", [mechanism("одна поверхность", "correctness")],
                    candidate="149403d6237fdb69"),
    narrative_round("b", "BLOCKED", [mechanism("одна поверхность", "correctness")],
                    candidate="149403d6237fdb69"),
]
same_candidate_decision = rule.decide(synthetic(same_candidate), policy, ROOT)
check("повтор на ОДНОМ кандидате даёт RECURRENCE_UNCONFIRMED, а не вердикт",
      same_candidate_decision["terminal"] == "RECURRENCE_UNCONFIRMED",
      same_candidate_decision["terminal"])
check("невыясненный повтор называет механизм",
      same_candidate_decision.get("mechanism") == "одна поверхность::correctness")

no_candidate = []
for round_id in ("a", "b"):
    entry = narrative_round(round_id, "BLOCKED", [mechanism("s", "correctness")])
    entry.pop("candidate")
    no_candidate.append(entry)
check("повтор без объявленных кандидатов тоже не выносит вердикта",
      rule.decide(synthetic(no_candidate), policy, ROOT)["terminal"] == "RECURRENCE_UNCONFIRMED")

rejects("пустая личность кандидата",
        synthetic([{**narrative_round("a", "PASSED", []), "candidate": "  "}]), policy)
rejects("личность кандидата не строкой",
        synthetic([{**narrative_round("a", "PASSED", []), "candidate": 42}]), policy)

# Сорванный маршрут получает СВОЙ исход, а не приглашение на новый раунд.
only_transport = synthetic([
    {"id": "t1", "terminal": "transport", "outcome": "UNAVAILABLE",
     "provenance": {"class": "absent"}}])
transport_decision = rule.decide(only_transport, policy, ROOT)
check("история без единого вердикта даёт ROUTE_REPAIR",
      transport_decision["terminal"] == "ROUTE_REPAIR", transport_decision["terminal"])
check("ROUTE_REPAIR берёт действие из класса сорвавшегося терминала",
      transport_decision["fix"] == policy["terminalClasses"]["transport"]["action"],
      transport_decision["fix"])

blocked_then_transport = synthetic([
    narrative_round("a", "BLOCKED", [mechanism("s", "correctness")]),
    {"id": "t1", "terminal": "transport", "outcome": "TIMEOUT",
     "provenance": {"class": "absent"}}])
check("сорванный маршрут после BLOCKED даёт ROUTE_REPAIR, а не CONTINUE",
      rule.decide(blocked_then_transport, policy, ROOT)["terminal"] == "ROUTE_REPAIR")

precondition_only = synthetic([
    {"id": "p1", "terminal": "precondition", "outcome": "UNVERIFIED",
     "provenance": {"class": "absent"}}])
check("история только из предусловий даёт ROUTE_REPAIR",
      rule.decide(precondition_only, policy, ROOT)["terminal"] == "ROUTE_REPAIR")

pass_then_transport = synthetic([
    narrative_round("a", "PASSED", []),
    {"id": "t1", "terminal": "transport", "outcome": "TIMEOUT",
     "provenance": {"class": "absent"}}])
check("срыв маршрута ПОСЛЕ зелёного не закрывает маршрут",
      rule.decide(pass_then_transport, policy, ROOT)["terminal"] == "ROUTE_REPAIR",
      rule.decide(pass_then_transport, policy, ROOT)["terminal"])
check("закрытие остаётся, когда последний раунд и есть чистый PASS",
      rule.decide(synthetic([
          {"id": "t1", "terminal": "transport", "outcome": "TIMEOUT",
           "provenance": {"class": "absent"}},
          narrative_round("a", "PASSED", []),
      ]), policy, ROOT)["terminal"] == "CLOSE")

check("политика перечисляет оба новых терминала в порядке применения",
      policy["precedence"] == ["ROUTE_DEFECT", "REDESIGN_OR_DISCARD",
                               "RECURRENCE_UNCONFIRMED", "SURFACE_TREADMILL",
                               "ROUTE_REPAIR", "CLOSE", "CONTINUE"],
      json.dumps(policy["precedence"], ensure_ascii=False))

# Нев-вердиктный раунд не может числиться машинной уликой.
rejects("предусловие объявляет себя машинной уликой",
        synthetic([{"id": "p1", "terminal": "precondition", "outcome": "UNVERIFIED",
                    "provenance": {"class": "report",
                                   "path": EVIDENCE_FILES[0], "sha256": "0" * 64}}]), policy)
rejects("транспорт объявляет себя машинной уликой",
        synthetic([{"id": "t1", "terminal": "transport", "outcome": "UNAVAILABLE",
                    "provenance": {"class": "report"}}]), policy)

# Флаги диспозиций в отчётах типизированы так же строго, как в пересказе.
for bad_flag in ("refuted", 1, ["refuted"]):
    mutated_history = copy.deepcopy(s04b_for_dispositions)
    for entry in mutated_history["rounds"]:
        if entry["id"] == first_report["id"]:
            entry["dispositions"] = [{"finding": 0, "refuted": bad_flag, "why": "основание"}]
    rejects(f"нелогический флаг диспозиции в отчёте: {bad_flag!r}", mutated_history, policy)

# Привязка бухгалтерии учитывает требуемый статус критериев.
check("живая привязка называет требуемый статус критериев",
      binding.get("requiredCriteriaStatus") == policy["policyBinding"]["requireCriteriaStatus"],
      str(binding.get("requiredCriteriaStatus")))
check("выровненность требует и совпадения юнита, и требуемого статуса критериев",
      binding["aligned"] == (binding["contractUnit"] == binding["ledgerUnit"]
                            and bool(binding["criteriaPresent"])
                            and bool(binding["statusSatisfied"])))
def binding_in(unit: str, contract_unit: str, statuses: list[str]) -> dict:
    """Собрать пару леджеров во временном корне и спросить у правила вердикт.

    Проверять требуемый статус критериев на ЖИВОМ репозитории нельзя: там все
    критерии уже passed, и мутация «игнорировать статус» осталась бы незамеченной.
    """
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-binding-") as scratch:
        root = Path(scratch)
        (root / ".itd").mkdir()
        (root / ".itd-memory").mkdir()
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
            "activeFollowup": {"unitId": contract_unit},
            "criteria": [{"id": f"{unit}-{index}", "status": status}
                         for index, status in enumerate(statuses, start=1)],
        }, ensure_ascii=False), encoding="utf-8")
        (root / ".itd-memory" / "STATE.json").write_text(json.dumps({
            "currentUnit": {"id": unit},
        }, ensure_ascii=False), encoding="utf-8")
        return rule.live_policy_binding(policy, root)


# Префикс сравнивается по границе идентификатора, а не по строке.
def binding_with_ids(unit: str, contract_unit: str, ids: list[tuple[str, str]]) -> dict:
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-binding-") as scratch:
        root = Path(scratch)
        (root / ".itd").mkdir()
        (root / ".itd-memory").mkdir()
        (root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
            "activeFollowup": {"unitId": contract_unit},
            "criteria": [{"id": ident, "status": status} for ident, status in ids],
        }, ensure_ascii=False), encoding="utf-8")
        (root / ".itd-memory" / "STATE.json").write_text(json.dumps({
            "currentUnit": {"id": unit}}, ensure_ascii=False), encoding="utf-8")
        return rule.live_policy_binding(policy, root)


neighbour = binding_with_ids("U-1", "U-1", [("U-10-a", "passed")])
check("критерий соседнего юнита с общим префиксом не считается своим",
      neighbour["criteriaTotal"] == 0 and neighbour["aligned"] is False,
      json.dumps(neighbour, ensure_ascii=False))
own_exact = binding_with_ids("U-1", "U-1", [("U-1", "passed"), ("U-1-a", "passed")])
check("свои критерии считаются и точным совпадением, и префиксом с дефисом",
      own_exact["criteriaTotal"] == 2 and own_exact["aligned"] is True)

pending_binding = binding_in("U-1", "U-1", ["passed", "pending"])
check("критерий в статусе pending снимает выровненность",
      pending_binding["aligned"] is False, json.dumps(pending_binding, ensure_ascii=False))
check("частичный статус виден в диагностике",
      (pending_binding["criteriaMatchingStatus"], pending_binding["criteriaTotal"]) == (1, 2))
all_passed_binding = binding_in("U-1", "U-1", ["passed", "passed"])
check("все критерии в требуемом статусе дают выровненность",
      all_passed_binding["aligned"] is True)
foreign_binding = binding_in("U-1", "U-OTHER", ["passed"])
check("чужой юнит в контракте снимает выровненность независимо от статусов",
      foreign_binding["aligned"] is False)
no_criteria_binding = binding_in("U-1", "U-1", [])
check("юнит без критериев не считается выровненным",
      no_criteria_binding["aligned"] is False)

check("статус критериев считается по всем критериям юнита, а не по одному",
      binding["statusSatisfied"] == (binding["criteriaTotal"] > 0
                                     and binding["criteriaMatchingStatus"] == binding["criteriaTotal"]))

# Личности кандидатов пересчитываются из журналов промптов там, где журнал
# есть на хосте: объявленное значение обязано совпасть с вычисленным.
recomputed = 0
for history_name in HISTORIES:
    document = load(history_name)
    source = document.get("candidateSource") or {}
    if source.get("kind") != "prompt-ledger-diff-sha256":
        continue
    prefix = source["prefix"]
    for entry in document["rounds"]:
        declared_candidate = entry.get("candidate")
        if not declared_candidate:
            continue
        # Тот же поиск, что у правила: две копии разошлись бы молча, и сверка
        # смотрела бы не в те файлы, что пересчёт.
        ledger = rule.round_ledger_path(source, str(entry["id"]), ROOT)
        if ledger is None:
            continue
        recomputed += 1
        checks += 1
        computed = rule.candidate_identity_from_ledger(ledger)
        if computed != declared_candidate:
            failures.append(
                f"{history_name}/{entry['id']}: объявленная личность кандидата "
                f"не совпадает с пересчитанной из {ledger.name}"
            )
        checks += 1
        if declared_candidate == rule.sha256_of(ledger)[:16]:
            failures.append(
                f"{history_name}/{entry['id']}: личность равна хешу ВСЕГО журнала — "
                f"обёртка промпта не должна входить в идентичность кандидата"
            )
# Журналы промптов принадлежат ХОСТУ: они git-ignored и в изолированном дереве
# машинной ноги отсутствуют по построению. Требовать их наличия значило бы
# делать оракул false-red там, где он обязан быть зелёным (класс LPD-003-1).
# Поэтому проверяется совпадение КАЖДОГО присутствующего журнала, а количество
# объявляется отдельной строкой, а не порогом.
declared_candidates = sum(
    1 for name in HISTORIES for entry in load(name)["rounds"]
    if entry.get("candidate")
)
# ТОЧНОЕ число, а не порог: «>= 20» пропускал бы тихую потерю четырёх личностей
# при правке историй (находка ревьюера, раунд r20). Правишь истории — правь
# константу той же правкой, это и есть смысл точного равенства.
check("объявленные личности кандидатов есть у каждого записанного раунда",
      declared_candidates == 42, str(declared_candidates))
# Полнота: в истории с журнальным источником КАЖДЫЙ вердикт-раунд с
# машинным отчётом обязан объявлять личность — молчаливый пропуск раунда
# делал бы его невидимым для сверки смены кандидата.
for history_name in HISTORIES:
    document = load(history_name)
    if (document.get("candidateSource") or {}).get("kind") != "prompt-ledger-diff-sha256":
        continue
    for entry in document["rounds"]:
        if entry.get("terminal") != "verdict":
            continue
        if (entry.get("provenance") or {}).get("class") != "report":
            continue
        checks += 1
        if not entry.get("candidate"):
            failures.append(
                f"{history_name}/{entry.get('id')}: вердикт с машинным отчётом "
                f"не объявил личность кандидата"
            )
available_ledgers = sum(
    1 for name in HISTORIES
    if (load(name).get("candidateSource") or {}).get("kind") == "prompt-ledger-diff-sha256"
    for entry in load(name)["rounds"]
    if entry.get("candidate")
    and rule.round_ledger_path(load(name)["candidateSource"], str(entry["id"]), ROOT) is not None
)
# Каждый ДОСТУПНЫЙ журнал обязан быть пересчитан: available == recomputed
# отличает «журналов нет по построению» (изоляция, класс LPD-003-1) от
# «журналы есть, но сверка их пропустила» (false-green, находка r20).
check("каждый доступный журнал промптов пересчитан",
      recomputed == available_ledgers,
      f"available={available_ledgers} recomputed={recomputed}")
print(f"CANDIDATE IDENTITIES: declared={declared_candidates} "
      f"available-ledgers={available_ledgers} "
      f"recomputed-from-host-ledgers={recomputed}"
      + ("" if recomputed else
         "  (журналы промптов host-owned и git-ignored: в изолированном дереве"
         " их нет по построению — это класс, а не красный)"))
# Ключевая гарантия исправления: личность нечувствительна к обёртке промпта и
# чувствительна к диффу. Проверяется на собранных журналах, а не на записи.
def synthetic_ledger(directory: Path, diff_text: str, wrapper: str) -> Path:
    written = directory / "ledger.jsonl"
    written.write_text("\n".join(json.dumps({
        "entry": "itd-prompt-ledger-entry-v1", "kind": "unit", "unitIndex": index,
        "prompt": (f"{wrapper}\nBEGIN UNTRUSTED DIFF UNIT\n{chunk}"
                   f"END UNTRUSTED DIFF UNIT\n{wrapper}\n"),
    }, ensure_ascii=False) for index, chunk in enumerate(diff_text.split("|"))) + "\n",
        encoding="utf-8")
    return written


for label, diff_text, wrapper in (("base", "diff-one\n|diff-two\n", "instructions v1"),
                                  ("wrapper", "diff-one\n|diff-two\n", "COMPLETELY OTHER WRAPPER"),
                                  ("diff", "diff-one\n|diff-CHANGED\n", "instructions v1")):
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-ledger-") as scratch:
        written = synthetic_ledger(Path(scratch), diff_text, wrapper)
        globals()[f"identity_{label}"] = rule.candidate_identity_from_ledger(written)
check("личность не меняется от правки обёртки промпта",
      identity_base == identity_wrapper, f"{identity_base} != {identity_wrapper}")
check("личность меняется от правки диффа",
      identity_base != identity_diff, f"{identity_base} == {identity_diff}")
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-ledger-") as scratch:
    wrapper_only = Path(scratch) / "ledger.jsonl"
    wrapper_only.write_text(json.dumps({
        "entry": "itd-prompt-ledger-entry-v1", "kind": "integration",
        "prompt": "инструкции ревьюеру без единого участка диффа\n",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    check("личность не выдумывается из журнала без участков диффа",
          rule.candidate_identity_from_ledger(wrapper_only) is None,
          str(rule.candidate_identity_from_ledger(wrapper_only)))
check("нежурнальный файл личности не даёт",
      rule.candidate_identity_from_ledger(ROOT / "tests" / "verify_stop_rule.py") is None)

# Замер, который прежний (по всему журналу) хеш прятал: в S04b раунды PUB5 и
# PUB6 судили ОДИН И ТОТ ЖЕ кандидат — первый дал PASSED, второй BLOCKED.
s04b_candidates = {entry["id"]: entry.get("candidate")
                   for entry in load("s04b")["rounds"] if entry.get("candidate")}
check("S04b: PUB5 и PUB6 стоят на одном кандидате",
      s04b_candidates.get("PUB5") == s04b_candidates.get("PUB6")
      and s04b_candidates.get("PUB5") is not None,
      f"{s04b_candidates.get('PUB5')} vs {s04b_candidates.get('PUB6')}")

# Точка ПРИМЕНЕНИЯ, а не только загрузки: критерии активного юнита в статусе
# pending обязаны давать невыровненную привязку, иначе правило обещало бы то,
# в чём маршрут откажет.
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-binding-") as scratch:
    fake_root = Path(scratch)
    (fake_root / ".itd").mkdir()
    (fake_root / ".itd-memory").mkdir()
    (fake_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
        "activeFollowup": {"unitId": "UNIT-7"},
        "criteria": [{"id": "UNIT-7-1-example", "status": "pending"}],
    }, ensure_ascii=False), encoding="utf-8")
    (fake_root / ".itd-memory" / "STATE.json").write_text(json.dumps({
        "currentUnit": {"id": "UNIT-7"},
    }, ensure_ascii=False), encoding="utf-8")
    pending_binding = rule.live_policy_binding(policy, fake_root)
    check("критерии в статусе pending не дают выровненной привязки",
          pending_binding["statusSatisfied"] is False
          and pending_binding["aligned"] is False,
          str(pending_binding))
    (fake_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
        "activeFollowup": {"unitId": "UNIT-7"},
        "criteria": [{"id": "UNIT-7-1-example", "status": "passed"}],
    }, ensure_ascii=False), encoding="utf-8")
    passed_binding = rule.live_policy_binding(policy, fake_root)
    check("те же критерии в статусе passed привязку выравнивают",
          passed_binding["aligned"] is True, str(passed_binding))
    # Граница префикса: критерий чужого юнита UNIT-70 своим не считается.
    (fake_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
        "activeFollowup": {"unitId": "UNIT-7"},
        "criteria": [{"id": "UNIT-70-1-foreign", "status": "passed"}],
    }, ensure_ascii=False), encoding="utf-8")
    # Вторая линия, независимая от заморозки: если ослабленная политика придёт
    # в точку применения МИМО load_policy, выравнивания всё равно не будет.
    smuggled = copy.deepcopy(policy)
    smuggled["policyBinding"]["requireCriteriaStatus"] = None
    (fake_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
        "activeFollowup": {"unitId": "UNIT-7"},
        "criteria": [{"id": "UNIT-7-1-example", "status": "pending"}],
    }, ensure_ascii=False), encoding="utf-8")
    smuggled_binding = rule.live_policy_binding(smuggled, fake_root)
    check("ослабленная мимо load_policy привязка не выравнивается",
          smuggled_binding["statusSatisfied"] is False
          and smuggled_binding["aligned"] is False,
          str(smuggled_binding))
    (fake_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(json.dumps({
        "activeFollowup": {"unitId": "UNIT-7"},
        "criteria": [{"id": "UNIT-70-1-foreign", "status": "passed"}],
    }, ensure_ascii=False), encoding="utf-8")
    foreign_binding = rule.live_policy_binding(policy, fake_root)
    check("критерий соседнего юнита UNIT-70 не засчитывается юниту UNIT-7",
          foreign_binding["criteriaPresent"] is False
          and foreign_binding["aligned"] is False,
          str(foreign_binding))

# Ключ механизма обязан зависеть от НАЗВАННОГО механизма, а не от написания:
# иначе повтор снимается пробелом или регистром, то есть ровно тем действием,
# против которого правило и написано (находка ревьюера, раунд r18).
check("краевые пробелы не создают нового механизма",
      rule.raw_key({"file": "a.py", "category": " security"})
      == rule.raw_key({"file": "a.py", "category": "security"}))
check("внутренние пробелы схлопываются",
      rule.raw_key({"file": "a.py", "category": "input  validation"})
      == rule.raw_key({"file": "a.py", "category": "input validation"}))
check("регистр категории не создаёт нового механизма",
      rule.raw_key({"file": "a.py", "category": "Security"})
      == rule.raw_key({"file": "a.py", "category": "security"}))
check("регистр ПУТИ механизмы не склеивает",
      rule.raw_key({"file": "A.py", "category": "security"})
      != rule.raw_key({"file": "a.py", "category": "security"}),
      "на регистрозависимой ФС это разные файлы")
check("краевые пробелы пути не создают нового механизма",
      rule.raw_key({"file": " a.py ", "category": "security"})
      == rule.raw_key({"file": "a.py", "category": "security"}))
check("разные механизмы остаются разными",
      rule.raw_key({"file": "a.py", "category": "security"})
      != rule.raw_key({"file": "a.py", "category": "correctness"}))

# Объявленное слияние обязано совпадать с ключом находки байт в байт ПОСЛЕ
# нормализации: две копии канонизации разошлись бы молча.
merge_map = rule.build_merge_map({"mergeKeys": [{
    "label": "группа", "members": [[" a.py ", " Security"], ["b.py", "path safety"]],
}]})
check("член mergeKeys нормализуется так же, как ключ находки",
      rule.mechanism_of({"file": "a.py", "category": "security"}, merge_map) == "группа",
      str(merge_map))
try:
    rule.build_merge_map({"mergeKeys": [{
        "label": "мнимая пара", "members": [["a.py", "security"], ["a.py", " Security "]],
    }]})
except rule.StopRuleError:
    check("два написания одного ключа группой из двух не делают", True)
else:
    check("два написания одного ключа группой из двух не делают", False)

# Поведенческая проверка целиком: повтор, записанный в двух написаниях, обязан
# опознаваться как ОДИН механизм и давать останов.
def whitespace_history() -> dict:
    base = load("s04b")
    rounds = []
    for index, spelling in enumerate((" security", "Security")):
        rounds.append({
            "id": f"w{index + 1}", "terminal": "verdict",
            "candidate": f"{index + 1:016x}",
            "provenance": {"class": "narrative",
                           "path": ".itd/DECISIONS.md", "line": 1},
            "declared": {"verdict": "BLOCKED", "mechanisms": [
                {"surface": "scripts/x.py", "defectClass": spelling},
            ]},
        })
    return {"schema": base["schema"], "unit": "WS-1",
            "orderSource": "синтетическая проверка написаний",
        "orderProvenance": {"class": "artifact-list"},
            "candidateSource": {"kind": "declared", "archived": False,
                                "note": "синтетика"},
            "policyBinding": {"contractUnit": "WS-1", "ledgerUnit": "WS-1",
                              "criteriaPresent": True},
            "rounds": rounds}


whitespace_decision = rule.decide(whitespace_history(), policy, ROOT)
check("повтор в двух написаниях опознан как один механизм",
      whitespace_decision["terminal"] == "REDESIGN_OR_DISCARD",
      whitespace_decision["terminal"])

# Редизайн после r19: закрытые словари проверяются и во внутренних функциях,
# личность кандидата имеет формат, объявленное сверяется с журналом.
# Путь и строка НАСТОЯЩИЕ: единственной причиной отказа обязано быть членство
# класса, иначе проверка проходила бы за счёт несуществующего файла и мутация
# «снять membership» переживала бы её молча.
try:
    rule.validate_provenance({"class": "forged", "path": ".itd/DECISIONS.md",
                              "line": 1}, "verdict", "direct", ROOT)
except rule.StopRuleError as exc:
    check("validate_provenance сам отвергает неизвестный класс",
          "must be one of" in str(exc), str(exc))
else:
    check("validate_provenance сам отвергает неизвестный класс", False)

for bad in ("z" * 16, "AB12CD34EF56AB12", "abc", "cand-x"):
    checks += 1
    try:
        rule.decide(synthetic([narrative_round(
            "a", "BLOCKED", [mechanism("a.py", "x")], candidate=bad)]),
            policy, ROOT)
    except rule.StopRuleError as exc:
        # Причина отказа обязана быть именно форматом личности.
        if "16 lowercase hex" not in str(exc):
            failures.append(f"личность {bad!r} отвергнута не форматом: {exc}")
    else:
        failures.append(f"личность {bad!r} принята — а это не вывод "
                        f"candidate_identity_from_ledger")

# Сверка объявленной личности с журналом: подделка — отказ, отсутствие — счёт.
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-idcheck-") as scratch:
    scratch_root = Path(scratch)
    (scratch_root / "ledgers").mkdir()
    (scratch_root / ".itd").mkdir()
    (scratch_root / ".itd" / "DECISIONS.md").write_text(
        "строка для пересказного провенанса\n", encoding="utf-8")
    written = synthetic_ledger(scratch_root / "ledgers", "diff-x\n|diff-y\n", "w")
    named = scratch_root / "ledgers" / "U-r1-prompt.md.ledger.jsonl"
    written.rename(named)
    true_identity = rule.candidate_identity_from_ledger(named)
    forged_identity = ("0" * 16 if true_identity != "0" * 16 else "1" * 16)
    id_history = {
        "schema": rule.HISTORY_SCHEMA, "unit": "U", "orderSource": "t",
        "orderProvenance": {"class": "artifact-list"},
        "candidateSource": {"kind": "prompt-ledger-diff-sha256", "prefix": "U",
                            "directories": ["ledgers"], "archived": False,
                            "note": "t"},
        "policyBinding": {"contractUnit": "U", "ledgerUnit": "U",
                          "criteriaPresent": True},
        "rounds": [{"id": "r1", "terminal": "verdict",
                    "candidate": forged_identity,
                    "provenance": {"class": "narrative",
                                   "path": ".itd/DECISIONS.md", "line": 1},
                    "declared": {"verdict": "BLOCKED", "mechanisms": [
                        {"surface": "a.py", "defectClass": "x"}]}}],
    }
    try:
        rule.decide(id_history, policy, scratch_root)
    except rule.StopRuleError:
        check("личность, опровергнутая журналом, роняет разбор", True)
    else:
        check("личность, опровергнутая журналом, роняет разбор", False)
    id_history["rounds"][0]["candidate"] = true_identity
    verified_decision = rule.decide(id_history, policy, scratch_root)
    check("совпавшая личность засчитана как проверенная",
          verified_decision["candidateIdentities"]
          == {"declared": 1, "verified": 1, "unverifiable": 0},
          str(verified_decision["candidateIdentities"]))
    # r26: вердикт-раунд без объявленной личности при ДОСТУПНОМ журнале — отказ.
    id_history["rounds"][0].pop("candidate")
    try:
        rule.decide(id_history, policy, scratch_root)
    except rule.StopRuleError as exc:
        check("умолчание личности при доступном журнале — отказ",
              "declares no candidate" in str(exc), str(exc))
    else:
        check("умолчание личности при доступном журнале — отказ", False)
    id_history["rounds"][0]["candidate"] = true_identity
    named.unlink()
    # Без журнала то же умолчание законно: журналы host-owned (класс LPD-003-1).
    id_history["rounds"][0].pop("candidate")
    no_ledger_no_declared = rule.decide(id_history, policy, scratch_root)
    check("умолчание личности без журнала — не отказ",
          isinstance(no_ledger_no_declared, dict))
    id_history["rounds"][0]["candidate"] = true_identity
    absent_decision = rule.decide(id_history, policy, scratch_root)
    check("отсутствие журнала — host-owned класс, а не отказ",
          absent_decision["candidateIdentities"]
          == {"declared": 1, "verified": 0, "unverifiable": 1},
          str(absent_decision["candidateIdentities"]))

# Ключи provenanceClasses политики совпадают с классами кода один в один:
# документированный ключ, прочитанный как класс, обязан БЫТЬ классом — иначе
# история по докам законна, а кодом отвергается (находка ревьюера, раунд r21).
check("классы провенанса политики и кода совпадают",
      tuple(sorted(policy["provenanceClasses"])) == tuple(sorted(rule.PROVENANCE_CLASSES)),
      f"{sorted(policy['provenanceClasses'])} vs {sorted(rule.PROVENANCE_CLASSES)}")

# Контрактные скаляры политики заморожены декларативной картой (r24):
for label, mutate_scalar in (
    ("порог различимых раундов поднят до 3",
     lambda p: p["mechanismKey"].__setitem__("distinctRoundsRequired", 3)),
    ("порог различимых раундов подан строкой",
     lambda p: p["mechanismKey"].__setitem__("distinctRoundsRequired", "2")),
    ("порог различимых раундов подан булевым",
     lambda p: p["mechanismKey"].__setitem__("distinctRoundsRequired", True)),
):
    checks += 1
    mutated = copy.deepcopy(policy)
    mutate_scalar(mutated)
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-") as scratch:
        written = Path(scratch) / "mutated-policy.json"
        written.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        try:
            rule.load_policy(written)
        except rule.StopRuleError:
            pass
        else:
            failures.append(f"мутация политики принята: {label}")

# Незакрытый BEGIN-маркер журнала — отказ, а не частичный хеш и не None (r24).
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-ledger-") as scratch:
    broken = Path(scratch) / "ledger.jsonl"
    broken.write_text(json.dumps({
        "entry": "itd-prompt-ledger-entry-v1", "kind": "unit", "unitIndex": 0,
        "prompt": ("w\nBEGIN UNTRUSTED DIFF UNIT\nfull-one\n"
                   "END UNTRUSTED DIFF UNIT\nw\n"
                   "BEGIN UNTRUSTED DIFF UNIT\ntruncated-tail"),
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        rule.candidate_identity_from_ledger(broken)
    except rule.StopRuleError as exc:
        check("незакрытый сегмент диффа в журнале — отказ, а не частичный хеш",
              "unterminated" in str(exc), str(exc))
    else:
        check("незакрытый сегмент диффа в журнале — отказ, а не частичный хеш", False)

# Находки r25: привязка называет юнит СВОЕЙ истории; секции политики — объекты.
rejects("привязка объявляет чужую пару одинаковых юнитов",
        synthetic([narrative_round("a", "BLOCKED", [mechanism("a.py", "x")])],
                  policyBinding={"ledgerUnit": "FOREIGN-9", "contractUnit": "FOREIGN-9",
                                 "criteriaPresent": True}), policy)
rejects("голый startswith не делает LPD003-30 серией юнита LPD003-3",
        synthetic([narrative_round("a", "BLOCKED", [mechanism("a.py", "x")])],
                  unit="synthetic0",
                  policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic",
                                 "criteriaPresent": True}), policy)
for section_name in ("mechanismKey", "terminalClasses", "policyBinding"):
    checks += 1
    mutated = copy.deepcopy(policy)
    mutated[section_name] = None
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-") as scratch:
        written = Path(scratch) / "mutated-policy.json"
        written.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        try:
            rule.load_policy(written)
        except rule.StopRuleError:
            pass
        except AttributeError:
            failures.append(f"null-секция {section_name} даёт AttributeError, а не StopRuleError")
        else:
            failures.append(f"null-секция {section_name} принята")

# r31: сегменты хешируются в порядке ПОЯВЛЕНИЯ, а не по виду маркера.
def mixed_ledger(directory: Path, order: list) -> Path:
    written = directory / "ledger.jsonl"
    prompt = "w\n" + "".join(
        f"BEGIN UNTRUSTED {marker}\n{chunk}END UNTRUSTED {marker}\n"
        for marker, chunk in order)
    written.write_text(json.dumps({
        "entry": "itd-prompt-ledger-entry-v1", "kind": "unit", "unitIndex": 0,
        "prompt": prompt}, ensure_ascii=False) + "\n", encoding="utf-8")
    return written


with tempfile.TemporaryDirectory(prefix="itd-stop-rule-mixed-") as scratch:
    forward = rule.candidate_identity_from_ledger(mixed_ledger(
        Path(scratch), [("DIFF UNIT", "one\n"), ("REVIEW DIFF", "two\n"),
                        ("DIFF UNIT", "three\n")]))
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-mixed-") as scratch:
    reordered = rule.candidate_identity_from_ledger(mixed_ledger(
        Path(scratch), [("DIFF UNIT", "one\n"), ("DIFF UNIT", "three\n"),
                        ("REVIEW DIFF", "two\n")]))
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-mixed-") as scratch:
    same_content_plain = rule.candidate_identity_from_ledger(mixed_ledger(
        Path(scratch), [("DIFF UNIT", "one\n"), ("DIFF UNIT", "two\n"),
                        ("DIFF UNIT", "three\n")]))
check("личность смешанного журнала считается в порядке появления",
      forward == same_content_plain, f"{forward} != {same_content_plain}")
check("перестановка сегментов меняет личность",
      forward != reordered)

# r31: битые live-леджеры -> StopRuleError, а не трейсбэк.
for label, contract_text in (("не-JSON", "{broken"), ("корень-список", "[]")):
    checks += 1
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-badjson-") as scratch:
        bad_root = Path(scratch)
        (bad_root / ".itd").mkdir()
        (bad_root / ".itd-memory").mkdir()
        (bad_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            contract_text, encoding="utf-8")
        (bad_root / ".itd-memory" / "STATE.json").write_text(
            json.dumps({"currentUnit": {"id": "U"}}), encoding="utf-8")
        try:
            rule.live_policy_binding(policy, bad_root)
        except rule.StopRuleError:
            pass
        except Exception as exc:
            failures.append(f"битый контракт ({label}) дал {type(exc).__name__}, "
                            f"а не StopRuleError")
        else:
            failures.append(f"битый контракт ({label}) принят")

# r32: идентификаторы юнита в live-леджерах типизированы, str(None)-коэрция
# «None» == «None» больше не выравнивает привязку без активного юнита.
for label, contract_doc, ledger_doc in (
    ("оба юнита отсутствуют",
     {"activeFollowup": {}, "criteria": [{"id": "None-1", "status": "passed"}]},
     {"currentUnit": {}}),
    ("юнит леджера null",
     {"activeFollowup": {"unitId": "U-1"}, "criteria": []},
     {"currentUnit": {"id": None}}),
    ("юнит контракта пустая строка",
     {"activeFollowup": {"unitId": "  "}, "criteria": []},
     {"currentUnit": {"id": "U-1"}}),
):
    checks += 1
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-liveunit-") as scratch:
        live_root = Path(scratch)
        (live_root / ".itd").mkdir()
        (live_root / ".itd-memory").mkdir()
        (live_root / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
            json.dumps(contract_doc, ensure_ascii=False), encoding="utf-8")
        (live_root / ".itd-memory" / "STATE.json").write_text(
            json.dumps(ledger_doc, ensure_ascii=False), encoding="utf-8")
        try:
            rule.live_policy_binding(policy, live_root)
        except rule.StopRuleError:
            pass
        else:
            failures.append(f"живая привязка без активного юнита принята: {label}")

# r33: недоверенные candidateSource.directories заперты под root.
for label, escape_dirs in (
    ("абсолютный каталог", ["/etc"]),
    ("traversal", ["../../.."]),
):
    checks += 1
    escape_history = {
        "schema": rule.HISTORY_SCHEMA, "unit": "ESC-1", "orderSource": "t",
        "orderProvenance": {"class": "artifact-list"},
        "candidateSource": {"kind": "prompt-ledger-diff-sha256", "prefix": "passwd",
                            "directories": escape_dirs, "archived": False,
                            "note": "t"},
        "policyBinding": {"contractUnit": "ESC-1", "ledgerUnit": "ESC-1",
                          "criteriaPresent": True},
        "rounds": [{"id": "r1", "terminal": "verdict",
                    "candidate": "0" * 16,
                    "provenance": {"class": "narrative",
                                   "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "mechanisms": [
                        {"surface": "a.py", "defectClass": "x"}]}}],
    }
    try:
        rule.decide(escape_history, policy, ROOT)
    except rule.StopRuleError as exc:
        if "escapes the repository root" not in str(exc):
            failures.append(f"выход за root ({label}) отвергнут не границей: {exc}")
    else:
        failures.append(f"candidateSource с выходом за root принят: {label}")

# r33: --root управляет и путём политики по умолчанию.
cli_probe = subprocess.run(
    [sys.executable, "-I", str(ROOT / "scripts" / "itd_stop_rule.py"),
     "--root", tempfile.gettempdir(), "--check-binding"],
    capture_output=True, text=True)
cli_error = cli_probe.stderr + cli_probe.stdout
check("--root без своей политики падает именно на политике этого root",
      cli_probe.returncode != 0 and "Traceback" not in cli_error
      and "policy is missing" in cli_error,
      cli_error[-200:])

# r34: источник порядка проверяется машинно.
rejects("история без orderProvenance",
        {k: v for k, v in synthetic([narrative_round("a", "PASSED", [])]).items()
         if k != "orderProvenance"}, policy)
rejects("orderProvenance с неизвестным классом",
        synthetic([narrative_round("a", "PASSED", [])],
                  orderProvenance={"class": "vibes"}), policy)
rejects("recorded-document без path",
        synthetic([narrative_round("a", "PASSED", [])],
                  orderProvenance={"class": "recorded-document", "line": 1}), policy)
order_doc_missing = synthetic([narrative_round("a", "PASSED", [])],
                              orderProvenance={"class": "recorded-document",
                                               "path": "no/such/file.md",
                                               "line": 1})
try:
    rule.decide(order_doc_missing, policy, ROOT)
except rule.StopRuleError as exc:
    check("recorded-document с несуществующим документом отвергается в decide",
          "missing" in str(exc) or "orderProvenance" in str(exc), str(exc))
else:
    check("recorded-document с несуществующим документом отвергается в decide", False)
check("gpg-001 объявляет recorded-document с документом серии",
      (load("gpg-001-broker-policy").get("orderProvenance") or {}).get("class")
      == "recorded-document")

check("история без установленных личностей объявляет это видом none",
      (load("gpg-001-broker-policy").get("candidateSource") or {}).get("kind") == "none")

# Матрица провенанса: гарантия одинакова для ВСЕХ комбинаций
# (класс терминала x класс провенанса). Прежняя форма разводила проверки по
# отдельным ранним выходам, и каждая новая комбинация давала новую щель —
# три находки независимого ревьюера в одном классе за пять раундов.
for terminal_class, outcome in (("verdict", "BLOCKED"),
                                ("precondition", "UNVERIFIED"),
                                ("transport", "UNAVAILABLE")):
    # База схемно-валидна для СВОЕГО класса: личность и вердикт-содержание
    # несут только вердикты. Прежняя база с cand-m и verdict-полями у всех
    # классов падала ДО проверяемого условия — вся матрица была ложной
    # гарантией (находка ревьюера, раунд r21). Валидность базы доказана ниже
    # позитивным прогоном: та же база с ЦЕЛЫМ провенансом принимается.
    if terminal_class == "verdict":
        base = {"id": "m", "terminal": terminal_class,
                "candidate": "717a92394559df85",
                "declared": {"verdict": outcome,
                             "mechanisms": [{"surface": "s", "defectClass": "c"}]}}
    else:
        base = {"id": "m", "terminal": terminal_class, "outcome": outcome}
    intact = {**base, "provenance": {"class": "narrative",
                                     "path": SYNTHETIC_SOURCE,
                                     "line": SYNTHETIC_LINE}}
    check(f"{terminal_class}: база матрицы валидна с целым провенансом",
          isinstance(rule.decide(synthetic([intact]), policy, ROOT), dict))
    rejects(f"{terminal_class}: пересказ без документа",
            synthetic([{**base, "provenance": {"class": "narrative", "line": 1}}]), policy)
    rejects(f"{terminal_class}: пересказ без строки",
            synthetic([{**base, "provenance": {"class": "narrative",
                                               "path": SYNTHETIC_SOURCE}}]), policy)
    rejects(f"{terminal_class}: пересказ со строкой за концом файла",
            synthetic([{**base, "provenance": {"class": "narrative",
                                               "path": SYNTHETIC_SOURCE,
                                               "line": 10 ** 9}}]), policy)
    rejects(f"{terminal_class}: пересказ с путём за пределы репозитория",
            synthetic([{**base, "provenance": {"class": "narrative",
                                               "path": "../../etc/passwd",
                                               "line": 1}}]), policy)
    if terminal_class == "verdict":
        rejects(f"{terminal_class}: вердикт с классом absent",
                synthetic([{**base, "provenance": {"class": "absent"}}]), policy)
    if terminal_class != "verdict":
        rejects(f"{terminal_class}: попытка числиться машинной уликой",
                synthetic([{**base, "provenance": {"class": "report",
                                                   "path": EVIDENCE_FILES[0],
                                                   "sha256": rule.sha256_of(
                                                       ROOT / EVIDENCE_FILES[0])}}]),
                policy)
    else:
        rejects(f"{terminal_class}: улика с подменённым sha",
                synthetic([{**base, "provenance": {"class": "report",
                                                   "path": EVIDENCE_FILES[0],
                                                   "sha256": "0" * 64}}]), policy)

# Пересказ у нев-вердиктного раунда законен, если он полон.
legal_narrative = synthetic([
    {"id": "t1", "terminal": "transport", "outcome": "UNAVAILABLE",
     "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE, "line": 1}}])
check("полный пересказ у сорванного раунда принимается",
      rule.decide(legal_narrative, policy, ROOT)["terminal"] == "ROUTE_REPAIR")

# Отсутствие orderSource — отказ ещё на загрузке.
def rejects_on_load(name: str, document: dict) -> None:
    """Загрузчик обязан отвергнуть документ ещё до разбора раундов."""
    global checks
    checks += 1
    with tempfile.TemporaryDirectory(prefix="itd-stop-rule-") as scratch:
        written = Path(scratch) / "mutated-history.json"
        written.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        try:
            rule.load_history(written)
        except rule.StopRuleError:
            return
    failures.append(f"{name}: история принята, хотя обязана быть отвергнута")


rejects_on_load("история без orderSource",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x",
                 "rounds": [narrative_round("a", "PASSED", [])]})

# Личность кандидата без объявленного происхождения — отказ на загрузке.
rejects_on_load("кандидаты без candidateSource",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
                 "rounds": [narrative_round("a", "BLOCKED",
                                            [mechanism("s", "correctness")])]})
rejects_on_load("решение ссылается на несуществующий раунд",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
                 "candidateSource": {"kind": "synthetic"},
                 "recordedDecision": {"terminal": "CLOSE", "atRound": "nope"},
                 "rounds": [narrative_round("a", "PASSED", [])]})
rejects_on_load("recordedDecision не объект",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
                 "candidateSource": {"kind": "synthetic"}, "recordedDecision": "CLOSE",
                 "rounds": [narrative_round("a", "PASSED", [])]})

# Обратная сторона той же гарантии: ссылка на ОБЪЯВЛЕННЫЙ пробел законна —
# иначе проверка выродилась бы в запрет ссылаться на невосстановимый раунд.
checks += 1
accepted_gap = {
    "schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
    "orderProvenance": {"class": "artifact-list"},
    "candidateSource": {"kind": "synthetic"},
    "knownGaps": [{"id": "PUB9", "why": "артефакта нет"}],
    "recordedDecision": {"terminal": "CLOSE", "atRound": "PUB9"},
    "rounds": [narrative_round("a", "PASSED", [])],
}
with tempfile.TemporaryDirectory(prefix="itd-stop-rule-") as scratch:
    written = Path(scratch) / "history.json"
    written.write_text(json.dumps(accepted_gap, ensure_ascii=False), encoding="utf-8")
    try:
        rule.load_history(written)
    except rule.StopRuleError as exc:
        failures.append(f"решение со ссылкой на ОБЪЯВЛЕННЫЙ пробел отвергнуто: {exc}")

# bool не является индексом находки: True не должен читаться как индекс 1.
mutated_history = copy.deepcopy(s04b_for_dispositions)
for entry in mutated_history["rounds"]:
    if entry["id"] == first_report["id"]:
        entry["dispositions"] = [{"finding": True, "refuted": True, "why": "основание"}]
rejects("булев индекс находки в диспозиции", mutated_history, policy)



# knownGaps без объяснения — отказ.
rejects_on_load("пробел без объяснения",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
                 "knownGaps": [{"id": "PUB9"}],
                 "rounds": [narrative_round("a", "PASSED", [])]})
rejects_on_load("история с подменённой схемой",
                {"schema": "other", "unit": "x", "orderSource": "s",
                 "rounds": [narrative_round("a", "PASSED", [])]})


# ---------------------------------------------------------------------------
# 5. провенанс: улика сверяется с деревом
# ---------------------------------------------------------------------------

s04b_history = load("s04b")
report_rounds = [r for r in s04b_history["rounds"]
                 if r["provenance"]["class"] == "report"]
declared_evidence = set(EVIDENCE_FILES)
cited_evidence = set()
for history_name in HISTORIES:
    for entry in load(history_name)["rounds"]:
        source = (entry.get("provenance") or {}).get("path")
        if source:
            cited_evidence.add(source)
        # Улика поверхности (R7) — такая же улика: архив, sha256, литерал в списке.
        surface_path = (entry.get("surface") or {}).get("path")
        if surface_path:
            cited_evidence.add(surface_path)
check("набор улик объявлен целиком: ни одной незаявленной ссылки",
      cited_evidence <= declared_evidence,
      json.dumps(sorted(cited_evidence - declared_evidence), ensure_ascii=False))
declared_sources = set(SOURCE_FILES)
cited_sources = set()
for history_name in HISTORIES:
    document = load(history_name)
    for holder in (document.get("recordedDecision"), document.get("policyBinding"),
                   document.get("divergence")):
        if not isinstance(holder, dict):
            continue
        value = holder.get("source")
        if not isinstance(value, str) or not value.strip():
            continue
        head = value.split(",")[0].strip()
        in_tree = holder.get("sourceInTree")
        checks += 1
        if not isinstance(in_tree, bool):
            failures.append(
                f"{history_name}: цитируемый источник {head!r} не объявляет sourceInTree — "
                f"молчание тут и есть fail-open"
            )
            continue
        if in_tree:
            cited_sources.add(head)
            checks += 1
            if not (ROOT / head).is_file():
                failures.append(f"{history_name}: источник объявлен в дереве, но его там нет: {head}")
        else:
            checks += 1
            if not str(holder.get("sourceNote") or "").strip():
                failures.append(
                    f"{history_name}: источник {head!r} вне дерева и без объяснения"
                )
            checks += 1
            if (ROOT / head).is_file():
                failures.append(
                    f"{history_name}: источник объявлен вне дерева, но он в дереве есть: {head}"
                )
check("цитируемые документы-записи объявлены целиком",
      cited_sources <= declared_sources,
      json.dumps(sorted(cited_sources - declared_sources), ensure_ascii=False))
check("в объявленном наборе документов нет лишних",
      declared_sources <= cited_sources,
      json.dumps(sorted(declared_sources - cited_sources), ensure_ascii=False))
for declared in sorted(declared_sources):
    check(f"документ-запись в дереве: {declared}", (ROOT / declared).is_file())

check("в объявленном наборе нет лишних улик",
      declared_evidence <= cited_evidence,
      json.dumps(sorted(declared_evidence - cited_evidence), ensure_ascii=False))
for declared in sorted(declared_evidence):
    check(f"улика в дереве: {declared}", (ROOT / declared).is_file())

check("s04b: все раунды-улики ссылаются на артефакты в дереве",
      len(report_rounds) == 9, str(len(report_rounds)))

tampered = copy.deepcopy(s04b_history)
tampered["rounds"][0]["provenance"]["sha256"] = "0" * 64
rejects("подменённый sha256 улики", tampered, policy)

missing = copy.deepcopy(s04b_history)
missing["rounds"][0]["provenance"]["path"] = \
    ".itd-memory/verification-loop/reports/does-not-exist.json"
rejects("улика, которой нет в дереве", missing, policy)

escaping = copy.deepcopy(s04b_history)
escaping["rounds"][0]["provenance"]["path"] = "../../etc/passwd"
rejects("путь улики за пределы репозитория", escaping, policy)

for history_name in HISTORIES:
    document = load(history_name)
    for entry in document["rounds"]:
        if entry["provenance"]["class"] != "report":
            continue
        checks += 1
        artifact = ROOT / entry["provenance"]["path"]
        if not artifact.is_file():
            failures.append(f"{history_name}/{entry['id']}: улики нет в дереве")
            continue
        if rule.sha256_of(artifact) != entry["provenance"]["sha256"]:
            failures.append(f"{history_name}/{entry['id']}: sha256 улики разошёлся")


# ---------------------------------------------------------------------------
# 6. живая проверка привязки бухгалтерии
# ---------------------------------------------------------------------------

for field in ("ledgerUnit", "contractUnit", "criteriaPresent", "aligned"):
    check(f"живая привязка: поле {field} присутствует", field in binding)
check("живая привязка: расхождение вычисляется, а не декларируется",
      binding["aligned"] == (binding["contractUnit"] == binding["ledgerUnit"]
                            and bool(binding["criteriaPresent"])
                            and bool(binding["statusSatisfied"])))

route_defect_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "synthetic", "contractUnit": "other-unit", "criteriaPresent": True})
check("чужой юнит в контракте даёт ROUTE_DEFECT",
      rule.decide(route_defect_history, policy, ROOT)["terminal"] == "ROUTE_DEFECT")

no_criteria_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic", "criteriaPresent": False})
check("отсутствие критериев юнита тоже даёт ROUTE_DEFECT",
      rule.decide(no_criteria_history, policy, ROOT)["terminal"] == "ROUTE_DEFECT")

aligned_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "synthetic", "contractUnit": "synthetic", "criteriaPresent": True})
check("совпадающая привязка не мешает обычному решению",
      rule.decide(aligned_history, policy, ROOT)["terminal"] == "CLOSE")


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# R7 — SURFACE_TREADMILL (STOPRULE-1): улика поверхности, окно, прецедент.
# Позитив — синтетический (машинные диффы во временном корне); замер серии
# PILOT-P02 воспроизводится по архивным проекциям hunks и живым деревьям.
# ---------------------------------------------------------------------------
TREADMILL = policy["surfaceTreadmill"]
WINDOW = int(TREADMILL["windowRounds"])
check("policy: SURFACE_TREADMILL после терминалов повтора и перед ROUTE_REPAIR",
      policy["precedence"].index("RECURRENCE_UNCONFIRMED")
      < policy["precedence"].index("SURFACE_TREADMILL")
      < policy["precedence"].index("ROUTE_REPAIR"),
      json.dumps(policy["precedence"], ensure_ascii=False))
check("policy: окно R7 заморожено по значению — ровно 5 вердикт-раундов",
      WINDOW == rule.APPROVED_WINDOW_ROUNDS == 5 and type(WINDOW) is int)
check("policy: улика поверхности снимается командой с -U0",
      TREADMILL["contextLines"] == 0 and "-U0" in TREADMILL["evidenceCommand"])
check("policy: недостающая улика не взводит терминал, окно требует BLOCKED",
      TREADMILL["unlocatedFinding"] == "not-on-added-surface"
      and TREADMILL["requireBlockedWindow"] is True)
for name, mutate in (
    ("окно R7 = 1", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", 1)),
    ("окно R7 = 3 — ослабление внутри «диапазона»", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", 3)),
    ("окно R7 = 7 — ужесточение тоже не молча", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", 7)),
    ("окно R7 = 99 — это потолок", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", 99)),
    ("окно R7 — булево", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", True)),
    ("окно R7 — строка", lambda p: p["surfaceTreadmill"].__setitem__("windowRounds", "5")),
    ("контекст диффа ослаблен", lambda p: p["surfaceTreadmill"].__setitem__("contextLines", 3)),
    ("недостающая улика объявлена добавленной поверхностью",
     lambda p: p["surfaceTreadmill"].__setitem__("unlocatedFinding", "on-added-surface")),
    ("окно без требования BLOCKED",
     lambda p: p["surfaceTreadmill"].__setitem__("requireBlockedWindow", False)),
    ("класс улики подменён", lambda p: p["surfaceTreadmill"].__setitem__("evidenceClass", "narrative")),
    ("проекции урезаны", lambda p: p["surfaceTreadmill"].__setitem__("projections", ["full"])),
    ("секция R7 удалена", lambda p: p.pop("surfaceTreadmill")),
    ("SURFACE_TREADMILL убран из прецедента", lambda p: p["precedence"].remove("SURFACE_TREADMILL")),
    ("SURFACE_TREADMILL поставлен выше REDESIGN_OR_DISCARD",
     lambda p: p.__setitem__("precedence", ["ROUTE_DEFECT", "SURFACE_TREADMILL",
                                            "REDESIGN_OR_DISCARD", "RECURRENCE_UNCONFIRMED",
                                            "ROUTE_REPAIR", "CLOSE", "CONTINUE"])),
):
    checks += 1
    mutated = copy.deepcopy(policy)
    mutate(mutated)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "policy.json"
        path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        try:
            rule.load_policy(path)
        except rule.StopRuleError:
            continue
    failures.append(f"policy R7 mutation accepted: {name}")

BASE_TREE = "a" * 40


def tree_id(round_id: str) -> str:
    return hashlib.sha256(f"tree-{round_id}".encode()).hexdigest()[:40]


def full_diff(files: dict) -> str:
    """Полный вывод `git diff -U0` для файлов с добавленными диапазонами."""
    out = []
    for path, ranges in files.items():
        out += [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}"]
        for start, end in ranges:
            count = end - start + 1
            out.append(f"@@ -{start - 1},0 +{start},{count} @@")
            out += ["+line"] * count
    return "\n".join(out) + "\n"


def header_projection(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if line.startswith(rule.SURFACE_HEADER_PREFIXES)) + "\n"


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SurfaceLab:
    """Временный корень: журнал для пересказа и улики поверхности."""

    def __init__(self, tmp: Path):
        self.root = tmp
        (tmp / "journal.md").write_text("journal\n", encoding="utf-8")
        (tmp / "evidence").mkdir()

    def round(self, round_id, verdict, mechanisms, diff_files=None, *,
              projection="full", candidate=None, base=BASE_TREE):
        entry = {
            "id": round_id, "terminal": "verdict",
            "provenance": {"class": "narrative", "path": "journal.md", "line": 1},
            "candidate": candidate or hashlib.sha256(f"cand-{round_id}".encode()).hexdigest()[:16],
            "declared": {"verdict": verdict, "mechanisms": mechanisms},
        }
        if diff_files is not None:
            text = full_diff(diff_files)
            if projection == "hunk-headers":
                text = header_projection(text)
            entry["surface"] = self.evidence(round_id, text, projection, base)
        return entry

    def evidence(self, round_id, text, projection="full", base=BASE_TREE):
        rel = f"evidence/{round_id}-{sha_text(text)[:8]}.diff"
        (self.root / rel).write_text(text, encoding="utf-8")
        return {"class": "diff-hunks", "projection": projection, "path": rel,
                "sha256": sha_text(text), "baseTree": base, "candidateTree": tree_id(round_id)}

    def history(self, rounds, **extra):
        document = synthetic(rounds, surfaceBaseline={"tree": BASE_TREE})
        document.update(extra)
        return document

    def decide(self, rounds, **extra):
        return rule.decide(self.history(rounds, **extra), policy, self.root)

    def rejects(self, name, rounds, **extra):
        global checks
        checks += 1
        try:
            rule.decide(self.history(rounds, **extra), policy, self.root)
        except rule.StopRuleError:
            return
        failures.append(f"{name}: вход принят, хотя обязан быть отвергнут")


with tempfile.TemporaryDirectory() as tmp:
    lab = SurfaceLab(Path(tmp))

    def treadmill(count=WINDOW, projection="full"):
        return [lab.round(f"t{k}", "BLOCKED",
                          [mechanism(f"f{k}.py", "correctness", line=10 + k)],
                          {f"f{k}.py": [(10 + k, 12 + k)]}, projection=projection)
                for k in range(count)]

    armed = lab.decide(treadmill())
    check("R7: окно BLOCKED-раундов с находками только на добавленной поверхности взводит SURFACE_TREADMILL",
          armed["terminal"] == "SURFACE_TREADMILL" and armed["atRound"] == f"t{WINDOW - 1}",
          f"{armed['terminal']} @ {armed['atRound']}")
    check("R7: диагностика поверхности объявляет evaluated и terminalArmed",
          armed["surface"]["evaluated"] is True and armed["surface"]["terminalArmed"] is True)
    check("R7: рендер называет поверхность и ADR-007",
          "ПОВЕРХНОСТЬ" in rule.render(armed) and "ADR-007" in armed["fix"])
    check("R7: FIX не обещает составления диспозиций правилом — оно отнесено к STOPRULE-2",
          "STOPRULE-2" in armed["fix"] and "adjudicate" in armed["fix"]
          and "правило составляет" not in armed["fix"], armed["fix"])
    check("R7: во временном корне без git улика помечена непересчитанной, а не проверенной",
          all(item["verifiedAgainstTrees"] is False for item in armed["surface"]["rounds"]))
    headers = lab.decide(treadmill(projection="hunk-headers"))
    check("R7: проекция заголовков hunks даёт тот же терминал",
          headers["terminal"] == "SURFACE_TREADMILL", headers["terminal"])
    # Один буфер (pub1): хеш и разбор судят ОДНИ И ТЕ ЖЕ байты. Улика, чей
    # второй read вернул бы другую поверхность, не должна на решение влиять —
    # иначе между sha256 и разбором есть окно подмены.
    real_artifact = rule.repository_artifact

    class TwoFaced:
        """Файл, который при повторном чтении отдаёт ДРУГУЮ поверхность."""

        def __init__(self, path):
            self._path = path
            self._served = False

        def read_bytes(self):
            if not self._served:
                self._served = True
                return self._path.read_bytes()
            return full_diff({"other.py": [(1, 3)]}).encode()

    def two_faced(rel, round_id, root, label):
        artifact = real_artifact(rel, round_id, root, label)
        return TwoFaced(artifact) if label == "surface evidence" else artifact

    rule.repository_artifact = two_faced
    try:
        toctou = lab.decide(treadmill())
    finally:
        rule.repository_artifact = real_artifact
    check("улика поверхности читается один раз: подмена байтов после sha не меняет разбор",
          toctou["terminal"] == "SURFACE_TREADMILL", toctou["terminal"])
    rounds = treadmill()
    rounds[2]["declared"]["mechanisms"][0]["line"] = 3
    off = lab.decide(rounds)
    check("R7: одна находка на исходной поверхности снимает критерий",
          off["terminal"] == "CONTINUE" and off["surface"]["evaluated"] is True
          and "t2" in off["surface"]["why"], f"{off['terminal']}: {off['surface']['why']}")
    rounds = treadmill()
    del rounds[1]["declared"]["mechanisms"][0]["line"]
    check("R7: находка без строки не считается лежащей на добавленной поверхности",
          lab.decide(rounds)["terminal"] == "CONTINUE")
    rounds = treadmill()
    rounds[3]["declared"]["mechanisms"][0]["surface"] = "other.py"
    check("R7: файл вне диффа — не добавленная поверхность",
          lab.decide(rounds)["terminal"] == "CONTINUE")
    short = lab.decide(treadmill(WINDOW - 1))
    check("R7: окно короче политики не взводит и называет причину",
          short["terminal"] == "CONTINUE" and "меньше окна" in short["surface"]["why"],
          short["surface"]["why"])
    rounds = treadmill()
    rounds[1]["declared"]["verdict"] = "PASSED"
    rounds[1]["declared"]["mechanisms"] = []
    passed_inside = lab.decide(rounds)
    check("R7: PASSED внутри окна — поток дошёл до нуля, это не treadmill",
          passed_inside["terminal"] == "CONTINUE" and "не-BLOCKED" in passed_inside["surface"]["why"],
          passed_inside["surface"]["why"])
    check("R7: PASSED последним раундом закрывает маршрут, а не взводит",
          lab.decide(treadmill() + [lab.round("z", "PASSED", [])])["terminal"] == "CLOSE")
    # Окно хронологическое (r9): свежий PASSED без содержания не выпадает из
    # хвоста, и старый BLOCKED не занимает его место.
    contentless_pass = {"id": "p", "terminal": "verdict",
                        "provenance": {"class": "narrative", "path": "journal.md", "line": 1},
                        "declared": {"verdict": "PASSED", "contentRecorded": False,
                                     "why": "отчёт не сохранился"}}
    trailing_pass = lab.decide(treadmill() + [contentless_pass])
    check("R7: PASSED без содержания в конце окна снимает критерий, а не выпадает из него",
          trailing_pass["terminal"] != "SURFACE_TREADMILL"
          and not trailing_pass["surface"]["terminalArmed"],
          f"{trailing_pass['terminal']}: {trailing_pass['surface']['why']}")
    contentless_block = dict(contentless_pass, id="b",
                             declared={"verdict": "BLOCKED", "contentRecorded": False,
                                       "why": "отчёт не сохранился"})
    inner_block = lab.decide(treadmill()[:4] + [contentless_block])
    check("R7: BLOCKED без содержания в окне — нет улики, критерий не проверяем",
          inner_block["terminal"] == "CONTINUE" and "b" in inner_block["surface"]["why"],
          inner_block["surface"]["why"])
    rounds = treadmill()
    rounds[4].pop("surface")
    missing = lab.decide(rounds)
    check("R7: раунд окна без улики поверхности — критерий не проверяем",
          missing["terminal"] == "CONTINUE" and "нет улики" in missing["surface"]["why"],
          missing["surface"]["why"])
    rounds = treadmill()
    rounds[1] = lab.round("t1", "BLOCKED", [mechanism("f0.py", "correctness", line=10)],
                          {"f0.py": [(10, 12)], "f1.py": [(11, 13)]})
    recurrence = lab.decide(rounds)
    check("R7 ниже R1: тот же ключ на добавленной поверхности при смене кандидата — REDESIGN_OR_DISCARD",
          recurrence["terminal"] == "REDESIGN_OR_DISCARD", recurrence["terminal"])
    check("R7: цифры поверхности печатаются и при терминале повтора",
          len(recurrence["surface"]["rounds"]) == WINDOW
          and "ПОВЕРХНОСТЬ" in rule.render(recurrence))
    rounds = treadmill()
    rounds[4]["declared"]["mechanisms"][0].update(refuted=True, why="опровергнута фактами")
    refuted = lab.decide(rounds)
    check("R7: раунд, где все находки опровергнуты, не поддерживает поток",
          refuted["terminal"] == "CONTINUE" and "без засчитанных" in refuted["surface"]["why"],
          refuted["surface"]["why"])
    trailing = treadmill() + [{"id": "x", "terminal": "transport", "outcome": "UNAVAILABLE",
                               "provenance": {"class": "absent"}}]
    check("R7 выше ROUTE_REPAIR: хвостовой срыв транспорта не прячет treadmill",
          lab.decide(trailing)["terminal"] == "SURFACE_TREADMILL")
    # Отказы улики поверхности.
    rounds = treadmill(); rounds[0]["surface"]["sha256"] = "0" * 64
    lab.rejects("улика поверхности с чужим sha256", rounds)
    rounds = treadmill(); rounds[0]["surface"]["baseTree"] = "b" * 40
    lab.rejects("улика поверхности от чужой базы", rounds)
    lab.rejects("улика поверхности без базы серии", treadmill(), surfaceBaseline=None)
    lab.rejects("база серии не 40-hex", treadmill(), surfaceBaseline={"tree": "abc"})
    rounds = treadmill(); rounds[0]["surface"]["candidateTree"] = "xyz"
    lab.rejects("дерево кандидата не 40-hex", rounds)
    rounds = treadmill(); rounds[0]["surface"]["projection"] = "narrative"
    lab.rejects("неизвестная проекция улики", rounds)
    rounds = treadmill(); rounds[0]["surface"]["class"] = "report"
    lab.rejects("неизвестный класс улики поверхности", rounds)
    rounds = treadmill(); rounds[0]["surface"]["path"] = "../outside.diff"
    lab.rejects("улика поверхности вне репозитория", rounds)
    rounds = treadmill()
    lab.rejects("улика поверхности у не-вердиктного раунда",
                rounds + [{"id": "x", "terminal": "transport", "outcome": "UNAVAILABLE",
                           "provenance": {"class": "absent"}, "surface": rounds[0]["surface"]}])
    text = full_diff({"f0.py": [(10, 12)]}).replace("+line\n", " context\n", 1)
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text)
    lab.rejects("строка контекста в full-проекции — улика снята не с -U0", rounds)
    # Удалённый файл в диффе — законная улика (r1): hunk без новой стороны.
    deletion = ("diff --git a/gone.py b/gone.py\n--- a/gone.py\n+++ /dev/null\n"
                "@@ -1,2 +0,0 @@\n-x\n-y\n") + full_diff({"f0.py": [(10, 12)]})
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", deletion)
    check("улика с удалённым файлом разбирается, критерий взводится",
          lab.decide(rounds)["terminal"] == "SURFACE_TREADMILL")
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", header_projection(deletion), "hunk-headers")
    check("проекция заголовков с удалённым файлом разбирается",
          lab.decide(rounds)["terminal"] == "SURFACE_TREADMILL")
    rounds = treadmill()
    rounds[0]["surface"] = lab.evidence("t0", deletion.replace("-y\n", "+z\n", 1))
    lab.rejects("добавленная строка внутри удалённого файла", rounds)
    rounds = treadmill()
    rounds[0]["surface"] = lab.evidence(
        "t0", header_projection(deletion).replace("+0,0", "+0,2"), "hunk-headers")
    lab.rejects("проекция заголовков: удалённый файл с новыми строками в заголовке", rounds)
    text = full_diff({"f0.py": [(10, 12)]})
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text, "hunk-headers")
    lab.rejects("содержательные строки в проекции заголовков", rounds)
    text = full_diff({"f0.py": [(10, 12)]}).replace("@@ -9,0 +10,3 @@", "@@ garbage @@")
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text)
    lab.rejects("искажённый заголовок hunk", rounds)
    text = "@@ -9,0 +10,3 @@\n+line\n+line\n+line\n"
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text)
    lab.rejects("hunk без заголовка файла", rounds)
    # Структурная связка (r10): без diff --git/--- проекция не является выводом git.
    for name, text in (
        ("проекция из одних +++/@@", "+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("diff --git без ---", "diff --git a/f0.py b/f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("+++ с чужим путём", "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/other.py\n@@ -9,0 +10,3 @@\n"),
        ("--- дважды", "diff --git a/f0.py b/f0.py\n--- a/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("diff --git с чужими операндами", "diff --git a/f0.py b/zzz.py\n--- a/f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("операнд без a/", "diff --git f0.py b/f0.py\n--- f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("--- с чужим префиксом той же длины", "diff --git a/f0.py b/f0.py\n--- zzf0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"),
        ("+++ с чужим префиксом той же длины", "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ zzf0.py\n@@ -9,0 +10,3 @@\n"),
    ):
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text, "hunk-headers")
        lab.rejects(name, rounds)
    # Путь с подстрокой " b/" и переименование разбираются по ---/+++ (r11).
    spaced = ("diff --git a/x b/y.py b/x b/y.py\n--- a/x b/y.py\n+++ b/x b/y.py\n"
              "@@ -0,0 +1,2 @@\n+a\n+b\n")
    check("путь с подстрокой ' b/' разбирается по заголовкам ---/+++",
          rule.surface_lines(rule.parse_diff_surface(spaced, projection="full", where="t")) == {"x b/y.py": {1, 2}})
    renamed = ("diff --git a/old.py b/new.py\nsimilarity index 90%\nrename from old.py\n"
               "rename to new.py\n--- a/old.py\n+++ b/new.py\n@@ -0,0 +1,1 @@\n+a\n")
    check("переименование: операнды diff --git совпадают с ---/+++",
          rule.surface_lines(rule.parse_diff_surface(renamed, projection="full", where="t")) == {"new.py": {1}})
    new_file = "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1,1 @@\n+a\n"
    check("новый файл: операнды сверяются по +++",
          rule.surface_lines(rule.parse_diff_surface(new_file, projection="full", where="t")) == {"n.py": {1}})
    # Гигантский hunk (r18): интервалы вместо множеств, предел координат.
    huge = "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -0,0 +1,50000000 @@\n"
    huge_added = rule.parse_diff_surface(huge, projection="hunk-headers", where="t")
    # Без порога по времени (r20: флейк на нагруженном хосте): отсутствие
    # материализации доказывается формой результата — один интервал, а не
    # множество из 50 млн элементов.
    check("hunk на 50 млн строк разбирается интервалом без материализации",
          huge_added == {"f0.py": [[1, 50_000_000]]}
          and isinstance(huge_added["f0.py"][0], list)
          and rule.on_added_surface(huge_added, "f0.py", 49_999_999)
          and not rule.on_added_surface(huge_added, "f0.py", 50_000_001),
          repr(huge_added.get("f0.py")))
    rounds = treadmill()
    rounds[0]["surface"] = lab.evidence("t0", huge.replace("+1,50000000", "+1,900000000"), "hunk-headers")
    lab.rejects("hunk за практическим пределом строк", rounds)
    # Невозможные координаты (r21): положительный диапазон с нулевого старта.
    for name, header in (("новая сторона +0,2", "@@ -0,0 +0,2 @@"),
                         ("старая сторона -0,1", "@@ -0,1 +1,0 @@")):
        impossible = f"diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n{header}\n"
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", impossible, "hunk-headers")
        lab.rejects(f"невозможные координаты hunk: {name}", rounds)
    for name, header in (("мусор после @@", "@@ -0,0 +1,2 @@garbage"),
                         ("двойной пробел перед контекстом", "@@ -0,0 +1,2 @@  x"),):
        malformed_tail = f"diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n{header}\n"
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", malformed_tail, "hunk-headers")
        if name == "двойной пробел перед контекстом":
            continue  # `@@  x` — пробел + контекст " x": законно по грамматике git
        lab.rejects(f"заголовок hunk: {name}", rounds)
    # Полнота секций (r24): голая секция и `---` без `+++` — отказ; metadata-only — законна.
    good = "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@\n"
    for name, text in (
        ("голая секция в конце архива", good + "diff --git a/z.py b/z.py\n"),
        ("голая секция между секциями", "diff --git a/z.py b/z.py\n" + good),
        ("--- без +++ в конце", good + "diff --git a/z.py b/z.py\nindex 0000000..1111111 100644\n--- a/z.py\n"),
        ("--- без +++ перед следующей секцией",
         "diff --git a/z.py b/z.py\nindex 0000000..1111111 100644\n--- a/z.py\n" + good),
    ):
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text, "hunk-headers")
        lab.rejects(f"неполная секция: {name}", rounds)
    for name, text in (
        ("служебная строка вне секции", "index 0000000..1111111 100644\n" + good),
        ("секция только с index", good + "diff --git a/z.py b/z.py\nindex 0000000..1111111 100644\n"),
        ("новый файл со старой стороной hunk",
         "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n@@ -1,5 +1,5 @@\n"),
    ):
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text, "hunk-headers")
        lab.rejects(f"структура секции: {name}", rounds)
    new_full = "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n@@ -1,2 +1,2 @@\n-a\n-b\n+c\n+d\n"
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", new_full)
    lab.rejects("новый файл с удалёнными строками в full-проекции", rounds)
    mode_only = good + "diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"
    check("секция только со сменой режима (без ---/+++) — законный вывод git",
          rule.parse_diff_surface(mode_only, projection="hunk-headers", where="t") == {"f0.py": [[10, 12]]})
    with_context = "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -9,0 +10,3 @@ def parse():\n"
    check("function-context после @@ принимается",
          rule.parse_diff_surface(with_context, projection="hunk-headers", where="t") == {"f0.py": [[10, 12]]})
    boundary = "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -0,0 +1,1 @@\n"
    check("нулевая координата при нулевой длине законна (вставка в пустой файл)",
          rule.parse_diff_surface(boundary, projection="hunk-headers", where="t") == {"f0.py": [[1, 1]]})
    adjacent = ("diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n"
                "@@ -9,0 +10,3 @@\n@@ -12,0 +13,2 @@\n")
    check("смежные hunks сливаются в один интервал без потери строк",
          rule.parse_diff_surface(adjacent, projection="hunk-headers", where="t") == {"f0.py": [[10, 14]]}
          and rule.surface_lines(rule.parse_diff_surface(adjacent, projection="hunk-headers", where="t"))
          == {"f0.py": {10, 11, 12, 13, 14}})
    # Порядок hunks (r13): дубли, перекрытие, обратный порядок, повтор секции.
    ordered = full_diff({"f0.py": [(10, 12), (20, 21)]})
    check("hunks по возрастанию принимаются",
          rule.surface_lines(rule.parse_diff_surface(ordered, projection="full", where="t")) == {"f0.py": {10, 11, 12, 20, 21}})
    for name, text in (
        ("hunks в обратном порядке", full_diff({"f0.py": [(20, 21), (10, 12)]})),
        ("перекрывающиеся hunks", full_diff({"f0.py": [(10, 12), (12, 13)]})),
        ("дубль hunk", full_diff({"f0.py": [(10, 12), (10, 12)]})),
        ("секция файла дважды", full_diff({"f0.py": [(10, 12)]}) + full_diff({"f0.py": [(20, 21)]})),
        ("один путь назначения из двух секций-переименований",
         "diff --git a/old1.py b/t.py\n--- a/old1.py\n+++ b/t.py\n@@ -0,0 +1,1 @@\n+a\n"
         "diff --git a/old2.py b/t.py\n--- a/old2.py\n+++ b/t.py\n@@ -0,0 +2,1 @@\n+b\n"),
        ("путь удалён и добавлен в разных секциях",
         "diff --git a/t.py b/t.py\n--- a/t.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-a\n"
         "diff --git a/t.py b/t.py\nnew file mode 100644\n--- /dev/null\n+++ b/t.py\n@@ -0,0 +1,1 @@\n+b\n"),
    ):
        checks += 1
        try:
            rule.parse_diff_surface(text, projection="full", where="t")
            failures.append(f"{name}: принято, хотя обязано быть отвергнуто")
        except rule.StopRuleError:
            pass
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", header_projection(text), "hunk-headers")
        lab.rejects(f"{name} (проекция заголовков)", rounds)
    # Проекция заголовков по состоянию hunk (r13): содержимое `+++ x` не заголовок.
    lookalike_full = ("diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n"
                      "@@ -9,1 +10,3 @@\n--- y\n+a\n+++ b\n+c\n")
    projected = rule.project_hunk_headers(lookalike_full)
    check("проекция заголовков не берёт содержимое, похожее на заголовок",
          projected == "diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n@@ -9,1 +10,3 @@\n"
          and rule.surface_lines(rule.parse_diff_surface(projected, projection="hunk-headers", where="t")) == {"f0.py": {10, 11, 12}},
          repr(projected))
    # LF-разбор (r16): U+2028/U+0085 внутри добавленной строки — не разделители.
    unicode_line = full_diff({"f0.py": [(10, 10)]}).replace("+line\n", "+a\u2028b\u0085c\n", 1)
    check("U+2028/U+0085 внутри добавленной строки не рвут hunk",
          rule.surface_lines(rule.parse_diff_surface(unicode_line, projection="full", where="t")) == {"f0.py": {10}})
    check("проекция заголовков тоже читает дифф по LF",
          rule.project_hunk_headers(unicode_line) == header_projection(unicode_line))
    # git-квотинг операндов (r12): табы, кавычки, октальные байты.
    quoted_tab = ('diff --git "a/f\\tx.py" "b/f\\tx.py"\n--- "a/f\\tx.py"\n+++ "b/f\\tx.py"\n'
                  "@@ -0,0 +1,1 @@\n+a\n")
    check("квотированный путь с табом декодируется",
          rule.surface_lines(rule.parse_diff_surface(quoted_tab, projection="full", where="t")) == {"f\tx.py": {1}})
    quoted_octal = ('diff --git "a/\\303\\251.py" "b/\\303\\251.py"\n--- "a/\\303\\251.py"\n'
                    '+++ "b/\\303\\251.py"\n@@ -0,0 +1,1 @@\n+a\n')
    check("квотированный путь с октальными байтами декодируется в UTF-8",
          rule.surface_lines(rule.parse_diff_surface(quoted_octal, projection="full", where="t")) == {"\u00e9.py": {1}})
    quoted_new = ('diff --git "a/q\\"x.py" "b/q\\"x.py"\nnew file mode 100644\n--- /dev/null\n'
                  '+++ "b/q\\"x.py"\n@@ -0,0 +1,1 @@\n+a\n')
    check("новый квотированный файл: сторона a/ выводится с сохранением квотинга",
          rule.surface_lines(rule.parse_diff_surface(quoted_new, projection="full", where="t")) == {'q"x.py': {1}})
    for name, text in (
        ("незакрытая кавычка", 'diff --git "a/x.py "b/x.py"\n--- "a/x.py\n+++ "b/x.py"\n@@ -0,0 +1,1 @@\n+a\n'),
        ("неизвестный escape", 'diff --git "a/\\qx.py" "b/\\qx.py"\n--- "a/\\qx.py"\n+++ "b/\\qx.py"\n@@ -0,0 +1,1 @@\n+a\n'),
        ("октальный escape выше одного байта", 'diff --git "a/\\541.py" "b/\\541.py"\n--- "a/\\541.py"\n+++ "b/\\541.py"\n@@ -0,0 +1,1 @@\n+a\n'),
        ("квотированные операнды diff --git не совпадают с заголовками",
         'diff --git "a/f\\tx.py" "b/f\\ty.py"\n--- "a/f\\tx.py"\n+++ "b/f\\tx.py"\n@@ -0,0 +1,1 @@\n+a\n'),
    ):
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text)
        lab.rejects(name, rounds)
    check("policy: окно описано хронологически, без исключения раундов без содержания",
          "ХРОНОЛОГИЧЕСКОМ" in TREADMILL["windowNote"] and "с сохранённым содержанием" not in TREADMILL["windowNote"])
    for value in (0, -1, True, "10", 1.5):
        rounds = treadmill()
        rounds[0]["declared"]["mechanisms"][0]["line"] = value
        lab.rejects(f"строка находки пересказа {value!r}", rounds)
    # Содержимое, похожее на заголовок (r8): `+++ x` внутри недолитого hunk —
    # добавленная строка `++ x`, `--- y` — удалённая `-- y`; путь не подменяется.
    lookalike = ("diff --git a/f0.py b/f0.py\n--- a/f0.py\n+++ b/f0.py\n"
                 "@@ -9,1 +10,3 @@\n--- y\n+a\n+++ b\n+c\n")
    rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", lookalike)
    lookalike_decision = lab.decide(rounds)
    check("строки '+++ '/'--- ' внутри hunk — содержимое, критерий взводится",
          lookalike_decision["terminal"] == "SURFACE_TREADMILL",
          f"{lookalike_decision['terminal']}: {lookalike_decision['surface']['why']}")
    check("строки-двойники заголовков не подменяют путь файла",
          rule.surface_lines(rule.parse_diff_surface(lookalike, projection="full", where="t")) == {"f0.py": {10, 11, 12}})
    # Полнота hunk (r2): содержимое обязано совпасть с заголовком строка в строку.
    base_text = full_diff({"f0.py": [(10, 12)]})
    for name, text in (
        ("недолитый hunk (EOF)", base_text.replace("+line\n+line\n+line\n", "+line\n+line\n")),
        ("перелитый hunk", base_text.replace("+line\n+line\n+line\n", "+line\n" * 4)),
        ("недолитый hunk перед следующим файлом",
         base_text.replace("+line\n+line\n+line\n", "+line\n") + full_diff({"z.py": [(1, 1)]})),
        ("удалённая строка сверх заголовка", base_text.replace("+line\n", "-gone\n+line\n", 1)),
        ("удалённый файл с новыми строками в заголовке",
         "diff --git a/g.py b/g.py\n--- a/g.py\n+++ /dev/null\n@@ -1,1 +0,1 @@\n-x\n" + base_text),
    ):
        rounds = treadmill(); rounds[0]["surface"] = lab.evidence("t0", text)
        lab.rejects(name, rounds)
    # Живые деревья (r4): объект улики обязан быть типа tree, коммит — отказ;
    # настоящие деревья — пересчёт проекции и verified.
    with tempfile.TemporaryDirectory() as git_tmp:
        repo = Path(git_tmp)

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()

        git("init", "-q")
        git("config", "user.email", "oracle@example.invalid")
        git("config", "user.name", "oracle")
        (repo / "f0.py").write_text("a\nb\nc\n", encoding="utf-8")
        git("add", "-A")
        base_tree = git("write-tree")
        git("commit", "-q", "-m", "base")
        (repo / "f0.py").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        git("add", "-A")
        cand_tree = git("write-tree")
        git("commit", "-q", "-m", "cand")
        head = git("rev-parse", "HEAD")
        (repo / "journal.md").write_text("journal\n", encoding="utf-8")
        projection = rule.surface_projection(repo, base_tree, cand_tree, "hunk-headers")
        (repo / "ev.surface").write_text(projection, encoding="utf-8")
        live_round = {"id": "g", "terminal": "verdict",
                      "provenance": {"class": "narrative", "path": "journal.md", "line": 1},
                      "candidate": cand_tree[:16],
                      "surface": {"class": "diff-hunks", "projection": "hunk-headers", "path": "ev.surface",
                                  "sha256": sha_text(projection), "baseTree": base_tree, "candidateTree": cand_tree},
                      "declared": {"verdict": "BLOCKED", "mechanisms": [mechanism("f0.py", "correctness", line=4)]}}
        live = rule.decide(synthetic([live_round], surfaceBaseline={"tree": base_tree},
                                     candidateSource={"kind": "reviewed-tree"}), policy, repo)
        live_item = live["surface"]["rounds"][0]
        check("живые деревья: проекция пересчитана и сверена, личность verified",
              live_item["verifiedAgainstTrees"] is True and live_item["onAdded"] == 1
              and live["candidateIdentities"] == {"declared": 1, "verified": 1, "unverifiable": 0},
              json.dumps([live_item, live["candidateIdentities"]]))
        empty_projection = rule.surface_projection(repo, cand_tree, cand_tree, "hunk-headers")
        (repo / "empty.surface").write_bytes(b"")
        same_round = copy.deepcopy(live_round)
        same_round["surface"].update(path="empty.surface", sha256=sha_text(""), baseTree=cand_tree)
        same_decision = rule.decide(synthetic([same_round], surfaceBaseline={"tree": cand_tree},
                                              candidateSource={"kind": "reviewed-tree"}), policy, repo)
        check("идентичные деревья: проекция пуста байт в байт и сверяется с пустой уликой",
              empty_projection == "" and same_decision["surface"]["rounds"][0]["verifiedAgainstTrees"] is True
              and same_decision["surface"]["rounds"][0]["onAdded"] == 0,
              repr(empty_projection))
        check("живой репозиторий: отсутствующий объект — None без разбора stderr",
              rule.git_object_type(repo, "f" * 40) is None)
        # Linked worktree (r14): `.git` — файл, объекты доступны.
        linked = Path(git_tmp) / "linked"
        git("worktree", "add", "-q", "--detach", str(linked))
        check("linked worktree: `.git`-файл не мешает живой проверке дерева",
              (linked / ".git").is_file() and rule.git_object_type(linked, cand_tree) == "tree",
              str(rule.git_object_type(linked, cand_tree)))
        absent_base = copy.deepcopy(live_round)
        absent_base["surface"]["baseTree"] = "f" * 40
        absent_base["surface"]["candidateTree"] = head
        absent_base["candidate"] = head[:16]
        checks += 1
        try:
            rule.decide(synthetic([absent_base], surfaceBaseline={"tree": "f" * 40},
                                  candidateSource={"kind": "synthetic"}), policy, repo)
            failures.append("при отсутствующей базе дерево кандидата не проверено на тип")
        except rule.StopRuleError:
            pass
        # Полное окно R7 на живых деревьях: 5 последовательных кандидатов, каждый
        # добавляет строки, находки — только в добавленном; улики пересчитаны по
        # деревьям, личности verified, терминал взведён (пробел, названный чекером c1).
        window_rounds = []
        content = "a\nb\nc\nd\ne\n"
        for k in range(WINDOW):
            content += f"w{k}\n"
            (repo / "f0.py").write_text(content, encoding="utf-8")
            git("add", "-A")
            step_tree = git("write-tree")
            git("commit", "-q", "-m", f"w{k}")
            step_projection = rule.surface_projection(repo, base_tree, step_tree, "hunk-headers")
            (repo / f"w{k}.surface").write_text(step_projection, encoding="utf-8")
            window_rounds.append({
                "id": f"w{k}", "terminal": "verdict",
                "provenance": {"class": "narrative", "path": "journal.md", "line": 1},
                "candidate": step_tree[:16],
                "surface": {"class": "diff-hunks", "projection": "hunk-headers", "path": f"w{k}.surface",
                            "sha256": sha_text(step_projection), "baseTree": base_tree, "candidateTree": step_tree},
                "declared": {"verdict": "BLOCKED",
                             "mechanisms": [mechanism("f0.py", f"class-{k}", line=6 + k)]},
            })
        live_window = rule.decide(synthetic(window_rounds, surfaceBaseline={"tree": base_tree},
                                            candidateSource={"kind": "reviewed-tree"}), policy, repo)
        check("R7 на живых деревьях: полное окно, пересчёт 5/5, личности verified, терминал взведён",
              live_window["terminal"] == "SURFACE_TREADMILL"
              and all(item["verifiedAgainstTrees"] is True for item in live_window["surface"]["rounds"])
              and live_window["candidateIdentities"] == {"declared": WINDOW, "verified": WINDOW, "unverifiable": 0},
              f"{live_window['terminal']} {live_window['candidateIdentities']} {live_window['surface']['why']}")
        git("reset", "-q", "--hard", "HEAD~" + str(WINDOW))
        forged = copy.deepcopy(live_round)
        forged["candidate"] = head[:16]
        forged["surface"]["candidateTree"] = head
        checks += 1
        try:
            rule.decide(synthetic([forged], surfaceBaseline={"tree": base_tree},
                                  candidateSource={"kind": "reviewed-tree"}), policy, repo)
            failures.append("объект-коммит принят как дерево кандидата")
        except rule.StopRuleError:
            pass
        tampered_text = projection.replace("+4,2", "+1,5")
        check("лаборатория: проекция содержит ожидаемый hunk", tampered_text != projection)
        (repo / "ev2.surface").write_text(tampered_text, encoding="utf-8")
        tampered = copy.deepcopy(live_round)
        tampered["surface"].update(path="ev2.surface", sha256=sha_text(tampered_text))
        checks += 1
        try:
            rule.decide(synthetic([tampered], surfaceBaseline={"tree": base_tree},
                                  candidateSource={"kind": "reviewed-tree"}), policy, repo)
            failures.append("подложная проекция с верным sha прошла мимо пересчёта по деревьям")
        except rule.StopRuleError:
            pass
    # Сбой исполнения git (r5) — отказ, а не «непроверяемо».
    with tempfile.TemporaryDirectory() as git_tmp:
        repo = Path(git_tmp)
        (repo / ".git").mkdir()
        real_run = rule.subprocess.run

        class RepoYes:
            returncode = 0
            stdout = "true\n"
            stderr = ""

        def fake_git(response):
            """Подмена subprocess.run: rev-parse отвечает «репозиторий есть»,
            остальное — заданный ответ или исключение."""
            def run(args, *rest, **kwargs):
                if "rev-parse" in args:
                    return RepoYes()
                if isinstance(response, BaseException):
                    raise response
                return response
            return run

        class Broken:
            returncode = 129
            stdout = ""
            stderr = "fatal: index file corrupt"

        for name, fake in (
            ("git недоступен", fake_git(OSError("no git"))),
            ("git завис", fake_git(rule.subprocess.TimeoutExpired("git", 30))),
            ("репозиторий повреждён", fake_git(Broken())),
        ):
            rule.subprocess.run = fake
            try:
                checks += 1
                try:
                    rule.require_live_tree(repo, "a" * 40, "test")
                    failures.append(f"{name}: сбой проверки принят как «объекта нет»")
                except rule.StopRuleError:
                    pass
            finally:
                rule.subprocess.run = real_run

        rule.subprocess.run = fake_git(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
        try:
            checks += 1
            try:
                rule.surface_projection(repo, "a" * 40, "b" * 40, "full")
                failures.append("байты вне UTF-8 при пересчёте не дали контролируемого отказа")
            except rule.StopRuleError:
                pass
        finally:
            rule.subprocess.run = real_run

        class Missing:
            returncode = 0
            stdout = "a" * 40 + " missing\n"
            stderr = ""

        rule.subprocess.run = fake_git(Missing())
        try:
            check("отсутствующий объект остаётся непроверяемым, а не отказом (batch-check)",
                  rule.require_live_tree(repo, "a" * 40, "test") is False)
        finally:
            rule.subprocess.run = real_run

        captured_env = {}

        def capture_env(args, *rest, **kwargs):
            captured_env["env"] = kwargs.get("env")
            return RepoYes()

        rule.subprocess.run = capture_env
        try:
            rule.git_repository_present(repo)
        finally:
            rule.subprocess.run = real_run
        check("git вызывается со стабильной локалью C (диагностики разбираются по тексту)",
              (captured_env.get("env") or {}).get("LC_ALL") == "C"
              and (captured_env.get("env") or {}).get("LANG") == "C")

        class RepoOdd:
            returncode = 0
            stdout = ""
            stderr = ""

        rule.subprocess.run = lambda args, *rest, **kwargs: RepoOdd()
        try:
            checks += 1
            try:
                rule.require_live_tree(repo, "a" * 40, "test")
                failures.append("rev-parse с exit 0 и пустым выводом принят как «репозитория нет»")
            except rule.StopRuleError:
                pass
        finally:
            rule.subprocess.run = real_run

        class Odd:
            returncode = 0
            stdout = "b" * 40 + " tree 10\n"
            stderr = ""

        rule.subprocess.run = fake_git(Odd())
        try:
            checks += 1
            try:
                rule.require_live_tree(repo, "a" * 40, "test")
                failures.append("ответ batch-check про другой oid принят")
            except rule.StopRuleError:
                pass
        finally:
            rule.subprocess.run = real_run
    # Архив вне UTF-8 (r14) — отказ, а не подмена символами.
    rounds = treadmill()
    # Невалидные байты ВНУТРИ содержательной строки: с errors="replace" такой
    # архив разбирался бы как валидный дифф.
    bad_bytes = full_diff({"f0.py": [(10, 12)]}).encode("utf-8").replace(b"+line\n", b"+\xff\xfe\n", 1)
    rel = "evidence/bad-utf8.diff"
    (lab.root / rel).write_bytes(bad_bytes)
    rounds[0]["surface"] = {"class": "diff-hunks", "projection": "full", "path": rel,
                            "sha256": hashlib.sha256(bad_bytes).hexdigest(),
                            "baseTree": BASE_TREE, "candidateTree": tree_id("t0")}
    lab.rejects("улика поверхности вне UTF-8", rounds)
    check("рендер печатает секцию поверхности и без улик — с причиной",
          "ПОВЕРХНОСТЬ" in rule.render(rule.decide(synthetic([
              narrative_round("a", "BLOCKED", [mechanism("s", "correctness")])]), policy, ROOT)))
    # Личности kind=reviewed-tree выводятся из улики поверхности.
    lab.rejects("reviewed-tree: личность не является префиксом candidateTree",
                treadmill(), candidateSource={"kind": "reviewed-tree"})
    unnamed = treadmill()
    for entry in unnamed:
        entry["candidate"] = tree_id(entry["id"])[:16]
    del unnamed[2]["candidate"]
    lab.rejects("reviewed-tree: раунд с уликой поверхности без объявленной личности",
                unnamed, candidateSource={"kind": "reviewed-tree"})
    tied = [lab.round(f"t{k}", "BLOCKED", [mechanism(f"f{k}.py", "correctness", line=10 + k)],
                      {f"f{k}.py": [(10 + k, 12 + k)]}, candidate=tree_id(f"t{k}")[:16])
            for k in range(WINDOW)]
    tied_decision = lab.decide(tied, candidateSource={"kind": "reviewed-tree"})
    check("reviewed-tree: личности из улик приняты и без git считаются непроверяемыми",
          tied_decision["candidateIdentities"] == {"declared": WINDOW, "verified": 0,
                                                   "unverifiable": WINDOW},
          json.dumps(tied_decision["candidateIdentities"]))
    # Иерархический отчёт продюсера: union находок без дублей, вердикт из интеграции.
    finding_a = {"file": "f.py", "line": 7, "category": "correctness", "severity": "important", "summary": "a"}
    finding_b = {"file": "g.py", "line": 9, "category": "security", "severity": "minor", "summary": "b"}
    hierarchical = {"kind": "hierarchical", "unitCalls": [{"report": {"findings": [finding_a]}}],
                    "integrationReport": {"verdict": "BLOCKED", "findings": [finding_a, finding_b]}}

    def report_round(document, round_id="h"):
        text = json.dumps(document, ensure_ascii=False)
        rel = f"evidence/{round_id}-{sha_text(text)[:8]}.json"
        (lab.root / rel).write_text(text, encoding="utf-8")
        return {"id": round_id, "terminal": "verdict",
                "provenance": {"class": "report", "path": rel, "sha256": sha_text(text)}}

    record = rule.read_round(report_round(hierarchical), 0, policy, lab.root)
    check("иерархический отчёт: находки юнита и интеграции объединены без дублей",
          [f["file"] for f in record["findings"]] == ["f.py", "g.py"] and record["verdict"] == "BLOCKED",
          json.dumps(record["findings"], ensure_ascii=False))
    check("иерархический отчёт: строка находки сохранена для критерия поверхности",
          [f["line"] for f in record["findings"]] == [7, 9])
    for name, document in (
        ("иерархический отчёт без integrationReport",
         {"unitCalls": [{"report": {"findings": [finding_a]}}]}),
        ("иерархический отчёт с unitCalls не списком",
         {"unitCalls": {}, "integrationReport": {"verdict": "BLOCKED", "findings": [finding_a]}}),
        ("иерархический отчёт с unitCalls[].report не объектом",
         {"unitCalls": [{"report": []}], "integrationReport": {"verdict": "BLOCKED", "findings": [finding_a]}}),
        ("плоский отчёт со строкой находки не целым",
         {"verdict": "BLOCKED", "findings": [dict(finding_a, line="7")]}),
        ("плоский отчёт со строкой находки булевой",
         {"verdict": "BLOCKED", "findings": [dict(finding_a, line=True)]}),
    ):
        checks += 1
        try:
            rule.read_round(report_round(document, "bad"), 0, policy, lab.root)
        except rule.StopRuleError:
            continue
        failures.append(f"{name}: вход принят, хотя обязан быть отвергнут")
    checks += 1
    try:
        # Интеграция читается первой: валидная единица идёт раньше булевой копии.
        rule.read_round(report_round({"unitCalls": [{"report": {"findings": [dict(finding_a, line=True)]}}],
                                      "integrationReport": {"verdict": "BLOCKED",
                                                            "findings": [dict(finding_a, line=1)]}},
                                     "bool-dup"), 0, policy, lab.root)
        failures.append("иерархический отчёт: булева строка спряталась за единицей в дедупе")
    except rule.StopRuleError:
        pass
    checks += 1
    try:
        rule.verify_reviewed_tree_candidates(
            {"rounds": [{"id": "x", "terminal": "verdict", "candidate": tree_id("x")[:3],
                         "surface": {"candidateTree": tree_id("x")}}]}, lab.root,
            {"declared": 0, "verified": 0, "unverifiable": 0})
        failures.append("reviewed-tree: личность короче 16 hex принята как префикс")
    except rule.StopRuleError:
        pass
    route_defect = lab.decide(treadmill(), policyBinding={"ledgerUnit": "synthetic",
                                                          "contractUnit": "other",
                                                          "criteriaPresent": True})
    check("цифры поверхности считаются и при ROUTE_DEFECT",
          route_defect["terminal"] == "ROUTE_DEFECT"
          and len(route_defect.get("surface", {}).get("rounds", [])) == WINDOW
          and "ПОВЕРХНОСТЬ" in rule.render(route_defect), route_defect["terminal"])
    flat = rule.read_round(report_round({"verdict": "BLOCKED", "findings": [finding_b]}, "flat"),
                           0, policy, lab.root)
    check("плоский отчёт читается как прежде, строка находки доступна",
          flat["findings"][0]["line"] == 9 and flat["verdict"] == "BLOCKED")

# Реплей PILOT-P02: терминал сверен с независимым замером по транскрипту.
p02_history = load("pilot-p02")
p02 = decisions["pilot-p02"]
p02_evidenced = [item for item in p02["surface"]["rounds"] if item["evidence"]]
check("pilot-p02: R1 взводится на r14 по ключу test-coverage — совпадает с замером",
      p02["terminal"] == "REDESIGN_OR_DISCARD" and p02["atRound"] == "r14"
      and p02.get("mechanism") == "tests/verify_blind_protocol.py::test-coverage",
      f"{p02['terminal']} @ {p02['atRound']} {p02.get('mechanism')}")
check("pilot-p02: поверхность измерена у всех 18 вердиктов с содержанием",
      len(p02_evidenced) == 18, str(len(p02_evidenced)))
check("pilot-p02: цифры поверхности совпадают с записанным замером (r70 — 0/1, опровержение знаменатель не трогает)",
      {item["round"]: f"{item['onAdded']}/{item['located']}" for item in p02_evidenced}
      == p02_history["measured"]["onAddedSurface"]
      and p02_history["measured"]["onAddedSurface"]["r70"] == "0/1",
      json.dumps({item["round"]: f"{item['onAdded']}/{item['located']}" for item in p02_evidenced}))
check("pilot-p02: R7 не взводится — в окне раунд r70 без засчитанных находок",
      p02["surface"]["evaluated"] is True and p02["surface"]["terminalArmed"] is False
      and "r70" in p02["surface"]["why"], p02["surface"]["why"])
check("pilot-p02: строки находок помечены пересказом, не машинной уликой",
      all(item["narrativeLines"] for item in p02_evidenced))
check("pilot-p02: личности кандидатов выведены из улик поверхности",
      p02["candidateIdentities"]["declared"] == 18, json.dumps(p02["candidateIdentities"]))
check("pilot-p02: полная раскладка терминалов — 21 вердикт, 1 предусловие, 4 транспорта, 26 заходов, 47 пробелов",
      p02["counters"] == {"verdict": 21, "precondition": 1, "transport": 4}
      and p02["attempts"] == 26 and len(p02["knownGaps"]) == 47,
      json.dumps(p02["counters"]))
p02_recomputed = sum(1 for item in p02_evidenced if item["verifiedAgainstTrees"] is True)
print(f"PILOT-P02 SURFACE: проекции пересчитаны по живым деревьям {p02_recomputed}/18 "
      f"(0 на клоне без loose-объектов — ожидаемо)")
mutated_p02 = copy.deepcopy(p02_history)
mutated_p02["rounds"][[r["id"] for r in mutated_p02["rounds"]].index("r62")]["surface"]["sha256"] = "0" * 64
rejects("pilot-p02: подмена sha улики поверхности отвергается", mutated_p02, policy)
mutated_p02 = copy.deepcopy(p02_history)
mutated_p02.pop("surfaceBaseline")
rejects("pilot-p02: история с уликами поверхности без базы серии отвергается", mutated_p02, policy)
mutated_p02 = copy.deepcopy(p02_history)
r62 = mutated_p02["rounds"][[r["id"] for r in mutated_p02["rounds"]].index("r62")]
r62["declared"]["mechanisms"][0]["line"] = 1
moved = rule.decide(mutated_p02, policy, ROOT)
moved_r62 = next(item for item in moved["surface"]["rounds"] if item["round"] == "r62")
check("pilot-p02: перенос строки находки на исходную поверхность меняет цифру раунда",
      moved_r62["onAdded"] == 2 and moved_r62["counted"] == 3, json.dumps(moved_r62))
mutated_p02 = copy.deepcopy(p02_history)
r70 = mutated_p02["rounds"][[r["id"] for r in mutated_p02["rounds"]].index("r70")]
r70["declared"]["mechanisms"][0].pop("refuted"); r70["declared"]["mechanisms"][0].pop("why")
unrefuted = rule.decide(mutated_p02, policy, ROOT)
unrefuted_r70 = next(item for item in unrefuted["surface"]["rounds"] if item["round"] == "r70")
refuted_r70 = next(item for item in p02["surface"]["rounds"] if item["round"] == "r70")
check("pilot-p02: без опровержения r70 его находка становится засчитанной и лежит на исходной поверхности",
      unrefuted_r70["counted"] == 1 and unrefuted_r70["liveOffSurface"] == 1
      and refuted_r70["counted"] == 0 and refuted_r70["located"] == 1
      and "r70 0/1" in unrefuted["surface"]["why"]
      and "без засчитанных" not in unrefuted["surface"]["why"],
      json.dumps([unrefuted_r70, refuted_r70, unrefuted["surface"]["why"]], ensure_ascii=False))

print(f"LIVE BINDING: ledger={binding['ledgerUnit']} contract={binding['contractUnit']} "
      f"criteria={binding['criteriaTotal']} passed={binding['criteriaMatchingStatus']} "
      f"aligned={binding['aligned']}")
if failures:
    print(f"RESULT: {checks - len(failures)} passed, {len(failures)} failed")
    for item in failures:
        print(f"  FAIL {item}")
    raise SystemExit(1)
print(f"RESULT: {checks} passed, 0 failed")
