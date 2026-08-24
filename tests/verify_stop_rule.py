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
import json
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
    "r6-coarse-grouping": "tests/references/stop-rule/r6-coarse-grouping.json",
    "gpg-001-broker-policy": "tests/references/stop-rule/gpg-001-broker-policy.json",
    "lpd003-1-publication": "tests/references/stop-rule/lpd003-1-publication.json",
    "lpd003-1-2026-08-23": "tests/references/stop-rule/lpd003-1-2026-08-23.json",
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
)

# Документы, на которые истории ссылаются как на ЗАПИСЬ решения. Тоже
# литералами: иначе impact-карта видит один цитируемый журнал и не видит
# другой, и targeted-прогон пропускает оракул при правке второго.
SOURCE_FILES = (
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
        "candidateSource": "id раунда — синтетические раунды моделируют перечеканенного кандидата",
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
        "candidate": candidate if candidate is not None else f"cand-{round_id}",
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
check("r6: грубая группировка переворачивает терминал — и это объявлено",
      decisions["r6-coarse-grouping"]["terminal"] == "REDESIGN_OR_DISCARD"
      and r6["terminal"] == "CLOSE")


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

# Терминал не зависит от порядка раундов.
gpg_history = load("gpg-001-broker-policy")
shuffled = copy.deepcopy(gpg_history)
shuffled["rounds"] = list(reversed(shuffled["rounds"]))
shuffled_decision = rule.decide(shuffled, policy, ROOT)
check("порядок раундов не меняет терминал",
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
rejects("группа слияния из одного ключа",
        synthetic([narrative_round("a", "PASSED", [])],
                  mergeKeys=[{"label": "x", "members": [["f", "c"]]}]), policy)
rejects("РАЗДЕЛЕНИЕ ключа между двумя группами",
        synthetic([narrative_round("a", "PASSED", [])],
                  mergeKeys=[{"label": "x", "members": [["f", "c"], ["g", "c"]]},
                             {"label": "y", "members": [["f", "c"], ["h", "c"]]}]), policy)
rejects("criteriaPresent непустой строкой вместо булева",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "A", "contractUnit": "A",
                                 "criteriaPresent": "да"}), policy)
rejects("criteriaPresent числом",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "A", "contractUnit": "A",
                                 "criteriaPresent": 1}), policy)
rejects("дефект привязки не отменяет проверку провенанса раундов",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "c1",
                    "provenance": {"class": "report", "path": EVIDENCE_FILES[0],
                                   "sha256": "0" * 64}}],
                  policyBinding={"ledgerUnit": "A", "contractUnit": "B",
                                 "criteriaPresent": True}), policy)
rejects("дефект привязки не отменяет проверку исхода раунда",
        synthetic([{"id": "a", "terminal": "transport", "outcome": "LOOKS_FINE",
                    "provenance": {"class": "absent"}}],
                  policyBinding={"ledgerUnit": "A", "contractUnit": "B",
                                 "criteriaPresent": True}), policy)
rejects("привязка политики без поля criteriaPresent",
        synthetic([narrative_round("a", "PASSED", [])],
                  policyBinding={"ledgerUnit": "A", "contractUnit": "A"}), policy)

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
    "id": "a", "terminal": "verdict", "candidate": "cand-a",
    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE, "line": SYNTHETIC_LINE},
    "declared": {"verdict": "BLOCKED", "contentRecorded": False,
                 "why": "отчёт не сохранён"}}])
check("вердикт с цитатой и объявленной утратой содержания принимается и виден отдельно",
      rule.decide(unrecorded_verdict, policy, ROOT)["contentMissing"] == ["a"])
rejects("утрата содержания без основания",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "c",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "contentRecorded": False}}]), policy)
rejects("утрата содержания вместе с объявленными механизмами",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "c",
                    "provenance": {"class": "narrative", "path": SYNTHETIC_SOURCE,
                                   "line": SYNTHETIC_LINE},
                    "declared": {"verdict": "BLOCKED", "contentRecorded": False,
                                 "why": "нет", "mechanisms": [{"surface": "s",
                                                               "defectClass": "c"}]}}]),
        policy)
rejects("contentRecorded нелогического типа",
        synthetic([{"id": "a", "terminal": "verdict", "candidate": "c",
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
                    candidate="cand-x"),
    narrative_round("b", "BLOCKED", [mechanism("одна поверхность", "correctness")],
                    candidate="cand-x"),
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
check("чистый PASS не превращается в ROUTE_REPAIR из-за последующего срыва",
      rule.decide(pass_then_transport, policy, ROOT)["terminal"] == "CLOSE")

check("политика перечисляет оба новых терминала в порядке применения",
      policy["precedence"] == ["ROUTE_DEFECT", "REDESIGN_OR_DISCARD",
                               "RECURRENCE_UNCONFIRMED", "ROUTE_REPAIR",
                               "CLOSE", "CONTINUE"],
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

# Матрица провенанса: гарантия одинакова для ВСЕХ комбинаций
# (класс терминала x класс провенанса). Прежняя форма разводила проверки по
# отдельным ранним выходам, и каждая новая комбинация давала новую щель —
# три находки независимого ревьюера в одном классе за пять раундов.
for terminal_class, outcome in (("verdict", "BLOCKED"),
                                ("precondition", "UNVERIFIED"),
                                ("transport", "UNAVAILABLE")):
    base = {"id": "m", "terminal": terminal_class, "outcome": outcome,
            "candidate": "cand-m",
            "declared": {"verdict": outcome,
                         "mechanisms": [{"surface": "s", "defectClass": "c"}]}}
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
                 "candidateSource": "c",
                 "recordedDecision": {"terminal": "CLOSE", "atRound": "nope"},
                 "rounds": [narrative_round("a", "PASSED", [])]})
rejects_on_load("recordedDecision не объект",
                {"schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
                 "candidateSource": "c", "recordedDecision": "CLOSE",
                 "rounds": [narrative_round("a", "PASSED", [])]})

# Обратная сторона той же гарантии: ссылка на ОБЪЯВЛЕННЫЙ пробел законна —
# иначе проверка выродилась бы в запрет ссылаться на невосстановимый раунд.
checks += 1
accepted_gap = {
    "schema": rule.HISTORY_SCHEMA, "unit": "x", "orderSource": "s",
    "candidateSource": "c",
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
                            and bool(binding["criteriaPresent"])))

route_defect_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "A", "contractUnit": "B", "criteriaPresent": True})
check("чужой юнит в контракте даёт ROUTE_DEFECT",
      rule.decide(route_defect_history, policy, ROOT)["terminal"] == "ROUTE_DEFECT")

no_criteria_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "A", "contractUnit": "A", "criteriaPresent": False})
check("отсутствие критериев юнита тоже даёт ROUTE_DEFECT",
      rule.decide(no_criteria_history, policy, ROOT)["terminal"] == "ROUTE_DEFECT")

aligned_history = synthetic(
    [narrative_round("a", "PASSED", [])],
    policyBinding={"ledgerUnit": "A", "contractUnit": "A", "criteriaPresent": True})
check("совпадающая привязка не мешает обычному решению",
      rule.decide(aligned_history, policy, ROOT)["terminal"] == "CLOSE")


# ---------------------------------------------------------------------------

print(f"LIVE BINDING: ledger={binding['ledgerUnit']} contract={binding['contractUnit']} "
      f"criteria={binding['criteriaTotal']} passed={binding['criteriaMatchingStatus']} "
      f"aligned={binding['aligned']}")
if failures:
    print(f"RESULT: {checks - len(failures)} passed, {len(failures)} failed")
    for item in failures:
        print(f"  FAIL {item}")
    raise SystemExit(1)
print(f"RESULT: {checks} passed, 0 failed")
