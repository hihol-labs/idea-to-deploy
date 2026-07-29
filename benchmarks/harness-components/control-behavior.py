#!/usr/bin/env python3
"""Fixed behavioral metrics for reversible harness-control ablation.

Each probe exercises the protected behavior directly.  With the component's
documented disable environment set, the score must fall from 1 to 0; a generic
test-suite exit code is intentionally not accepted as an ablation metric.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def run_hook(name: str, payload: dict, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(ROOT / "hooks" / name)],
        input=json.dumps(payload), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=merged, timeout=30,
    )


def transcript_payload(final_text: str) -> tuple[dict, tempfile.TemporaryDirectory]:
    holder = tempfile.TemporaryDirectory(prefix="itd-control-transcript-")
    base = Path(holder.name)
    sid = "s-" + uuid.uuid4().hex[:8]
    agent_dir = base / sid / "subagents"
    agent_dir.mkdir(parents=True)
    transcript = agent_dir / "agent-checker.jsonl"
    rows = [
        {"type": "user", "isSidechain": True,
         "message": {"role": "user", "content": "review"}},
        {"type": "assistant", "isSidechain": True,
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": final_text}]}},
    ]
    transcript.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return {
        "session_id": sid,
        "transcript_path": str(transcript),
        "stop_hook_active": False,
        "hook_event_name": "SubagentStop",
    }, holder


def narration_final() -> int:
    payload, holder = transcript_payload(
        "I checked the first files.\n\nNow check the remaining tests.")
    try:
        result = run_hook("narration-final.sh", payload)
        data = json.loads(result.stdout or "{}")
        return int(data.get("decision") == "block")
    finally:
        holder.cleanup()


def verdict_contract() -> int:
    payload, holder = transcript_payload(
        "FINAL STATUS: PASSED — no findings in the reviewed diff.")
    try:
        result = run_hook("verdict-contract.sh", payload)
        data = json.loads(result.stdout or "{}")
        return int(data.get("decision") == "block")
    finally:
        holder.cleanup()


def wip_scope() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-control-wip-") as raw:
        root = Path(raw)
        (root / ".itd-memory").mkdir()
        (root / ".itd").mkdir()
        (root / ".itd-memory/STATE.json").write_text(json.dumps({
            "currentUnit": {"id": "U-1", "goal": "bounded change",
                            "status": "verifying"}
        }), encoding="utf-8")
        (root / ".itd/SCOPE_LOCK.md").write_text(
            "## Allowed Change Areas\n\n- `src/`\n\n## Forbidden Change Areas\n\n- everything else\n",
            encoding="utf-8")
        (root / ".codex-plugin").mkdir()
        (root / ".codex-plugin/plugin.json").write_text(
            '{"name":"fixture"}', encoding="utf-8")
        payload = {
            "session_id": "ablation-wip",
            "cwd": str(root),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(root / "docs/outside.md")},
        }
        result = run_hook(
            "wip-gate.sh", payload, {"ITD_WIP_GATE_RATE_MIN": "0"})
        data = json.loads(result.stdout or "{}")
        text = str((data.get("hookSpecificOutput") or {}).get(
            "additionalContext") or "")
        return int("[WIP-GATE" in text)


def handoff_readiness() -> int:
    with tempfile.TemporaryDirectory(prefix="itd-control-handoff-") as raw:
        root = Path(raw)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "bench@example.com"],
                       cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Benchmark"],
                       cwd=root, check=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
        (root / "tracked.txt").write_text("two\n", encoding="utf-8")
        payload = {
            "session_id": "ablation-handoff",
            "cwd": str(root),
            "stop_hook_active": False,
        }
        result = run_hook(
            "handoff-readiness.sh", payload, {"ITD_HANDOFF_RATE_MIN": "0"})
        data = json.loads(result.stdout or "{}")
        return int("[HANDOFF-READINESS]" in str(data.get("systemMessage") or ""))


PROBES = {
    "narration-final": narration_final,
    "verdict-contract": verdict_contract,
    "wip-scope": wip_scope,
    "handoff-readiness": handoff_readiness,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", choices=tuple(PROBES), required=True)
    args = parser.parse_args()
    score = PROBES[args.component]()
    print(json.dumps({"score": score}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
