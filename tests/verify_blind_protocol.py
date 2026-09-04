#!/usr/bin/env python3
"""Functional tests for the blind semantic protocol (PILOT-P02, v1.103.0).

The protocol is the smoke acceptance of the verdict taxonomy: the owner
categorises a sample of NEW findings from the finding text alone, the author's
label hidden, and agreement at or above the threshold accepts the pilot.

What must hold, and why each guarantee has its own check:
  * the population is NEW records only - legacy rows were written before
    validation on write, so agreeing with their labels says nothing;
  * a short population REFUSES with the count named, it does not sample fewer;
  * the sample is reproducible from the recorded seed - a measurement nobody
    can re-derive is not evidence;
  * the worksheet carries NO author label, and offers exactly the vocabulary
    the record's own source is allowed to use;
  * scoring is exact-match with a hard threshold, and an incomplete or
    out-of-vocabulary answer sheet REFUSES instead of scoring as a miss;
  * the seal is tamper-evident: editing the protocol or the sampled record
    after sealing refuses the score;
  * one attempt per seal - a re-run on the same frozen sample is tuning.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_blind_protocol.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
sys.path.insert(0, str(ROOT / "skills" / "_shared"))
sys.dont_write_bytecode = True

import itd_blind_protocol as bp  # noqa: E402

PASSED = 0
FAILED = 0
TMPDIRS: list[Path] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS  %s" % name)
    else:
        FAILED += 1
        print("FAIL  %s%s" % (name, ("  — " + detail) if detail else ""))


def record(lineage: str, category: str, summary: str = "",
           source: str = "subagent-verdict", stamped: bool = True) -> dict:
    row = {
        "source": source,
        "lineage": lineage,
        "findings": [{
            "severity": "important",
            "category": category,
            "file": "a/%s.py" % lineage,
            "line": 7,
            "summary": summary or ("finding text for %s" % lineage),
        }],
    }
    if stamped:
        row["taxonomy_version"] = 1
    return row


def project(rows: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="bp-"))
    TMPDIRS.append(root)
    mem = root / ".itd-memory"
    mem.mkdir()
    with (mem / "review-findings.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return root


CATS = ["correctness", "test-coverage", "documentation-accuracy", "security",
        "dead-code", "readability", "performance", "duplication",
        "incomplete-fix", "swallowed-diagnostic", "naming-collision",
        "over-inclusive-input", "unsupported-claim"]


def full_rows(n: int = 12) -> list[dict]:
    return [record("n-%d" % i, CATS[i % len(CATS)]) for i in range(n)]


def answers_for(root, sealed: dict, correct: int) -> dict:
    """Лист ответов с заданным числом совпадений — по популяции этого дерева."""
    pool = {i["ref"]: i for i in bp.eligible(root, bp.load_protocol(ROOT))}
    out = {}
    for n, item in enumerate(sealed["items"]):
        true = pool[item["ref"]]["category"]
        out[item["id"]] = true if n < correct else next(
            c for c in CATS if c != true)
    return out


def main() -> int:
    proto = bp.load_protocol(ROOT)
    check("the frozen protocol loads and names its threshold",
          proto is not None and proto["scoring"]["threshold"] == 8
          and proto["sample"]["size"] == 10)
    check("the protocol carries the honest marking verbatim",
          "НЕ статистическая гарантия" in proto["honestMarking"])
    check("the protocol names what a failure does",
          "Q2" in proto["onFail"]["action"] and proto["onFail"]["then"])

    # Популяция: только НОВЫЕ записи.
    mixed = full_rows(10) + [
        record("legacy-1", "correctness", stamped=False),
        record("no-cat-1", "", ),
        record("ext-1", "unclassified", source="external-github-review"),
    ]
    root = project(mixed)
    pool = bp.eligible(root, proto)
    ids = {p["lineage"] for p in pool}
    check("an unstamped legacy record is outside the population",
          "legacy-1" not in {i["lineage"] for i in pool}, str(sorted(ids))[:200])
    check("a record without a category is outside the population",
          "no-cat-1" not in ids)
    check("a record from another source is outside the population",
          "ext-1" not in ids)
    check("every new reviewer record is inside the population",
          len(pool) == 10)
    # r1-1: единица замера — НАХОДКА, а не первая находка записи. Живой
    # леджер несёт 260 записей против 286 находок, поэтому «первая в записи»
    # молча сузила бы популяцию, из которой якобы случайно тянется выборка.
    multi = record("multi-1", "correctness")
    multi["findings"].append({"severity": "minor", "category": "readability",
                              "file": "b.py", "line": 3, "summary": "second"})
    multi["findings"].append({"severity": "minor", "category": "performance",
                              "file": "c.py", "line": 4, "summary": "third"})
    mroot = project([multi])
    mpool = bp.eligible(mroot, proto)
    check("every finding of a multi-finding record enters the population",
          len(mpool) == 3
          and {i["category"] for i in mpool} == {"correctness", "readability",
                                                 "performance"},
          str([i["ref"] for i in mpool]))
    check("findings of one record carry distinct identities",
          len({i["ref"] for i in mpool}) == 3, str([i["ref"] for i in mpool]))

    # Короткая популяция ОТКАЗЫВАЕТ и называет счёт.
    short = project(full_rows(9))
    refused = None
    try:
        bp.seal(short, proto)
    except bp.ProtocolError as exc:
        refused = exc
    check("a short population refuses instead of sampling fewer",
          refused is not None and "9" in str(refused) and "10" in str(refused),
          repr(refused)[:200])

    # Воспроизводимость выборки по записанному seed.
    big = project(full_rows(40))
    s1 = bp.seal(big, proto)
    s2 = bp.seal(big, proto)
    check("the same seed draws the same sample",
          [i["ref"] for i in s1["items"]] == [i["ref"] for i in s2["items"]])
    check("the sample draws without replacement",
          len({i["ref"] for i in s1["items"]}) == 10)
    check("the seal records the seed it actually derived",
          s1["seed"] == bp._derive_seed(proto, s1["population"]))
    # Воспроизводимость не имеет права зависеть от ПОРЯДКА строк в леджере:
    # ротация и параллельные писатели переставляют записи, а тот же seed
    # обязан давать ту же выборку. Детерминированно: та же популяция в
    # обратном порядке.
    rows = full_rows(40)
    fwd = project(rows)
    rev = project(list(reversed(rows)))
    a = bp.seal(fwd, proto)
    b = bp.seal(rev, proto)
    check("the same seed survives a reordered ledger",
          [i["ref"] for i in a["items"]] == [i["ref"] for i in b["items"]],
          "%s vs %s" % ([i["ref"] for i in a["items"]][:3],
                        [i["ref"] for i in b["items"]][:3]))
    # Жеребьёвка без возврата проверяется на популяции РОВНО в размер выборки:
    # там возврат обязан дать повтор, а не «повезло не столкнуться».
    exact = project(full_rows(10))
    e = bp.seal(exact, proto)
    check("a population of exactly the sample size is drawn whole, no repeats",
          len({i["ref"] for i in e["items"]}) == 10,
          str(sorted(i["ref"] for i in e["items"]))[:200])

    # Лист не показывает авторскую метку.
    sheet = bp.worksheet(big, proto, s1)
    blob = json.dumps(sheet, ensure_ascii=False)
    # Авторские метки берутся из ПОПУЛЯЦИИ, а не из одной печати: ниже
    # печатаются другие выборки, и карта обязана покрывать их все.
    # Популяции этих деревьев построены одним генератором, поэтому карта
    # авторских меток по ссылке общая для всех.
    author = {i["ref"]: i for i in bp.eligible(big, proto)}
    leaked = [it["id"] for it in sheet["items"] if "category" in it]
    check("the worksheet carries no category field at all",
          not leaked, str(leaked)[:160])
    check("the worksheet shows only the declared visible fields",
          all(set(it) <= {"id", "summary", "file", "line", "vocabulary"}
              for it in sheet["items"]),
          str(sorted(set().union(*(set(it) for it in sheet["items"]))))[:200])
    check("the worksheet offers the source vocabulary, not the flat one",
          "unclassified" not in sheet["vocabulary"]
          and len(sheet["vocabulary"]) == 13,
          str(len(sheet["vocabulary"])))
    check("the worksheet explains every offered value",
          all(v in sheet["meaning"] and sheet["meaning"][v]
              for v in sheet["vocabulary"]))
    # Словарь листа берётся ПО ИСТОЧНИКУ, а не плоским списком значений.
    # На поставляемом словаре оба совпадают, поэтому гарантия проверяется на
    # заглушке, где значение есть в общем списке, но источнику недоступно.
    stub = project(full_rows(12))
    shared = stub / "skills" / "_shared"
    shared.mkdir(parents=True)
    (shared / "BLIND_PROTOCOL.json").write_text(
        (ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    tax = json.loads((ROOT / "skills" / "_shared" / "VERDICT_TAXONOMY.json")
                     .read_text(encoding="utf-8"))
    tax["category"]["values"] = list(tax["category"]["values"]) + ["operator-only"]
    tax["category"]["meaning"]["operator-only"] = "Не выдаётся авторам находок."
    (shared / "VERDICT_TAXONOMY.json").write_text(
        json.dumps(tax, ensure_ascii=False), encoding="utf-8")
    stub_proto = bp.load_protocol(stub)
    stub_sheet = bp.worksheet(stub, stub_proto, bp.seal(stub, stub_proto))
    check("a value outside the source vocabulary is never offered",
          "operator-only" not in stub_sheet["vocabulary"],
          str(stub_sheet["vocabulary"])[-120:])
    # r1-2: словарь резолвится ПО ИСТОЧНИКУ КАЖДОЙ позиции. Популяция
    # допускает несколько источников, а у них разные разрешённые значения;
    # один словарь на весь лист показывал бы части выборки недостижимую метку.
    two = project([record("s-%d" % i, CATS[i % len(CATS)]) for i in range(6)]
                  + [record("e-%d" % i, "unclassified",
                            source="external-github-review") for i in range(6)])
    tshared = two / "skills" / "_shared"
    tshared.mkdir(parents=True)
    tproto_raw = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                            .read_text(encoding="utf-8"))
    tproto_raw["population"]["sourceIn"] = ["subagent-verdict",
                                            "external-github-review"]
    (tshared / "BLIND_PROTOCOL.json").write_text(
        json.dumps(tproto_raw, ensure_ascii=False), encoding="utf-8")
    (tshared / "VERDICT_TAXONOMY.json").write_text(
        (ROOT / "skills" / "_shared" / "VERDICT_TAXONOMY.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    tproto = bp.load_protocol(two)
    tseal = bp.seal(two, tproto)
    tsheet = bp.worksheet(two, tproto, tseal)
    tpool_by_ref = {i["ref"]: i for i in bp.eligible(two, tproto)}
    src_of = [tpool_by_ref[e["ref"]]["source"] for e in tseal["items"]]
    by_src = set(src_of)
    ext = [it for it, src in zip(tsheet["items"], src_of)
           if src == "external-github-review"]
    own = [it for it, src in zip(tsheet["items"], src_of)
           if src == "subagent-verdict"]
    check("a mixed-source sample really contains both sources",
          by_src == {"subagent-verdict", "external-github-review"}, str(by_src))
    check("only the external source is offered its external-only value",
          all("unclassified" in it["vocabulary"] for it in ext)
          and all("unclassified" not in it["vocabulary"] for it in own),
          "ext=%d own=%d" % (len(ext), len(own)))
    # И скоринг проверяет ответ по словарю ЭТОЙ позиции, а не по общему.
    bad = {it["id"]: "unclassified" for it in tsheet["items"]}
    refused = None
    try:
        bp.score(two, tproto, tseal, bad)
    except bp.ProtocolError as exc:
        refused = exc
    check("an answer valid for another source is refused for this one",
          refused is not None and "subagent-verdict" in str(refused),
          repr(refused)[:200])
    check("the worksheet repeats the honest marking to the labeller",
          "НЕ статистическая гарантия" in blob)

    def answers(root_seal, correct: int) -> dict:
        out = {}
        for n, item in enumerate(root_seal["items"]):
            true = author[item["ref"]]["category"]
            if n < correct:
                out[item["id"]] = true
            else:
                wrong = next(c for c in CATS if c != true)
                out[item["id"]] = wrong
        return out

    # Порог: 7 — провал, 8 — приёмка.
    big7 = project(full_rows(40))
    s7 = bp.seal(big7, proto)
    v7 = bp.score(big7, proto, s7, answers(s7, 7))
    check("seven of ten does not accept the pilot",
          v7["matches"] == 7 and v7["verdict"] == "FAILED", json.dumps(v7)[:200])
    check("a failing verdict names the fail action",
          "Q2" in json.dumps(v7, ensure_ascii=False))
    big8 = project(full_rows(40))
    s8 = bp.seal(big8, proto)
    v8 = bp.score(big8, proto, s8, answers(s8, 8))
    check("eight of ten accepts the pilot",
          v8["matches"] == 8 and v8["verdict"] == "PASSED", json.dumps(v8)[:200])
    # r4: сирота временного файла с ИМЕНЕМ ПО PID (крах предыдущего скорера,
    # PID переиспользован) не должна блокировать единственную попытку: имя
    # временного файла уникально, а FileExistsError означает только целевой путь.
    big_orphan = project(full_rows(40))
    s_orphan = bp.seal(big_orphan, proto)
    orphan_target = bp._verdict_path(big_orphan, s_orphan)
    orphan_target.parent.mkdir(parents=True, exist_ok=True)
    orphan = orphan_target.with_name(orphan_target.name + ".%d.tmp" % os.getpid())
    orphan.write_text("{broken", encoding="utf-8")
    v_orphan = bp.score(big_orphan, proto, s_orphan, answers(s_orphan, 8))
    check("an orphan pid-named temp file does not block the sole attempt",
          v_orphan["verdict"] == "PASSED" and orphan_target.exists()
          and orphan.read_text(encoding="utf-8") == "{broken",
          json.dumps(v_orphan)[:160])
    check("the verdict carries the honest marking",
          "НЕ статистическая гарантия" in json.dumps(v8, ensure_ascii=False))
    check("the verdict binds the protocol and the seed it used",
          v8["protocolDigest"] == bp.protocol_digest(proto)
          and v8["seed"] == bp._derive_seed(proto, s8["population"]))

    # Неполный и внесловарный лист ответов ОТКАЗЫВАЮТ.
    big9 = project(full_rows(40))
    s9 = bp.seal(big9, proto)
    a9 = answers(s9, 10)
    a9.pop(sorted(a9)[0])
    refused = None
    try:
        bp.score(big9, proto, s9, a9)
    except bp.ProtocolError as exc:
        refused = exc
    check("an incomplete answer sheet refuses instead of scoring a miss",
          refused is not None, repr(refused)[:160])
    a9b = answers(s9, 10)
    a9b[sorted(a9b)[0]] = "не-из-словаря"
    refused = None
    try:
        bp.score(big9, proto, s9, a9b)
    except bp.ProtocolError as exc:
        refused = exc
    check("an out-of-vocabulary answer refuses instead of counting as a miss",
          refused is not None, repr(refused)[:160])

    # Печать защищает от подмены протокола и записи.
    big10 = project(full_rows(40))
    s10 = bp.seal(big10, proto)
    tampered = json.loads(json.dumps(proto))
    tampered["scoring"]["threshold"] = 5
    refused = None
    try:
        bp.score(big10, tampered, s10, answers(s10, 10))
    except bp.ProtocolError as exc:
        refused = exc
    check("a protocol edited after the seal refuses the score",
          refused is not None, repr(refused)[:160])

    ledger = big10 / ".itd-memory" / "review-findings.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    target = s10["items"][0]["ref"].split("#")[0]
    out = []
    for ln in lines:
        row = json.loads(ln)
        if row.get("lineage") == target:
            # Значение выбирается ГАРАНТИРОВАННО отличным от исходного: жёстко
            # зашитая категория могла совпасть с уже стоящей, фикстура тогда
            # не менялась бы, и оракул ждал бы отказа от нетронутых данных.
            was = row["findings"][0]["category"]
            row["findings"][0]["category"] = next(c for c in CATS if c != was)
        out.append(json.dumps(row, ensure_ascii=False))
    ledger.write_text("\n".join(out) + "\n", encoding="utf-8")
    refused = None
    try:
        bp.score(big10, proto, s10, answers(s10, 10))
    except bp.ProtocolError as exc:
        refused = exc
    check("a sampled record edited after the seal refuses the score",
          refused is not None, repr(refused)[:160])
    # r3-1: печать не принимается на веру — выборка ПЕРЕСОБИРАЕТСЯ по
    # записанному seed. Иначе правка seal.json подменяет случайную выборку
    # удобными находками и выдаёт проходной вердикт, обнуляя разом заморозку
    # выборки, tamper-evidence и одну попытку.
    forge_root = project(full_rows(40))
    honest = bp.seal(forge_root, proto)
    pool_forge = {i["ref"]: i for i in bp.eligible(forge_root, proto)}
    picked = {e["ref"] for e in honest["items"]}
    spare = [r for r in sorted(pool_forge) if r not in picked]

    def refuses(mutate) -> str:
        forged = json.loads(json.dumps(honest))
        mutate(forged)
        try:
            bp.score(forge_root, proto, forged,
                     {"item-%02d" % (n + 1): "correctness" for n in range(10)})
        except bp.ProtocolError as exc:
            return str(exc)
        return ""

    def swap(doc):
        doc["items"][0]["ref"] = spare[0]
        doc["items"][0]["digest"] = pool_forge[spare[0]]["digest"]
    check("a cherry-picked item in the seal refuses the score",
          bool(refuses(swap)), "no refusal")

    def duplicate(doc):
        doc["items"][1] = json.loads(json.dumps(doc["items"][0]))
        doc["items"][1]["id"] = "item-02"
    # Дубль ловится ИМЕНЕМ причины, а не только фактом отказа: пересборка
    # отвергла бы его и так, но тогда владелец увидел бы «seed не сходится»
    # вместо «в печати повторяются находки», и страж был бы мёртвым кодом.
    check("a duplicated item is refused as a duplicate, by name",
          "повторяются" in refuses(duplicate), refuses(duplicate)[:140])

    def truncate(doc):
        doc["items"] = doc["items"][:9]
    check("a seal with fewer items than the protocol demands refuses",
          bool(refuses(truncate)), "no refusal")

    def shrink_population(doc):
        doc["population"] = doc["population"][:5]
    check("a seal whose population digest stops matching refuses",
          bool(refuses(shrink_population)), "no refusal")

    # r4-1: САМОСОГЛАСОВАННАЯ подделка. Дайджест популяции считается по её же
    # содержимому, поэтому редактор мог подставить десяток удобных находок,
    # пересчитать дайджест и подобрать items под тот же seed — и печать
    # осталась бы внутренне непротиворечивой. Спасает только сверка с живой
    # популяцией.
    def forge_consistent(doc):
        favourable = [{"ref": r, "digest": pool_forge[r]["digest"]}
                      for r in sorted(pool_forge)[:10]]
        doc["population"] = favourable
        doc["populationDigest"] = bp._digest(favourable)
        doc["populationSize"] = len(favourable)
        drawn = bp._draw(favourable, 10, doc["seed"])
        doc["items"] = [{"id": "item-%02d" % (n + 1), "ref": d["ref"],
                         "digest": d["digest"]}
                        for n, d in enumerate(drawn)]
    reason = refuses(forge_consistent)
    check("a self-consistent forged population is refused against the live one",
          "не совпадает с текущей популяцией" in reason, reason[:180])
    # То же правило закрывает и обратный случай: находка, появившаяся между
    # печатью и разметкой, делает выборку неслучайной задним числом.
    grow_root = project(full_rows(40))
    grown = bp.seal(grow_root, proto)
    ledger_grow = grow_root / ".itd-memory" / "review-findings.jsonl"
    with ledger_grow.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record("zz-new", "security"), ensure_ascii=False) + "\n")
    grew = None
    try:
        bp.score(grow_root, proto, grown,
                 {"item-%02d" % (n + 1): "correctness" for n in range(10)})
    except bp.ProtocolError as exc:
        grew = exc
    check("a finding written after the seal closes the window with a refusal",
          grew is not None and "Окно замера" in str(grew), repr(grew)[:180])

    def reseed(doc):
        doc["seed"] = "0" * 32
    check("a seal whose seed no longer draws its own items refuses",
          bool(refuses(reseed)), "no refusal")

    # r3-2: версия протокола и тип флага поколений — fail-closed.
    for label, block, field, value in [
            ("protocol_version", None, "protocol_version", 2),
            ("population.includeRotatedGenerations", "population",
             "includeRotatedGenerations", "yes")]:
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        if block:
            doc[block][field] = value
        else:
            doc[field] = value
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        refused_v = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            refused_v = exc
        check("a contract contradicting the implementation refuses: %s" % label,
              refused_v is not None, repr(refused_v)[:140])

    # Одна попытка на печать.
    fresh = project(full_rows(40))
    s11 = bp.seal(fresh, proto)
    bp.score(fresh, proto, s11, answers(s11, 10))
    refused = None
    try:
        bp.score(fresh, proto, s11, answers(s11, 10))
    except bp.ProtocolError as exc:
        refused = exc
    check("a second score on the same seal refuses",
          refused is not None, repr(refused)[:160])
    # r1-3: заявка на попытку АТОМАРНА. Проверка «файла нет» с последующей
    # записью — гонка: несколько скореров одновременно видят пустоту и
    # затирают друг друга, а «одна попытка на печать» становится пожеланием.
    # Детерминированно: восемь процессов стартуют по общему барьеру, ровно
    # один обязан вынести вердикт.
    import subprocess
    race = project(full_rows(40))
    s_race = bp.seal(race, proto)
    seal_file = race / "seal.json"
    seal_file.write_text(json.dumps(s_race, ensure_ascii=False), encoding="utf-8")
    pool_race = {i["ref"]: i for i in bp.eligible(race, proto)}
    ans_file = race / "ans.json"
    ans_file.write_text(json.dumps(
        {it["id"]: pool_race[it["ref"]]["category"] for it in s_race["items"]}),
        encoding="utf-8")
    # Барьер, а не стенные часы: при последовательном запуске ранние дети на
    # медленном хосте успевали закончить до старта поздних, и сломанная
    # реализация check-then-write прошла бы, дав ровно один SCORED. Теперь
    # каждый ребёнок объявляет готовность и ждёт общего разрешения родителя.
    ready_dir = race / "ready"
    ready_dir.mkdir()
    go_file = race / "go"
    racer = (
        "import json, os, sys, time\n"
        "sys.path.insert(0, %r)\n"
        "import itd_blind_protocol as bp\n"
        "open(os.path.join(%r, sys.argv[1]), 'w').close()\n"
        "while not os.path.exists(%r):\n"
        "    pass\n"
        "proto = bp.load_protocol(%r)\n"
        "sealed = json.load(open(%r, encoding='utf-8'))\n"
        "answers = json.load(open(%r, encoding='utf-8'))\n"
        "try:\n"
        "    bp.score(%r, proto, sealed, answers)\n"
        "    print('SCORED')\n"
        "except bp.ProtocolError:\n"
        "    print('REFUSED')\n"
        % (str(ROOT / "skills" / "_shared"), str(ready_dir), str(go_file),
           str(race), str(seal_file), str(ans_file), str(race)))
    procs = [subprocess.Popen([PY, "-c", racer, "w%d" % n],
                              stdout=subprocess.PIPE, text=True)
             for n in range(8)]
    deadline = time.time() + 60
    while len(list(ready_dir.iterdir())) < 8 and time.time() < deadline:
        time.sleep(0.01)
    all_ready = len(list(ready_dir.iterdir())) == 8
    go_file.write_text("", encoding="utf-8")
    outs = [pr.communicate()[0].strip() for pr in procs]
    check("exactly one of eight concurrent scorers claims the attempt",
          all_ready and outs.count("SCORED") == 1
          and outs.count("REFUSED") == 7,
          "ready=%s outs=%s" % (all_ready, outs))
    # А отказавший замер попытку НЕ тратит: отказ — это не вердикт.
    spend = project(full_rows(40))
    s_spend = bp.seal(spend, proto)
    partial = answers_for(spend, s_spend, 10)
    partial.pop(sorted(partial)[0])
    try:
        bp.score(spend, proto, s_spend, partial)
    except bp.ProtocolError:
        pass
    v_spend = bp.score(spend, proto, s_spend, answers_for(spend, s_spend, 10))
    check("a refused measurement does not consume the single attempt",
          v_spend["matches"] == 10, json.dumps(v_spend)[:160])
    # r6-3: брошенная заявка (процесс умер между созданием файла и записью
    # вердикта) НЕ считается потраченной попыткой: сбой хоста не имеет права
    # отнимать замер. Целый вердикт при этом остаётся неприкосновенным.
    abandoned = project(full_rows(40))
    s_ab = bp.seal(abandoned, proto)
    stale = bp._verdict_path(abandoned, s_ab)
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("", encoding="utf-8")
    got_stray = None
    try:
        bp.score(abandoned, proto, s_ab, answers_for(abandoned, s_ab, 10))
    except bp.ProtocolError as exc:
        got_stray = exc
    check("a stray non-verdict file refuses by name, it is not silently reused",
          got_stray is not None and "посторонний файл" in str(got_stray),
          repr(got_stray)[:160])
    stale.unlink()
    v_ab = bp.score(abandoned, proto, s_ab, answers_for(abandoned, s_ab, 10))
    check("with the stray file gone the attempt is available",
          v_ab["matches"] == 10, json.dumps(v_ab)[:120])
    refused_done = None
    try:
        bp.score(abandoned, proto, bp.seal(abandoned, proto),
                 answers_for(abandoned, s_ab, 10))
    except bp.ProtocolError as exc:
        refused_done = exc
    check("a complete verdict still spends the attempt",
          refused_done is not None and "уже вынесен" in str(refused_done),
          repr(refused_done)[:140])
    # Вердикт публикуется АТОМАРНО: полуфабриката по целевому имени не бывает,
    # поэтому неудачный замер не может съесть попытку.
    watch = project(full_rows(40))
    s_watch = bp.seal(watch, proto)
    trace = []
    real_link = os.link
    real_fsync = os.fsync

    def watching_fsync(fd):
        # Записывается ИМЕННО тот inode, который синхронизировали: иначе
        # реализация могла бы синхронизировать посторонний дескриптор,
        # оставить источник вердикта несинхронизированным и всё равно пройти.
        try:
            ino = os.fstat(fd).st_ino
        except OSError:
            ino = None
        trace.append(("fsync", ino))
        return real_fsync(fd)

    def watching_link(src, dst):
        # Содержимое ИСТОЧНИКА читается в момент публикации: без этого тест
        # проходил бы и на реализации, которая связывает недописанный inode и
        # дописывает его после — а именно это и запрещено требованием.
        try:
            payload_at_link = json.loads(Path(src).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload_at_link = None
        try:
            src_ino = os.stat(src).st_ino
        except OSError:
            src_ino = None
        trace.append(("link", payload_at_link, Path(dst).exists(), src_ino))
        return real_link(src, dst)

    os.link = watching_link
    os.fsync = watching_fsync
    try:
        bp.score(watch, proto, s_watch, answers_for(watch, s_watch, 10))
    finally:
        os.link = real_link
        os.fsync = real_fsync
    links = [e for e in trace if e[0] == "link"]
    published = bp._verdict_path(watch, s_watch)
    check("the source inode is already a complete verdict at publication time",
          len(links) == 1 and isinstance(links[0][1], dict)
          and links[0][1].get("verdict") == "PASSED"
          and links[0][1] == json.loads(published.read_text(encoding="utf-8")),
          str(links)[:200])
    check("the destination never exists before publication",
          len(links) == 1 and links[0][2] is False, str(links)[:120])
    src_ino = links[0][3] if links else None
    synced_before = [e[1] for e in trace[:trace.index(links[0])]
                     if e[0] == "fsync"] if links else []
    # r58: КАТАЛОГ синхронизируется после связывания. Содержимое вердикта
    # ложилось на диск, а запись каталога — нет: крах системы терял бы уже
    # вынесенный вердикт при вернувшемся успехе, и единственная попытка
    # открывалась бы заново.
    synced_dirs = []
    real_sync = bp._sync_directory

    def watching_sync(directory):
        synced_dirs.append((str(directory), real_vpath(watch, s_watch).exists()))
        return real_sync(directory)

    dir_root = project(full_rows(40))
    s_dir = bp.seal(dir_root, proto)
    dir_answers = answers_for(dir_root, s_dir, 10)
    calls = []
    real_link2 = os.link

    def tracking_link(src, dst):
        calls.append(("link", str(Path(dst).parent)))
        return real_link2(src, dst)

    def tracking_sync(directory):
        calls.append(("sync", str(directory)))
        return real_sync(directory)

    os.link = tracking_link
    bp._sync_directory = tracking_sync
    try:
        bp.score(dir_root, proto, s_dir, dir_answers)
    finally:
        os.link = real_link2
        bp._sync_directory = real_sync
    kinds = [c[0] for c in calls]
    check("the verdict directory is synced right after the link",
          kinds == ["link", "sync"] and calls[0][1] == calls[1][1],
          str(calls))
    if bp.DIRECTORY_SYNC_SUPPORTED:
        # И синхронизация действительно выполняется, а не только вызывается.
        probe = project(full_rows(1))
        real_sync(probe / ".itd-memory")
        check("the directory sync really runs on this platform", True)
    else:
        check("the platform without directory sync is named, not skipped",
              any("Windows" in x for x in
                  json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                             .read_text(encoding="utf-8"))["limitations"]))

    # r59: отказ синхронизации каталога НЕ отменяет уже опубликованный
    # вердикт и не тратит попытку. Внутри обработчика ссылки он превращался в
    # ложный отказ «нет жёстких ссылок» при лежащем на диске вердикте.
    sf_root = project(full_rows(40))
    s_sf = bp.seal(sf_root, proto)
    sf_answers = answers_for(sf_root, s_sf, 10)
    real_sd = bp._sync_directory

    def failing_sync(directory):
        raise OSError("directory sync refused (simulated)")

    bp._sync_directory = failing_sync
    got_sf = None
    try:
        v_sf = bp.score(sf_root, proto, s_sf, sf_answers)
    except bp.ProtocolError as exc:
        got_sf = exc
        v_sf = None
    finally:
        bp._sync_directory = real_sd
    check("a refused directory sync neither fails the score nor loses the verdict",
          got_sf is None and v_sf is not None and v_sf["matches"] == 10
          and bp._verdict_path(sf_root, s_sf).exists(),
          repr(got_sf)[:160])
    # И попытка при этом ПОТРАЧЕНА ровно один раз: вердикт вынесен.
    spent_sf = None
    try:
        bp.score(sf_root, proto, s_sf, sf_answers)
    except bp.ProtocolError as exc:
        spent_sf = exc
    check("the published verdict still spends the single attempt",
          spent_sf is not None and "уже вынесен" in str(spent_sf),
          repr(spent_sf)[:140])

    check("the published inode itself was fsynced before publication",
          src_ino is not None and src_ino in synced_before,
          "src=%r synced=%r" % (src_ino, synced_before))
    # Атомарность не имеет права ТИХО понижаться: файловая система без
    # жёстких ссылок обязана дать названный отказ, а не прямую запись.
    nolink = project(full_rows(40))
    s_nolink = bp.seal(nolink, proto)

    def refusing_link(src, dst):
        raise OSError("hard links unsupported (simulated)")

    os.link = refusing_link
    got_nolink = None
    try:
        bp.score(nolink, proto, s_nolink, answers_for(nolink, s_nolink, 10))
    except bp.ProtocolError as exc:
        got_nolink = exc
    finally:
        os.link = real_link
    check("a filesystem without hard links refuses instead of downgrading",
          got_nolink is not None and "атомарную публикацию" in str(got_nolink)
          and not bp._verdict_path(nolink, s_nolink).exists(),
          repr(got_nolink)[:160])

    # r38-2: печать fail-closed и на валидных JSON-повреждениях, которые
    # раньше уходили мимо ProtocolError отдельными исключениями.
    fc_root = project(full_rows(40))
    s_fc = bp.seal(fc_root, proto)
    fc_answers = {"item-%02d" % (n + 1): "correctness" for n in range(10)}
    for label, mutate, needle in [
            ("non-string ref in the population",
             lambda d: d["population"][0].__setitem__("ref", ["a"]),
             "повреждена"),
            # Дайджест пересчитывается: иначе сработал бы страж дайджеста, и
            # проверка ничего не сказала бы о защите от короткой популяции.
            ("population shorter than the sample",
             lambda d: (d.__setitem__("population", d["population"][:3]),
                        d.__setitem__("populationDigest",
                                      bp._digest(d["population"])),
                        d.__setitem__("populationSize", 3)),
             "меньше размера выборки"),
            ("missing protocolDigest", lambda d: d.pop("protocolDigest"),
             "protocolDigest"),
            ("missing sealedAt", lambda d: d.pop("sealedAt"), "sealedAt")]:
        forged_fc = json.loads(json.dumps(s_fc))
        mutate(forged_fc)
        got_w = got_s = None
        try:
            bp.worksheet(fc_root, proto, forged_fc)
        except bp.ProtocolError as exc:
            got_w = exc
        try:
            bp.score(fc_root, proto, forged_fc, fc_answers)
        except bp.ProtocolError as exc:
            got_s = exc
        check("a corrupted seal refuses by name, not by exception: %s" % label,
              got_w is not None and got_s is not None
              and needle in str(got_s), "sheet=%r score=%r" % (got_w, got_s))

    # r38-3: попытка ключуется ПОЛНЫМ дайджестом печати. Префикс seed давал
    # общее пространство имён, и чужая популяция наследовала бы потраченную
    # попытку.
    a_root = project(full_rows(40))
    b_root = project(full_rows(41))
    s_a, s_b = bp.seal(a_root, proto), bp.seal(b_root, proto)
    # r44: метка времени печати не входит в привязку — и это заявлено прямо,
    # а не выдаётся за часть личности. Привязать её нельзя: тогда повторная
    # печать неизменной популяции получала бы новое имя, и попытку можно было
    # бы переиграть пересдачей. Взамен её форма проверяется, а вердикт
    # помечает её как неаутентифицированную.
    ts_root = project(full_rows(40))
    s_ts = bp.seal(ts_root, proto)
    moved = json.loads(json.dumps(s_ts))
    moved["sealedAt"] = "1999-01-01T00:00:00+00:00"
    check("the timestamp is outside the verdict identity, by design",
          bp._verdict_path(ts_root, moved).name
          == bp._verdict_path(ts_root, s_ts).name)
    v_ts = bp.score(ts_root, proto, s_ts, answers_for(ts_root, s_ts, 10))
    check("the verdict says plainly that the timestamp is not authenticated",
          v_ts["sealedAtAuthenticated"] is False, json.dumps(v_ts)[:120])
    for bad_ts in (7, None, [], "не-время", ""):
        forged_ts = json.loads(json.dumps(s_ts))
        forged_ts["sealedAt"] = bad_ts
        got_ts = None
        try:
            bp.worksheet(ts_root, proto, forged_ts)
        except bp.ProtocolError as exc:
            got_ts = exc
        check("a malformed sealedAt refuses by name: %r" % (bad_ts,),
              got_ts is not None and "sealedAt" in str(got_ts),
              repr(got_ts)[:120])

    check("two different populations never share a verdict name",
          bp._verdict_path(a_root, s_a).name != bp._verdict_path(b_root, s_b).name,
          bp._verdict_path(a_root, s_a).name)
    shared_prefix = json.loads(json.dumps(s_a))
    shared_prefix["populationDigest"] = "0" * 64
    check("the verdict name changes when the sealed population changes",
          bp._verdict_path(a_root, shared_prefix).name
          != bp._verdict_path(a_root, s_a).name)

    # r47: популяция пересверяется НЕПОСРЕДСТВЕННО перед публикацией. Между
    # первой сверкой и записью проходят проверка ответов и сборка вердикта;
    # дозапись в леджер в этом промежутке иначе дала бы вердикт, привязанный
    # к уже неактуальной популяции. Чтобы проверить ИМЕННО пересверку, а не
    # первую сверку, дозапись делается внутри окна: подменяется вызов,
    # который случается после проверки ответов и до публикации.
    late_root = project(full_rows(40))
    s_late = bp.seal(late_root, proto)
    late_answers = answers_for(late_root, s_late, 10)
    real_vpath = bp._verdict_path
    fired = {"n": 0}

    def appending_vpath(root_arg, sealed_arg):
        if fired["n"] == 0:
            fired["n"] = 1
            with (late_root / ".itd-memory" / "review-findings.jsonl").open(
                    "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record("late-1", "security"),
                                    ensure_ascii=False) + "\n")
        return real_vpath(root_arg, sealed_arg)

    bp._verdict_path = appending_vpath
    got_late = None
    try:
        bp.score(late_root, proto, s_late, late_answers)
    except bp.ProtocolError as exc:
        got_late = exc
    finally:
        bp._verdict_path = real_vpath
    check("a ledger appended inside the scoring window refuses before publication",
          fired["n"] == 1 and got_late is not None
          and "Окно замера" in str(got_late)
          and not real_vpath(late_root, s_late).exists(),
          repr(got_late)[:180])

    # r51: окно между финальной сверкой и публикацией закрыто ОБЩЕЙ
    # блокировкой писателей леджера, а не обещанием. Проверяется тем, что
    # скоринг реально ждёт держателя этой блокировки: обещание ждать не
    # заставило бы.
    import subprocess
    lockroot = project(full_rows(40))
    s_lock = bp.seal(lockroot, proto)
    lock_answers = answers_for(lockroot, s_lock, 10)
    marker = lockroot / "held.marker"
    release = lockroot / "release.marker"
    # Двусторонняя синхронизация вместо стенных часов: держатель ждёт СИГНАЛА
    # от скорера, а не спит фиксированное время. Со сном планировщик мог
    # выпустить его раньше, чем скорер стартовал, и проверка падала бы даже
    # на корректной реализации.
    holder = (
        "import os, sys, time\n"
        "sys.path.insert(0, %r)\n"
        "from pathlib import Path\n"
        "import itd_verdict_taxonomy as t\n"
        "fd = t._acquire_ledger_lock(Path(%r))\n"
        "open(%r, 'w').close()\n"
        "deadline = time.time() + 60\n"
        "while not os.path.exists(%r) and time.time() < deadline:\n"
        "    time.sleep(0.005)\n"
        "t._release_ledger_lock(fd)\n"
        % (str(ROOT / "skills" / "_shared"),
           str(lockroot / ".itd-memory" / "review-findings.jsonl"),
           str(marker), str(release)))
    hp = subprocess.Popen([PY, "-c", holder])
    until = time.time() + 30
    while not marker.exists() and time.time() < until:
        time.sleep(0.005)
    real_acq = bp._acquire_ledger_lock
    reached = {"n": 0}

    def signalling_acquire(root_arg, protocol_arg):
        # r5: контенция измеряется, а не предполагается. Реальный захват
        # стартует в потоке, ПОКА держатель ещё держит блокировку: поток обязан
        # остаться заблокированным; только потом держателя отпускают, и захват
        # завершается. Скорер с другой (или неработающей) блокировкой прошёл бы
        # мгновенно — и тест покраснел бы.
        import threading
        reached["n"] += 1
        box = {}
        worker = threading.Thread(
            target=lambda: box.__setitem__("lock", real_acq(root_arg, protocol_arg)))
        worker.start()
        worker.join(0.7)
        reached["blocked"] = worker.is_alive()
        release.write_text("", encoding="utf-8")
        worker.join(30)
        return box["lock"]

    bp._acquire_ledger_lock = signalling_acquire
    try:
        v_lock = bp.score(lockroot, proto, s_lock, lock_answers)
    finally:
        bp._acquire_ledger_lock = real_acq
    hp.wait(timeout=60)
    check("scoring contends for the ledger writers' own lock before publishing",
          marker.exists() and reached["n"] == 1 and reached.get("blocked") is True
          and v_lock["matches"] == 10,
          "reached=%d blocked=%r" % (reached["n"], reached.get("blocked")))

    # r51: целочисленные поля контракта сравниваются с проверкой ТИПА.
    for field, value in [("protocol_version", True), ("protocol_version", 1.0)]:
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        doc[field] = value
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got_i = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            got_i = exc
        check("%s=%r is not accepted as the integer 1" % (field, value),
              got_i is not None, repr(got_i)[:120])
    for block, field, value in [("attempts", "perSeal", True),
                                ("attempts", "perSeal", 1.0)]:
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        doc[block][field] = value
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got_i = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            got_i = exc
        check("%s.%s=%r is not accepted as the integer 1" % (block, field, value),
              got_i is not None, repr(got_i)[:120])

    # r51: нехешируемая ссылка позиции отказывает по имени, а не роняет.
    uh_root = project(full_rows(40))
    s_uh = bp.seal(uh_root, proto)
    forged_uh = json.loads(json.dumps(s_uh))
    forged_uh["items"][0]["ref"] = []
    got_uh = None
    try:
        bp.score(uh_root, proto, forged_uh,
                 {"item-%02d" % (n + 1): "correctness" for n in range(10)})
    except bp.ProtocolError as exc:
        got_uh = exc
    check("an unhashable item ref refuses by name, not by TypeError",
          got_uh is not None and "непустыми строками" in str(got_uh),
          repr(got_uh)[:140])

    # r6-1: не-объект в листе ответов отказывает названно, а не роняет.
    for bad_answers in (None, 5, ["correctness"], "correctness"):
        s_bad = bp.seal(spend, proto)
        got = None
        try:
            bp.score(spend, proto, s_bad, bad_answers)
        except bp.ProtocolError as exc:
            got = exc
        check("a non-object answer sheet refuses by name: %s"
              % type(bad_answers).__name__,
              got is not None and "объектом" in str(got), repr(got)[:140])

    # r6-2: повреждённая печать отказывает и на листе, и на скоринге —
    # трейсбек вместо отказа заставил бы разметчика узнать о правке только
    # после всей ручной работы.
    # Каждая мутация печати проверяется на СВЕЖЕЙ непотраченной печати и по
    # ИМЕНИ причины: на потраченной печати отказ мог бы прийти от «вердикт уже
    # вынесен», и регрессия, проверяющая попытку раньше структуры, прошла бы
    # этот оракул незамеченной.
    for label, mutate, reason in [
            ("item is not a mapping",
             lambda d: d.__setitem__("items", ["oops"] + d["items"][1:]),
             "позиции печати повреждены"),
            ("items missing", lambda d: d.pop("items"), "items"),
            ("population missing", lambda d: d.pop("population"),
             "population")]:
        fresh = project(full_rows(40))
        s_mal = bp.seal(fresh, proto)
        broken_seal = json.loads(json.dumps(s_mal))
        mutate(broken_seal)
        got_w = got_s = None
        try:
            bp.worksheet(fresh, proto, broken_seal)
        except bp.ProtocolError as exc:
            got_w = exc
        try:
            bp.score(fresh, proto, broken_seal, answers_for(fresh, s_mal, 10))
        except bp.ProtocolError as exc:
            got_s = exc
        check("a malformed seal refuses structurally on sheet and score: %s"
              % label,
              got_w is not None and got_s is not None
              and reason in str(got_w) and reason in str(got_s),
              "sheet=%r score=%r" % (got_w, got_s))
        check("the malformed-seal refusal is not a spent-attempt refusal: %s"
              % label,
              "уже вынесен" not in str(got_s), repr(got_s)[:140])

    # r10: верхний уровень печати — тоже вход. Валидный JSON-список или
    # строка обязаны дать названный отказ, а не AttributeError.
    for bad_seal in ([], "seal", None, 7):
        got_t = got_t2 = None
        try:
            bp.worksheet(spend, proto, bad_seal)
        except bp.ProtocolError as exc:
            got_t = exc
        try:
            bp.score(spend, proto, bad_seal, answers_for(spend, s_spend, 10))
        except bp.ProtocolError as exc:
            got_t2 = exc
        check("a non-object seal refuses by name: %s" % type(bad_seal).__name__,
              got_t is not None and got_t2 is not None
              and "объектом" in str(got_t), repr(got_t)[:140])

    # r10: метка автора вне словаря источника — испорченный вход, а не
    # несогласие: разметчик выбирает только из словаря, поэтому совпадение
    # недостижимо, и такая находка занижала бы согласие, ничего не измеряя.
    tainted = project(full_rows(12) + [record("bad-1", "не-из-словаря"),
                                       record("bad-2", "operator-only")])
    tpool = bp.eligible(tainted, proto)
    check("an out-of-vocabulary author label is outside the population",
          {"bad-1#0", "bad-2#0"}.isdisjoint({i["ref"] for i in tpool})
          and len(tpool) == 12, str(sorted(i["ref"] for i in tpool))[-120:])

    # r14-1: seed не выбирается, а ВЫВОДИТСЯ из протокола и популяции.
    # Свободный seed оставлял оператору решающую степень свободы: перебирая
    # значения, можно намолотить удобную выборку и предъявить её случайной.
    import inspect
    check("seal takes no operator-chosen seed at all",
          "seed" not in inspect.signature(bp.seal).parameters,
          str(inspect.signature(bp.seal)))
    same_a = project(full_rows(40))
    same_b = project(full_rows(40))
    sa, sb = bp.seal(same_a, proto), bp.seal(same_b, proto)
    check("the same population always derives the same seed and sample",
          sa["seed"] == sb["seed"]
          and [i["ref"] for i in sa["items"]] == [i["ref"] for i in sb["items"]],
          "%s vs %s" % (sa["seed"][:12], sb["seed"][:12]))
    other = project(full_rows(41))
    so = bp.seal(other, proto)
    check("a different population derives a different seed",
          so["seed"] != sa["seed"], "%s vs %s" % (so["seed"][:12], sa["seed"][:12]))
    # Подставленный seed отказывает даже с пересчитанными под него позициями:
    # именно так выглядела бы намолоченная выборка.
    ground = json.loads(json.dumps(sa))
    ground["seed"] = "0" * len(sa["seed"])
    redrawn = bp._draw(ground["population"], 10, ground["seed"])
    ground["items"] = [{"id": "item-%02d" % (n + 1), "ref": e["ref"],
                        "digest": e["digest"]} for n, e in enumerate(redrawn)]
    got_ground = None
    try:
        bp.score(same_a, proto, ground,
                 {"item-%02d" % (n + 1): "correctness" for n in range(10)})
    except bp.ProtocolError as exc:
        got_ground = exc
    check("a ground seed with matching items is still refused",
          got_ground is not None and "не выводится" in str(got_ground),
          repr(got_ground)[:160])

    # r14-3: повтор ссылки в популяции отказывает, а не выбирается наугад.
    dup = record("dup-1", "correctness")
    dupes = project(full_rows(12) + [dup, json.loads(json.dumps(dup))])
    got_dup = None
    try:
        bp.eligible(dupes, proto)
    except bp.ProtocolError as exc:
        got_dup = exc
    check("a duplicated lineage refuses the population by name",
          got_dup is not None and "повторяется ссылка" in str(got_dup),
          repr(got_dup)[:160])

    # Контракт повтора обязан описывать РЕАЛЬНОСТЬ: повторная печать
    # неизменённой популяции воспроизводит ту же выборку и упирается в тот же
    # вынесенный вердикт — переиграть замер пересдачей нельзя. Новая попытка
    # появляется только вместе с новыми находками.
    retry = project(full_rows(40))
    s_r1 = bp.seal(retry, proto)
    bp.score(retry, proto, s_r1, answers_for(retry, s_r1, 10))
    s_r2 = bp.seal(retry, proto)
    got_retry = None
    try:
        bp.score(retry, proto, s_r2, answers_for(retry, s_r2, 10))
    except bp.ProtocolError as exc:
        got_retry = exc
    check("resealing an unchanged population reproduces the spent seal",
          s_r2["seed"] == s_r1["seed"]
          and [i["ref"] for i in s_r2["items"]] == [i["ref"] for i in s_r1["items"]]
          and got_retry is not None and "уже вынесен" in str(got_retry),
          repr(got_retry)[:160])
    with (retry / ".itd-memory" / "review-findings.jsonl").open(
            "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record("fresh-1", "security"), ensure_ascii=False) + "\n")
    s_r3 = bp.seal(retry, proto)
    v_r3 = bp.score(retry, proto, s_r3, answers_for(retry, s_r3, 10))
    check("a grown population earns a genuinely new attempt",
          s_r3["seed"] != s_r1["seed"] and v_r3["matches"] == 10,
          "%s vs %s" % (s_r3["seed"][:10], s_r1["seed"][:10]))

    # r14-2: onFail обязан быть строками — вердикт склеивает их в текст, и
    # истинное не-строковое значение падало бы ровно на провальном замере.
    for field in ("action", "then"):
        for bad in (True, 5, ["Q2"], {"a": 1}, "", "   "):
            broken = project(full_rows(1))
            bshared = broken / "skills" / "_shared"
            bshared.mkdir(parents=True)
            doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                             .read_text(encoding="utf-8"))
            doc["onFail"][field] = bad
            (bshared / "BLIND_PROTOCOL.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            got_of = None
            try:
                bp.load_protocol(broken)
            except bp.ProtocolError as exc:
                got_of = exc
            check("onFail.%s=%r refuses the protocol" % (field, bad),
                  got_of is not None and "строками" in str(got_of),
                  repr(got_of)[:120])

    # r19-3: поля-ПАРАМЕТРЫ (размер выборки, порог, требования популяции,
    # набор источников) не отвергаются — они настраиваемы. Но контракт обязан
    # их реально ИСПОЛНЯТЬ: молча игнорировать объявленное значение — тот же
    # docs-vs-code, что и расхождение семантики. Проверяется поведением.
    def with_contract(rows, **patch):
        root = project(rows)
        shared = root / "skills" / "_shared"
        shared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        for dotted, value in patch.items():
            block, _, field = dotted.partition(".")
            if field:
                doc[block][field] = value
            else:
                doc[block] = value
        (shared / "VERDICT_TAXONOMY.json").write_text(
            (ROOT / "skills" / "_shared" / "VERDICT_TAXONOMY.json").read_text(
                encoding="utf-8"), encoding="utf-8")
        (shared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return root, bp.load_protocol(root)

    small_root, small_proto = with_contract(
        full_rows(40), **{"sample.size": 5, "scoring.outOf": 5,
                          "scoring.threshold": 3})
    s_small = bp.seal(small_root, small_proto)
    check("a declared sample size really changes how many are drawn",
          len(s_small["items"]) == 5, str(len(s_small["items"])))
    pool_small = {i["ref"]: i for i in bp.eligible(small_root, small_proto)}
    ans_small = {}
    for n, it in enumerate(s_small["items"]):
        true = pool_small[it["ref"]]["category"]
        ans_small[it["id"]] = true if n < 3 else next(c for c in CATS if c != true)
    v_small = bp.score(small_root, small_proto, s_small, ans_small)
    check("a declared threshold really decides the verdict",
          v_small["matches"] == 3 and v_small["threshold"] == 3
          and v_small["verdict"] == "PASSED", json.dumps(v_small)[:140])

    legacy_root, legacy_proto = with_contract(
        [record("n-%d" % i, CATS[i % len(CATS)]) for i in range(11)]
        + [record("old-1", "correctness", stamped=False)],
        **{"population.requireTaxonomyVersion": False})
    check("a declared population requirement really admits what it allows",
          "old-1#0" in {i["ref"] for i in bp.eligible(legacy_root, legacy_proto)},
          str(sorted(i["ref"] for i in bp.eligible(legacy_root, legacy_proto)))[-90:])

    ext_root, ext_proto = with_contract(
        [record("e-%d" % i, "correctness", source="external-github-review")
         for i in range(11)] + [record("own-1", "correctness")],
        **{"population.sourceIn": ["external-github-review"]})
    ext_refs = {i["ref"] for i in bp.eligible(ext_root, ext_proto)}
    check("a declared source selection really decides the population",
          "own-1#0" not in ext_refs and len(ext_refs) == 11, str(len(ext_refs)))

    # r53: под блокировкой протокол и словарь перечитываются С ДИСКА. Снимок
    # даёт согласованность внутри фазы, но слепнет к подмене файла в окне
    # замера; отличить «читаю одно и то же» от «читаю то же, что в печати»
    # можно только переизданием и сверкой дайджестов.
    for label, target, mutate in [
            ("protocol", "BLIND_PROTOCOL.json",
             lambda d: (d["sample"].__setitem__("size", 9),
                        d["scoring"].__setitem__("outOf", 9),
                        d["scoring"].__setitem__("threshold", 7))),
            ("taxonomy", "VERDICT_TAXONOMY.json",
             lambda d: d["category"]["meaning"].__setitem__(
                 "correctness", "подменено"))]:
        sub_root, sub_proto = with_contract(full_rows(40))
        s_sub = bp.seal(sub_root, sub_proto)
        sub_answers = answers_for(sub_root, s_sub, 10)
        target_file = sub_root / "skills" / "_shared" / target
        real_vp = bp._verdict_path
        swapped = {"n": 0}

        def swapping_vpath(root_arg, sealed_arg, _f=target_file, _m=mutate,
                           _s=swapped):
            if _s["n"] == 0:
                _s["n"] = 1
                doc = json.loads(_f.read_text(encoding="utf-8"))
                _m(doc)
                _f.write_text(json.dumps(doc, ensure_ascii=False),
                              encoding="utf-8")
            return real_vp(root_arg, sealed_arg)

        bp._verdict_path = swapping_vpath
        got_sub = None
        try:
            bp.score(sub_root, sub_proto, s_sub, sub_answers)
        except bp.ProtocolError as exc:
            got_sub = exc
        finally:
            bp._verdict_path = real_vp
        check("a %s swapped inside the window refuses before publication"
              % label,
              swapped["n"] == 1 and got_sub is not None
              and "изменил" in str(got_sub)
              and not real_vp(sub_root, s_sub).exists(),
              repr(got_sub)[:160])

    # r62: вложенные контейнеры словаря — тоже вход.
    for label, doc in [("category is a list", {"category": []}),
                       ("meaning is a list", {"category": {"meaning": []}}),
                       ("bySource is a list",
                        {"category": {"meaning": {}, "bySource": []}})]:
        nt_root, nt_proto = with_contract(full_rows(12))
        (nt_root / "skills" / "_shared" / "VERDICT_TAXONOMY.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got_nt = None
        try:
            bp.eligible(nt_root, nt_proto)
        except bp.ProtocolError as exc:
            got_nt = exc
        check("a corrupted taxonomy container refuses by name: %s" % label,
              got_nt is not None and "повреждён" in str(got_nt),
              repr(got_nt)[:120])

    # r65: ЛИСТ тоже сверяет дайджест протокола. Он строится ПО протоколу
    # (видимые поля, честная маркировка), поэтому без сверки собирался бы по
    # новому, но нёс дайджест старого — ложно приписываясь запечатанному.
    wd_root, wd_proto = with_contract(full_rows(40))
    s_wd = bp.seal(wd_root, wd_proto)
    changed = json.loads(json.dumps(wd_proto))
    changed["honestMarking"] = changed["honestMarking"] + " (подменено)"
    got_wd = None
    try:
        bp.worksheet(wd_root, changed, s_wd)
    except bp.ProtocolError as exc:
        got_wd = exc
    check("the worksheet refuses a protocol that changed after the seal",
          got_wd is not None and "протокол изменился" in str(got_wd),
          repr(got_wd)[:140])

    # r65: ключи листа ответов приводятся к строкам ДО склейки в текст отказа.
    mk_root = project(full_rows(40))
    s_mk = bp.seal(mk_root, proto)
    mixed = answers_for(mk_root, s_mk, 10)
    mixed[7] = "correctness"
    mixed[("t",)] = "correctness"
    got_mk = None
    try:
        bp.score(mk_root, proto, s_mk, mixed)
    except bp.ProtocolError as exc:
        got_mk = exc
    check("mixed-type extra answer keys refuse by name, not by TypeError",
          got_mk is not None and "вне печати" in str(got_mk),
          repr(got_mk)[:140])

    # r19-1: ИСТОЧНИК записи входит в личность позиции. Он решает, каким
    # словарём размечается позиция, поэтому смена источника на другой, где та
    # же категория тоже допустима, молча меняла бы предмет замера уже после
    # печати. Проверять это можно только на контракте, где ОБА источника
    # допустимы: иначе запись просто выпадает из популяции, и отказ приходит
    # по другой причине, ничего не говоря о дайджесте.
    both_root, both_proto = with_contract(
        [record("s-%d" % i, "correctness") for i in range(12)],
        **{"population.sourceIn": ["subagent-verdict",
                                   "external-github-review"]})
    s_both = bp.seal(both_root, both_proto)
    both_ledger = both_root / ".itd-memory" / "review-findings.jsonl"
    target_line = s_both["items"][0]["ref"].split("#")[0]
    rows_both = []
    for ln in both_ledger.read_text(encoding="utf-8").splitlines():
        row = json.loads(ln)
        if row.get("lineage") == target_line:
            row["source"] = "external-github-review"
        rows_both.append(json.dumps(row, ensure_ascii=False))
    both_ledger.write_text("\n".join(rows_both) + "\n", encoding="utf-8")
    still_in = {i["ref"] for i in bp.eligible(both_root, both_proto)}
    got_src = None
    try:
        bp.score(both_root, both_proto, s_both,
                 {"item-%02d" % (n + 1): "correctness" for n in range(10)})
    except bp.ProtocolError as exc:
        got_src = exc
    # r23-1: СЛОВАРЬ тоже определяет замер — он решает, какие значения
    # предлагаются разметчику и принимаются на скоринге. Его правка внутри
    # открытого окна меняла бы правила, не задев ни одной другой привязки.
    tax_root, tax_proto = with_contract(full_rows(40))
    s_tax = bp.seal(tax_root, tax_proto)
    tax_file = tax_root / "skills" / "_shared" / "VERDICT_TAXONOMY.json"
    tdoc = json.loads(tax_file.read_text(encoding="utf-8"))
    tdoc["category"]["meaning"]["correctness"] = "Переписанное описание."
    tax_file.write_text(json.dumps(tdoc, ensure_ascii=False), encoding="utf-8")
    got_tax_w = got_tax_s = None
    try:
        bp.worksheet(tax_root, tax_proto, s_tax)
    except bp.ProtocolError as exc:
        got_tax_w = exc
    try:
        bp.score(tax_root, tax_proto, s_tax,
                 {"item-%02d" % (n + 1): "correctness" for n in range(10)})
    except bp.ProtocolError as exc:
        got_tax_s = exc
    # r38-1: словарь читается ОДНИМ снимком на весь замер. Перечитывание на
    # каждом обращении оставляло окно между проверкой дайджеста и
    # использованием: подмена между чтениями смешивала версии в одной
    # популяции или меняла словарь позиции уже после приёмки его дайджеста.
    import inspect
    check("the population and the vocabulary accept an injected snapshot",
          "taxonomy" in inspect.signature(bp.eligible).parameters
          and "taxonomy" in inspect.signature(bp._vocabulary).parameters,
          "%s | %s" % (inspect.signature(bp.eligible),
                       inspect.signature(bp._vocabulary)))
    snap_root, snap_proto = with_contract(full_rows(40))
    reads = {"n": 0}
    real_loader = bp._load_taxonomy

    def counting_loader(root):
        reads["n"] += 1
        return real_loader(root)

    # Ответы считаются ДО установки счётчика: хелпер сам обращается к
    # популяции, и его загрузки исказили бы замер фаз.
    snap_answers_seed = bp.seal(snap_root, snap_proto)
    snap_answers = answers_for(snap_root, snap_answers_seed, 10)
    bp._load_taxonomy = counting_loader
    try:
        reads["n"] = 0
        s_snap = bp.seal(snap_root, snap_proto)
        seal_reads = reads["n"]
        reads["n"] = 0
        bp.worksheet(snap_root, snap_proto, s_snap)
        sheet_reads = reads["n"]
        # СКОРИНГ тоже под счётчиком: без него реализация, перечитывающая
        # словарь уже после приёмки его дайджеста, снова открывала бы то
        # самое окно и проходила бы этот оракул.
        reads["n"] = 0
        bp.score(snap_root, snap_proto, s_snap, snap_answers)
        score_reads = reads["n"]
    finally:
        bp._load_taxonomy = real_loader
    # Печать и лист читают словарь ровно один раз — это согласованность фазы.
    # Скоринг читает ДВАЖДЫ, и это намеренно: снимок фазы плюс переиздание с
    # диска под блокировкой, которым и ловится подмена внутри окна замера.
    # Снимок без переиздания слеп к подмене, переиздание без снимка мешало бы
    # версии внутри одной фазы.
    check("phases read the taxonomy exactly as the design requires",
          seal_reads == 1 and sheet_reads == 1 and score_reads == 2,
          "seal=%d sheet=%d score=%d" % (seal_reads, sheet_reads, score_reads))

    # Повреждённый словарь — тоже вход: список, число или null обязаны дать
    # названный отказ, а не AttributeError у первого же `.get`.
    for bad_tax in ([], 7, None, "vocab"):
        bt_root, bt_proto = with_contract(full_rows(12))
        (bt_root / "skills" / "_shared" / "VERDICT_TAXONOMY.json").write_text(
            json.dumps(bad_tax, ensure_ascii=False), encoding="utf-8")
        got_bt = None
        try:
            bp.eligible(bt_root, bt_proto)
        except bp.ProtocolError as exc:
            got_bt = exc
        check("a non-object taxonomy refuses by name: %s"
              % type(bad_tax).__name__,
              got_bt is not None and "обязан быть объектом" in str(got_bt),
              repr(got_bt)[:120])
    # И нестроковые значения в словаре источника — до их склейки в текст.
    ns_root, ns_proto = with_contract(full_rows(12))
    ns_file = ns_root / "skills" / "_shared" / "VERDICT_TAXONOMY.json"
    ns_doc = json.loads(ns_file.read_text(encoding="utf-8"))
    ns_doc["category"]["bySource"]["subagent-verdict"] = ["correctness", 7, None]
    ns_file.write_text(json.dumps(ns_doc, ensure_ascii=False), encoding="utf-8")
    got_ns = None
    try:
        bp.eligible(ns_root, ns_proto)
    except bp.ProtocolError as exc:
        got_ns = exc
    check("non-string vocabulary values refuse before they are joined",
          got_ns is not None and "нестроковые" in str(got_ns), repr(got_ns)[:120])

    check("a taxonomy edited after the seal refuses both sheet and score",
          got_tax_w is not None and got_tax_s is not None
          and "словарь вердикта изменился" in str(got_tax_s),
          "sheet=%r score=%r" % (got_tax_w, got_tax_s))

    # r23-2: испорченная строка леджера с нехешируемым источником обязана
    # пропускаться, а не ронять TypeError мимо всех обработчиков.
    ugly = project(full_rows(12))
    with (ugly / ".itd-memory" / "review-findings.jsonl").open(
            "a", encoding="utf-8") as fh:
        for weird in ([{"a": 1}], {"nested": True}, 7, None):
            fh.write(json.dumps({"source": weird, "lineage": "weird",
                                 "taxonomy_version": 1,
                                 "findings": [{"category": "correctness",
                                               "summary": "x"}]},
                                ensure_ascii=False) + "\n")
    ugly_pool = None
    ugly_exc = None
    try:
        ugly_pool = bp.eligible(ugly, proto)
    except Exception as exc:  # noqa: BLE001
        ugly_exc = exc
    check("an unhashable source in a ledger row is skipped, not a traceback",
          ugly_exc is None and ugly_pool is not None and len(ugly_pool) == 12,
          repr(ugly_exc)[:140] if ugly_exc else str(len(ugly_pool or [])))

    check("a post-seal source change is caught by identity, not by dropout",
          "%s#0" % target_line in still_in and got_src is not None,
          "in_pool=%s exc=%r" % ("%s#0" % target_line in still_in,
                                 str(got_src)[:120]))

    # r28: population.ledger — путь, по которому читается сам предмет замера.
    # Отсутствующий или неверно типизированный он падал бы уже при чтении,
    # мимо машиночитаемого отказа обещанной fail-closed загрузки.
    for bad_ledger in (None, "", "   ", 7, ["a"], {"p": 1}):
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        doc["population"]["ledger"] = bad_ledger
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got_l = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            got_l = exc
        check("population.ledger=%r refuses the protocol" % bad_ledger,
              got_l is not None and "ledger" in str(got_l), repr(got_l)[:120])
    # И отсутствующий ключ целиком.
    broken = project(full_rows(1))
    bshared = broken / "skills" / "_shared"
    bshared.mkdir(parents=True)
    doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                     .read_text(encoding="utf-8"))
    doc["population"].pop("ledger")
    (bshared / "BLIND_PROTOCOL.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    got_l = None
    try:
        bp.load_protocol(broken)
    except bp.ProtocolError as exc:
        got_l = exc
    check("a missing population.ledger refuses the protocol",
          got_l is not None and "ledger" in str(got_l), repr(got_l)[:120])

    # seedBytes не может превышать длину дайджеста: объявленные 64 байта молча
    # дали бы 32, а контракт, который нельзя исполнить как написано, обязан
    # отказать.
    for width in (33, 64, 0, -1):
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                         .read_text(encoding="utf-8"))
        doc["sample"]["seedBytes"] = width
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        got_w2 = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            got_w2 = exc
        check("seedBytes outside the digest length refuses: %d" % width,
              got_w2 is not None and "seedBytes" in str(got_w2),
              repr(got_w2)[:140])

    # r10: верхний уровень печати — тоже вход. Валидный JSON-список или
    # строка обязаны дать названный отказ, а не AttributeError.
    for bad_seal in ([], "seal", None, 7):
        got_t = got_t2 = None
        try:
            bp.worksheet(spend, proto, bad_seal)
        except bp.ProtocolError as exc:
            got_t = exc
        try:
            bp.score(spend, proto, bad_seal, answers_for(spend, s_spend, 10))
        except bp.ProtocolError as exc:
            got_t2 = exc
        check("a non-object seal refuses by name: %s" % type(bad_seal).__name__,
              got_t is not None and got_t2 is not None
              and "объектом" in str(got_t), repr(got_t)[:140])

    # r10: метка автора вне словаря источника — испорченный вход, а не
    # несогласие: разметчик выбирает только из словаря, поэтому совпадение
    # недостижимо, и такая находка занижала бы согласие, ничего не измеряя.
    tainted = project(full_rows(12) + [record("bad-1", "не-из-словаря"),
                                       record("bad-2", "operator-only")])
    tpool = bp.eligible(tainted, proto)
    check("an out-of-vocabulary author label is outside the population",
          {"bad-1#0", "bad-2#0"}.isdisjoint({i["ref"] for i in tpool})
          and len(tpool) == 12, str(sorted(i["ref"] for i in tpool))[-120:])

    # r6-4: явный seed подчиняется тому же seedBytes, что и сгенерированный.
    # r1-4: замороженный контракт валидируется строго. Каждое поле, которое
    # ОПИСЫВАЕТ поведение, обязано отказать загрузку при расхождении — иначе
    # контракт перестаёт описывать то, что исполняется.
    raw = json.loads((ROOT / "skills" / "_shared" / "BLIND_PROTOCOL.json")
                     .read_text(encoding="utf-8"))
    breaks = [
        ("sample.withoutReplacement", ("sample", "withoutReplacement"), False),
        ("sample.rng", ("sample", "rng"), "mersenne"),
        ("sample.seedBytes", ("sample", "seedBytes"), 0),
        ("scoring.rule", ("scoring", "rule"), "fuzzy"),
        ("scoring.outOf", ("scoring", "outOf"), 7),
        ("scoring.missingAnswer", ("scoring", "missingAnswer"), "count-as-miss"),
        ("scoring.answerOutsideVocabulary",
         ("scoring", "answerOutsideVocabulary"), "count-as-miss"),
        ("attempts.perSeal", ("attempts", "perSeal"), 3),
        ("population.requireCategory", ("population", "requireCategory"), "yes"),
        ("worksheet.vocabularyFrom", ("worksheet", "vocabularyFrom"), "values"),
    ]
    for label, (block, field), value in breaks:
        broken = project(full_rows(1))
        bshared = broken / "skills" / "_shared"
        bshared.mkdir(parents=True)
        doc = json.loads(json.dumps(raw))
        doc[block][field] = value
        (bshared / "BLIND_PROTOCOL.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        refused = None
        try:
            bp.load_protocol(broken)
        except bp.ProtocolError as exc:
            refused = exc
        check("a contract contradicting the implementation refuses: %s" % label,
              refused is not None, repr(refused)[:140])

    # CLI: три шага и машиночитаемый ОТКАЗ с ненулевым кодом. Замер, который
    # не состоялся, не имеет права выглядеть пройденным для вызывающего.
    import subprocess
    mod = str(ROOT / "skills" / "_shared" / "itd_blind_protocol.py")
    cli_root = project(full_rows(20))
    r = subprocess.run([sys.executable, mod, "seal", "--root", str(cli_root)],
                       capture_output=True, text=True)
    check("the CLI seals and reports the population it drew from",
          r.returncode == 0 and json.loads(r.stdout)["status"] == "SEALED"
          and json.loads(r.stdout)["populationSize"] == 20, r.stdout[:200])
    r = subprocess.run([sys.executable, mod, "worksheet", "--root", str(cli_root)],
                       capture_output=True, text=True)
    check("the CLI writes a worksheet of exactly the sample size",
          r.returncode == 0 and json.loads(r.stdout)["items"] == 10, r.stdout[:200])
    sheet_file = cli_root / ".itd-memory" / "blind-protocol" / "worksheet.json"
    check("the worksheet on disk leaks no author label",
          '"category"' not in sheet_file.read_text(encoding="utf-8"))
    short_cli = project(full_rows(4))
    r = subprocess.run([sys.executable, mod, "seal", "--root", str(short_cli)],
                       capture_output=True, text=True)
    check("the CLI refuses a short population with a non-zero exit",
          r.returncode != 0 and json.loads(r.stdout)["status"] == "REFUSED"
          and "4" in json.loads(r.stdout)["why"], r.stdout[:200])
    answers_file = cli_root / "answers.json"
    sealed_cli = json.loads((cli_root / ".itd-memory" / "blind-protocol"
                             / "seal.json").read_text(encoding="utf-8"))
    pool_cli = {i["ref"]: i for i in bp.eligible(cli_root, proto)}
    answers_file.write_text(json.dumps(
        {it["id"]: pool_cli[it["ref"]]["category"]
         for it in sealed_cli["items"]}), encoding="utf-8")
    r = subprocess.run([sys.executable, mod, "score", "--root", str(cli_root),
                        "--answers", str(answers_file)],
                       capture_output=True, text=True)
    check("a fully agreeing sheet scores ten of ten and exits zero",
          r.returncode == 0 and json.loads(r.stdout)["matches"] == 10,
          r.stdout[:200])

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        import shutil
        for d in TMPDIRS:
            shutil.rmtree(d, ignore_errors=True)
