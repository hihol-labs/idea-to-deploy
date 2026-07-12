#!/usr/bin/env python3
"""Behavioural proof: exporter unit-attribution by field + semconv + usage
(v1.89.0, GO-004 — «атрибуция sub-span + semconv + иерархия span»).

  - сигнал с полем unit цепляется к span этого юнита (НЕ по времени)
  - orphan-доля сигналов <10% когда все несут unit
  - signal-span несут process.command_line/exit_code
  - test/verify-сигнал несёт test.case.result.status
  - agent-сигнал несёт gen_ai.operation.name (+ usage-токены)
  - validate_semconv зелёный на корректном payload, ловит отсутствие атрибута

Self-contained, stdlib only. Run: python3 tests/verify_otel_semconv.py
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


def attrs_of(sp):
    return {a["key"]: list(a["value"].values())[0] for a in sp.get("attributes", [])}


def main():
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td)
        (mem / "GOAL.json").write_text(json.dumps({
            "version": 1, "goal": "g", "status": "active", "createdAt": "2026-07-12T08:00:00Z",
            "units": [{"id": "U-1", "criterion": "c", "verificationCommand": "true", "status": "verified"},
                      {"id": "U-2", "criterion": "c", "verificationCommand": "true", "status": "in_progress"}],
        }), encoding="utf-8")
        (mem / "events.jsonl").write_text("\n".join([
            json.dumps({"at": "2026-07-12T09:00:00Z", "actor": "harness", "type": "unit", "name": "U-1", "decision": "activated"}),
            json.dumps({"at": "2026-07-12T09:30:00Z", "actor": "harness", "type": "unit", "name": "U-1", "decision": "verified", "evidence": "exit 0"}),
            json.dumps({"at": "2026-07-12T10:00:00Z", "actor": "harness", "type": "unit", "name": "U-2", "decision": "activated"}),
        ]) + "\n", encoding="utf-8")
        sigs = mem / "signals.jsonl"
        sigs.write_text("\n".join([
            # verify-сигнал U-2 но с ts ВНЕ окна U-2 (проверяем атрибуцию по полю, не по времени)
            json.dumps({"ts": "2026-07-11T00:00:00Z", "kind": "verify", "layer": 2, "class": "verification",
                        "command": "otk: pytest", "outcome": "pass", "unit": "U-2", "session": "otk"}),
            json.dumps({"ts": "2026-07-12T09:15:00Z", "kind": "test_run", "layer": 2, "class": "verification",
                        "command": "pytest -q", "outcome": "pass", "unit": "U-1", "session": "s1"}),
            json.dumps({"ts": "2026-07-12T09:16:00Z", "kind": "agent", "layer": 0, "class": "delegation",
                        "command": "agent:code-reviewer", "outcome": "ok",
                        "input_tokens": 1000, "output_tokens": 200, "unit": "U-1", "session": "s1"}),
        ]) + "\n", encoding="utf-8")

        p = mod.build_payload(mem, sigs, None)
        spans = p["resourceSpans"][0]["scopeSpans"][0]["spans"]
        by_name = {}
        for s in spans:
            by_name.setdefault(s["name"], []).append(s)
        u2_id = None
        for s in spans:
            if s["name"] == "itd.unit U-2":
                u2_id = s["spanId"]

        # 1) verify-сигнал U-2 цеплён к span U-2 по полю (несмотря на ts вне окна)
        vsig = by_name["itd.signal verify"][0]
        check("сигнал с unit -> span юнита по полю (не по времени)",
              vsig.get("parentSpanId") == u2_id, str(vsig.get("parentSpanId")) + " vs " + str(u2_id))

        # 2) orphan-доля < 10%
        root = [s for s in spans if s["name"] == "itd.goal"][0]["spanId"]
        sig_spans = [s for s in spans if s["name"].startswith("itd.signal")]
        orphan = sum(1 for s in sig_spans if s.get("parentSpanId") == root)
        check("orphan-доля сигналов < 10%", orphan / max(1, len(sig_spans)) < 0.1, f"{orphan}/{len(sig_spans)}")

        # 3) semconv на signal-span
        a = attrs_of(by_name["itd.signal test_run"][0])
        check("test_run: process.command_line + test.case.result.status",
              "process.command_line" in a and a.get("test.case.result.status") == "passed", str(a))
        check("test_run: process.exit_code 0", a.get("process.exit_code") == "0", str(a))

        # 4) agent semconv + usage
        a = attrs_of(by_name["itd.signal agent"][0])
        check("agent: gen_ai.operation.name invoke_agent",
              a.get("gen_ai.operation.name") == "invoke_agent", str(a))
        check("agent: gen_ai.usage.* токены",
              a.get("gen_ai.usage.input_tokens") == "1000" and a.get("gen_ai.usage.output_tokens") == "200", str(a))

        # 5) валидаторы
        check("validate_payload чистый", mod.validate_payload(p) == [], str(mod.validate_payload(p)))
        check("validate_semconv чистый", mod.validate_semconv(p) == [], str(mod.validate_semconv(p)))

        # 6) semconv-валидатор ловит пропуск
        broken = json.loads(json.dumps(p))
        for s in broken["resourceSpans"][0]["scopeSpans"][0]["spans"]:
            if s["name"] == "itd.signal agent":
                s["attributes"] = [a for a in s["attributes"] if a["key"] != "gen_ai.operation.name"]
        check("validate_semconv ловит пропуск gen_ai", mod.validate_semconv(broken) != [], "")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
