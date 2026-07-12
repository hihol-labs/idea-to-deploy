#!/usr/bin/env python3
"""OTel-экспортёр леджеров idea-to-deploy -> OTLP/HTTP JSON (v1.88.0, GP-005,
«пункт 4: стандартизация через OpenTelemetry»).

Маппинг (структура из статьи «трейс = сессия, span = задача, саб-span = шаг
верификации»):

  trace                          <- сессия работы над целью (--session id, иначе
                                    детерминированно из GOAL.json createdAt)
  root span "itd.goal"           <- цель целиком (min..max событий)
  span "itd.unit <id>"           <- юнит/задача: activated -> verified/failed
                                    (пары из events.jsonl, actor=harness)
  sub-span "itd.verify <id>"     <- шаг верификации: событие verified/failed
  sub-span "itd.signal <kind>"   <- runtime-сигнал из signals.jsonl (--signals),
                                    родитель — юнит, чьё окно накрывает ts,
                                    иначе root

Инвариант best-effort (методология): JSONL-леджеры ОСТАЮТСЯ каноном и
единственным контрактом; экспортёр — односторонний ТРАНСПОРТ в стандартную
цепочку наблюдаемости (Jaeger/Zipkin/любой OTLP-коллектор). Его исчезновение
ничего не ломает; ни один гейт на OTLP не завязан.

Stdlib only. Запуск:
  python3 scripts/itd_otel_export.py --memory-dir .itd-memory \
      [--signals .claude/completion/signals.jsonl] [--session <id>] \
      [--out payload.json] [--endpoint http://localhost:4318/v1/traces]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SERVICE = "idea-to-deploy"


def _nano(iso: str) -> int:
    """ISO-8601 ('2026-07-12T15:13:18Z') -> unix nanoseconds."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000_000)
    except Exception:
        return 0


def _hex_id(seed: str, nchars: int) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:nchars]


def _attr(key: str, value) -> dict:
    if isinstance(value, bool):
        v = {"boolValue": value}
    elif isinstance(value, int):
        v = {"intValue": str(value)}
    else:
        v = {"stringValue": str(value)[:500]}
    return {"key": key, "value": v}


def read_jsonl(path: Path) -> list:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def build_payload(memory_dir: Path, signals_path: Path | None, session: str | None) -> dict:
    events = [e for e in read_jsonl(memory_dir / "events.jsonl") if e.get("type") == "unit"]
    goal = {}
    gp = memory_dir / "GOAL.json"
    if gp.is_file():
        try:
            goal = json.loads(gp.read_text(encoding="utf-8"))
        except Exception:
            goal = {}

    trace_seed = session or f'{goal.get("goal", "itd")}|{goal.get("createdAt", "")}'
    trace_id = _hex_id("trace|" + trace_seed, 32)

    # окна юнитов: activated -> последний verified/failed/regressed
    units: dict[str, dict] = {}
    for e in events:
        name = e.get("name") or "?"
        at = _nano(e.get("at") or "")
        u = units.setdefault(name, {"start": 0, "end": 0, "verify": []})
        d = e.get("decision")
        if d == "activated" and (u["start"] == 0 or at < u["start"]):
            u["start"] = at
        if d in ("verified", "failed", "regressed", "blocked"):
            u["verify"].append((d, at, e.get("evidence") or ""))
            u["end"] = max(u["end"], at)

    known_ids = {u.get("id") for u in goal.get("units", [])} if goal else set()
    if known_ids:
        units = {k: v for k, v in units.items() if k in known_ids}

    all_ts = [t for u in units.values() for t in (u["start"], u["end"]) if t]
    root_start = min(all_ts) if all_ts else 0
    root_end = max(all_ts) if all_ts else root_start
    root_id = _hex_id("root|" + trace_seed, 16)

    spans = [{
        "traceId": trace_id, "spanId": root_id, "name": "itd.goal",
        "kind": 1, "startTimeUnixNano": str(root_start), "endTimeUnixNano": str(root_end),
        "attributes": [_attr("itd.goal", goal.get("goal", "")),
                       _attr("itd.goal.status", goal.get("status", ""))],
    }]

    for name, u in sorted(units.items()):
        start = u["start"] or (u["end"] or root_start)
        end = u["end"] or start
        span_id = _hex_id(f"unit|{trace_seed}|{name}", 16)
        last = u["verify"][-1][0] if u["verify"] else "in_progress"
        spans.append({
            "traceId": trace_id, "spanId": span_id, "parentSpanId": root_id,
            "name": f"itd.unit {name}", "kind": 1,
            "startTimeUnixNano": str(start), "endTimeUnixNano": str(end),
            "attributes": [_attr("itd.unit.id", name), _attr("itd.unit.decision", last)],
            "status": {"code": 1 if last == "verified" else 0},
        })
        for i, (d, at, ev) in enumerate(u["verify"]):
            spans.append({
                "traceId": trace_id,
                "spanId": _hex_id(f"verify|{trace_seed}|{name}|{i}", 16),
                "parentSpanId": span_id,
                "name": f"itd.verify {name}", "kind": 1,
                "startTimeUnixNano": str(at), "endTimeUnixNano": str(at),
                "attributes": [_attr("itd.verify.decision", d),
                               _attr("itd.verify.evidence", ev)],
                "status": {"code": 1 if d == "verified" else 2},
            })

    if signals_path:
        for i, s in enumerate(read_jsonl(signals_path)):
            if session and s.get("session") not in (session, "unknown"):
                continue
            ts = _nano(s.get("ts") or "")
            parent = root_id
            for name, u in units.items():
                if u["start"] and u["start"] <= ts <= (u["end"] or ts):
                    parent = _hex_id(f"unit|{trace_seed}|{name}", 16)
                    break
            attrs = [_attr("itd.signal.kind", s.get("kind", "")),
                     _attr("itd.signal.layer", int(s.get("layer", 0))),
                     _attr("itd.signal.class", s.get("class", "")),
                     _attr("itd.signal.outcome", s.get("outcome", "")),
                     _attr("itd.signal.command", s.get("command", ""))]
            if s.get("anomaly"):
                attrs.append(_attr("itd.signal.anomaly", s["anomaly"]))
            spans.append({
                "traceId": trace_id,
                "spanId": _hex_id(f"signal|{trace_seed}|{i}|{s.get('ts','')}", 16),
                "parentSpanId": parent,
                "name": f"itd.signal {s.get('kind','?')}", "kind": 1,
                "startTimeUnixNano": str(ts), "endTimeUnixNano": str(ts),
                "attributes": attrs,
                "status": {"code": 2 if s.get("outcome") == "fail" else 1},
            })

    return {
        "resourceSpans": [{
            "resource": {"attributes": [
                _attr("service.name", SERVICE),
                _attr("itd.machine", os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "?")),
            ]},
            "scopeSpans": [{"scope": {"name": "itd", "version": "1.88.0"}, "spans": spans}],
        }]
    }


def validate_payload(payload: dict) -> list[str]:
    """Офлайн-валидация OTLP JSON: структура, hex-id, времена. -> список ошибок."""
    errs = []
    try:
        rs = payload["resourceSpans"]
        assert isinstance(rs, list) and rs, "resourceSpans пуст"
        res_attrs = {a["key"] for a in rs[0]["resource"]["attributes"]}
        if "service.name" not in res_attrs:
            errs.append("нет resource attr service.name")
        spans = rs[0]["scopeSpans"][0]["spans"]
        assert spans, "нет spans"
        ids = set()
        for sp in spans:
            if not (len(sp["traceId"]) == 32 and int(sp["traceId"], 16) >= 0):
                errs.append(f"traceId не 32-hex: {sp.get('traceId')}")
            if not (len(sp["spanId"]) == 16 and int(sp["spanId"], 16) >= 0):
                errs.append(f"spanId не 16-hex: {sp.get('spanId')}")
            if sp["spanId"] in ids:
                errs.append(f"дубль spanId: {sp['spanId']}")
            ids.add(sp["spanId"])
            if int(sp["endTimeUnixNano"]) < int(sp["startTimeUnixNano"]):
                errs.append(f"end < start в {sp['name']}")
            if "parentSpanId" in sp and sp["parentSpanId"] not in ids and \
               all(o["spanId"] != sp["parentSpanId"] for o in spans):
                errs.append(f"parentSpanId вне трейса: {sp['name']}")
    except Exception as exc:
        errs.append(f"структура: {exc}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--memory-dir", default=".itd-memory")
    ap.add_argument("--signals", default=None)
    ap.add_argument("--session", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--endpoint", default=None,
                    help="OTLP/HTTP, например http://localhost:4318/v1/traces")
    args = ap.parse_args()

    payload = build_payload(Path(args.memory_dir),
                            Path(args.signals) if args.signals else None,
                            args.session)
    errs = validate_payload(payload)
    if errs:
        for e in errs:
            print("INVALID:", e, file=sys.stderr)
        return 1

    n = len(payload["resourceSpans"][0]["scopeSpans"][0]["spans"])
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"payload OK: {n} spans -> {args.out}")
    if args.endpoint:
        req = urllib.request.Request(
            args.endpoint, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"exported: {n} spans -> {args.endpoint} HTTP {resp.status}")
            if resp.status not in (200, 202):
                return 1
    if not args.out and not args.endpoint:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
