#!/usr/bin/env python3
"""Fail-closed чекер замера GENG-C-EXP (N8): фаза 0 + фаза 1.

Перепроверяет из первичных артефактов (промпты серии N7, манифест, файлы
вердиктов), что опубликованные агрегаты — пересчёт, а не заявление:
классы фазы 0 пересчитываются по байтам промптов, метрики фазы 1 — по
вердикт-файлам против ground truth манифеста, порог — по пре-регистрированному
правилу. Любое расхождение — красный. Stdlib-only, детерминированный.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEAS = ROOT / ".itd-memory" / "measurements"
BENCH = ROOT / "benchmarks" / "geng"
VL = ROOT / ".itd-memory" / "verification-loop"

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    print("%s  %s%s" % ("PASS" if cond else "FAIL", name,
                        ("  [%s]" % detail) if detail and not cond else ""))
    if cond:
        passed += 1
    else:
        failed += 1


def main() -> int:
    # Фаза 0 читает промпты серии N7 из .itd-memory/verification-loop/ —
    # они git-ignored и в кандидат не входят, поэтому изолированная машинная
    # нога ПО ПОСТРОЕНИЮ их не видит (ловушка N6: изолят не принимает
    # verification-loop как вход). --phase1-only — изолят-совместимый разрез;
    # полный прогон (обе фазы, включая сверку промптов с пиненными digest'ами)
    # остаётся локальной проверкой и уликой в acceptance-критерии.
    phase1_only = "--phase1-only" in sys.argv[1:]

    # --- фаза 0: пересчёт классов по байтам промптов -------------------------
    p0 = json.loads((MEAS / "GENG-C-EXP-phase0.json").read_text(encoding="utf-8"))
    if phase1_only:
        check("phase0: skipped in isolate mode, prompt digests are pinned in the record",
              all(len(v) == 64 for v in p0["corpus"]["promptSha256"].values()))
        return _phase1(p0)
    prompts = {k: (VL / f"ORACLE-DEBT-r{k}-prompt.md").read_bytes()
               for k in p0["corpus"]["rounds"]}
    for k, blob in prompts.items():
        check(f"phase0: prompt r{k} bytes match the pinned digest",
              hashlib.sha256(blob).hexdigest() == p0["corpus"]["promptSha256"][f"r{k}"])
    check("phase0: all candidate prompts are pairwise distinct",
          len({bytes(v) for v in prompts.values()}) == len(prompts))
    recounted: dict[str, int] = {}
    for row in p0["findings"]:
        k, prev = row["round"], row.get("previousRound")
        if prev is None:
            cls = "BASELINE"
        else:
            hits = [a for a in row["anchors"] if a.encode() in prompts[prev]]
            own = [a for a in row["anchors"] if a.encode() in prompts[k]]
            cls = "PRE" if hits else ("NEW" if own else "UNDECIDABLE")
        check(f"phase0: {row['id']} class recomputes to {row['class']}",
              cls == row["class"], f"recomputed {cls}")
        recounted[cls] = recounted.get(cls, 0) + 1
    check("phase0: published counts equal the recount",
          recounted == p0["counts"], f"recount {recounted}")
    decidable = recounted.get("PRE", 0) + recounted.get("NEW", 0)
    check("phase0: preShareOfDecidable is a recomputation",
          p0["preShareOfDecidable"] == round(recounted.get("PRE", 0) / decidable, 3))
    return _phase1(p0)


def _phase1(p0: dict) -> int:
    # --- фаза 1: пересчёт метрик по вердикт-файлам ---------------------------
    man = json.loads((BENCH / "phase1-manifest.json").read_text(encoding="utf-8"))
    res = json.loads((BENCH / "phase1-results.json").read_text(encoding="utf-8"))
    gt = {c["id"]: c for c in man["candidates"]}
    check("phase1: manifest holds 12 candidates, >=4 per class",
          len(gt) == 12 and all(
              sum(1 for c in gt.values() if c["class"] == cls) >= 4
              for cls in ("clean", "seeded", "reconstructed")))
    # Исключение из метрик — только объявленное: с непустой причиной в
    # манифесте И зеркальной записью в results.excluded (находка чекера r1:
    # C12 invalid excerpt). Молчаливое сужение популяции — красный.
    excluded = {c for c, v in gt.items() if v.get("excludedFromMetrics")}
    check("phase1: every exclusion carries a reason and is mirrored in results",
          all(str(gt[c].get("exclusionReason") or "").strip() for c in excluded)
          and set(res.get("excluded") or {}) == excluded)
    for c in man["candidates"]:
        blob = pathlib.Path(c["file"]).read_bytes()
        check(f"phase1: candidate {c['id']} bytes match the frozen manifest digest",
              hashlib.sha256(blob).hexdigest() == c["sha256"])
    by = {}
    for a in ("A1", "A2", "A3", "A4"):
        rows = json.loads((BENCH / "runs" / f"{a}.json").read_text(encoding="utf-8"))
        check(f"phase1: run {a} verdicts cover exactly the 12 candidates",
              {r["id"] for r in rows} == set(gt)
              and all(r["verdict"] in ("PASSED", "BLOCKED") for r in rows))
        by[a] = {r["id"]: r["verdict"] for r in rows}
    check("phase1: published verdict matrix equals the run files",
          res["verdictMatrix"] == {c: {a: by[a][c] for a in by} for c in sorted(gt)})
    valid = [c for c in sorted(gt) if c not in excluded]
    defective = [c for c in valid if gt[c]["defectPresent"]]
    clean = [c for c in valid if not gt[c]["defectPresent"]]
    fp_ctrl = sum(1 for c in defective if by["A1"][c] != "BLOCKED") / len(defective)
    fp_q = sum(1 for c in defective
               if sum(by[a][c] == "BLOCKED" for a in ("A2", "A3", "A4")) < 2
               ) / len(defective)
    noise = sum(1 for a in by for c in clean if by[a][c] == "BLOCKED")
    unanimous = sum(1 for c in valid if len({by[a][c] for a in by}) == 1)
    m = res["metrics"]
    check("phase1: falsePassRate(control) is a recomputation",
          m["falsePassRate_single_control"] == round(fp_ctrl, 3))
    check("phase1: falsePassRate(quorum 2-of-3) is a recomputation",
          m["falsePassRate_quorum_2of3"] == round(fp_q, 3))
    check("phase1: noise on clean candidates is a recomputation",
          m["noiseOnClean"] == noise)
    check("phase1: unanimity count is a recomputation",
          m["unanimousCandidates"] == f"{unanimous}/{len(valid)}")
    th = res["declaredThreshold"]
    met = fp_q <= 0.5 * fp_ctrl
    # Латентность пересчитывается из wallSeconds кворумной руки (A2..A4) —
    # раньше нога доверяла опубликованному met (находка чекера r1, low).
    w = res["wallSeconds"]
    par = max(w[a] for a in ("A2", "A3", "A4"))
    seq = sum(w[a] for a in ("A2", "A3", "A4"))
    lat_met = par <= seq
    check("phase1: latency leg is a recomputation from quorum-arm wallSeconds",
          th["latencyPart"]["parallelMaxQuorumArm"] == par
          and th["latencyPart"]["sequentialSumQuorumArm"] == seq
          and th["latencyPart"]["met"] == lat_met)
    check("phase1: threshold verdict follows the pre-registered rule",
          th["falsePassPart"]["met"] == met
          and th["overall"] == ("MET" if met and lat_met else "NOT MET"))
    check("phase1: population substitution is declared, not silent",
          "subagent" in res["population"] and any(
              "продюсер" in x for x in res["limitations"]))

    print("\n%d checks, %d failed" % (passed + failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
