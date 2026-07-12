#!/usr/bin/env python3
"""Behavioural proof: OTel-экспортёр JSONL -> OTLP (v1.88.0, GP-005,
«пункт 4: стандартизация через OpenTelemetry»).

Строит payload из синтетических леджеров и проверяет маппинг статьи:
trace = сессия, span = юнит/задача, sub-span = шаг верификации; сигналы —
sub-span'ы юнита, чьё окно накрывает их ts. Плюс офлайн-валидатор ловит
битые id. Сеть не используется (смоук с коллектором — отдельно, GP-005).

Self-contained, stdlib only. Run: python3 tests/verify_otel_export.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("itd_otel_export", REPO / "scripts" / "itd_otel_export.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS  " + name)
    else:
        FAIL += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def main():
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td)
        (mem / "GOAL.json").write_text(json.dumps({
            "version": 1, "goal": "test goal", "status": "active",
            "createdAt": "2026-07-12T08:00:00Z",
            "units": [{"id": "U-1", "criterion": "c", "verificationCommand": "true",
                       "status": "verified"}],
        }), encoding="utf-8")
        (mem / "events.jsonl").write_text("\n".join([
            json.dumps({"id": "e1", "at": "2026-07-12T09:00:00Z", "actor": "harness",
                        "type": "unit", "name": "U-1", "decision": "activated"}),
            json.dumps({"id": "e2", "at": "2026-07-12T09:30:00Z", "actor": "harness",
                        "type": "unit", "name": "U-1", "decision": "verified",
                        "evidence": "exit 0"}),
        ]) + "\n", encoding="utf-8")
        sigs = mem / "signals.jsonl"
        sigs.write_text(json.dumps({
            "ts": "2026-07-12T09:15:00Z", "kind": "test_run", "layer": 2,
            "class": "verification", "command": "pytest -q", "outcome": "pass",
            "evidence": "3 passed", "session": "s1"}) + "\n", encoding="utf-8")

        p = mod.build_payload(mem, sigs, "s1")
        spans = p["resourceSpans"][0]["scopeSpans"][0]["spans"]
        by_name = {s["name"]: s for s in spans}

        check("root itd.goal есть", "itd.goal" in by_name)
        check("span юнита есть", "itd.unit U-1" in by_name)
        u = by_name.get("itd.unit U-1", {})
        check("юнит — ребёнок root",
              u.get("parentSpanId") == by_name["itd.goal"]["spanId"])
        check("окно юнита activated->verified",
              u.get("startTimeUnixNano") < u.get("endTimeUnixNano"), str(u)[:120])
        v = by_name.get("itd.verify U-1", {})
        check("sub-span верификации — ребёнок юнита",
              v.get("parentSpanId") == u.get("spanId"))
        check("verify: status ok + evidence",
              v.get("status", {}).get("code") == 1 and
              any(a["key"] == "itd.verify.evidence" for a in v.get("attributes", [])))
        s = by_name.get("itd.signal test_run", {})
        check("сигнал — sub-span юнита (окно накрывает ts)",
              s.get("parentSpanId") == u.get("spanId"), str(s)[:150])
        check("сигнал несёт layer/class/outcome",
              {a["key"] for a in s.get("attributes", [])} >=
              {"itd.signal.layer", "itd.signal.class", "itd.signal.outcome"})
        check("один traceId на всё (trace = сессия)",
              len({sp["traceId"] for sp in spans}) == 1)
        check("resource: service.name",
              any(a["key"] == "service.name"
                  for a in p["resourceSpans"][0]["resource"]["attributes"]))

        check("валидатор: чистый payload без ошибок", mod.validate_payload(p) == [],
              str(mod.validate_payload(p)))
        broken = json.loads(json.dumps(p))
        broken["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"] = "xyz"
        check("валидатор ловит битый traceId", mod.validate_payload(broken) != [])

        # детерминизм: одинаковые входы -> одинаковые id (resume-совместимость)
        p2 = mod.build_payload(mem, sigs, "s1")
        check("экспорт детерминирован", json.dumps(p) == json.dumps(p2))

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
