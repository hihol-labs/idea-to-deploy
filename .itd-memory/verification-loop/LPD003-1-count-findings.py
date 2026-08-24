"""Пересчёт находок по отчётам LPD-003-1 — раздельно и стабильно.

Прежняя версия считала по маске `LPD003-1-r*-report.md` ВСЁ подряд, включая
аудиты САМОЙ леджерной записи (r21+). Из-за этого счёт рос с каждой новой
проверкой честности записи и не сходился (находка ревьюера r23). Здесь
границы объявлены явно: раунды ревью КАНДИДАТА перечислены списком, аудиты
леджера считаются отдельно и в цифры записи не входят.
"""
import json
import re
import glob
import os

REPORTS = ".itd-memory/verification-loop/reports"
# Раунды ревью кандидата (код и тесты). Список ЯВНЫЙ, чтобы позднейшие
# аудиты леджера не попадали в цифру задним числом.
CANDIDATE_ROUNDS = ["r%d" % n for n in range(1, 21)]
# Аудиты леджерной записи считаются отдельно и в публикуемые цифры не входят.
# Список НЕ перечисляется: любая верхняя граница протухает от следующего же
# аудита (поймано дважды — сначала на числе, потом на диапазоне имён файлов).
# Аудит — это всё r*, что не входит в закрытый список раундов кандидата.


def blocks(text):
    out = [m.group(1) for m in re.finditer(r"```json\s*([\s\S]*?)```", text)]
    out += re.findall(r"\{[\s\S]*?\"verdict\"[\s\S]*?\}\s*$", text)
    return out


def load(path):
    text = open(path, encoding="utf-8").read()
    for block in reversed(blocks(text)):
        try:
            value = json.loads(block.strip())
        except Exception:
            continue
        if isinstance(value, dict) and "verdict" in value:
            return value
    return None


def key(name, finding):
    return (name, str(finding.get("file")), finding.get("line"),
            str(finding.get("summary"))[:80])


def tally(names):
    rounds, findings = 0, set()
    for name in names:
        path = os.path.join(REPORTS, "LPD003-1-%s-report.md" % name)
        if not os.path.isfile(path):
            continue
        document = load(path)
        if not document:
            continue
        rounds += 1
        for finding in document.get("findings", []):
            findings.add(key(name, finding))
    return rounds, len(findings)


producer_names = [os.path.basename(p).split("LPD003-1-")[1].split("-report")[0]
                  for p in sorted(glob.glob(os.path.join(REPORTS, "LPD003-1-PUB*-report.md")))]
pr_rounds, pr_findings = tally(producer_names)
ck_rounds, ck_findings = tally(CANDIDATE_ROUNDS)
all_r = [os.path.basename(p).split("LPD003-1-")[1].split("-report")[0]
         for p in sorted(glob.glob(os.path.join(REPORTS, "LPD003-1-r*-report.md")))]
ledger_audits = [name for name in all_r if name not in set(CANDIDATE_ROUNDS)]
au_rounds, au_findings = tally(ledger_audits)
print("producer rounds", pr_rounds, "findings", pr_findings)
print("candidate checker rounds", ck_rounds, "findings", ck_findings)
print("candidate total findings", pr_findings + ck_findings)
print("ledger-audit rounds (excluded)", au_rounds, "findings", au_findings)
