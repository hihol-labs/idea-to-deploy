#!/usr/bin/env python3
"""Fail closed on stale Harness map, version, inventory, or taxonomy claims."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BLOCK_RE = re.compile(
    r'permissionDecision"?\s*:\s*"deny"|"decision"\s*:\s*"block"|'
    r'sys\.exit\(2\)|(?:^|\s|;)exit\s+2(?:\s|$)', re.M)
OBSOLETE_LIVE_GUARD_RE = re.compile(
    r"(?:remove|delete|убрать|удалить)\s+(?:the\s+)?`?if\s*:\s*false`?\s+(?:guard|гейт)",
    re.I,
)


def active_documentation() -> dict[str, str]:
    paths = [ROOT / "README.md", ROOT / "README.ru.md"]
    paths.extend((ROOT / "docs").rglob("*.md"))
    paths.extend((ROOT / "tests" / "references").rglob("*.md"))
    return {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in paths if path.is_file()
    }


def stale_live_guard_claims(documents: dict[str, str]) -> list[str]:
    return [path for path, content in documents.items()
            if OBSOLETE_LIVE_GUARD_RE.search(content)]


def validate(state: dict, today: dt.date | None = None) -> list[str]:
    issues: list[str] = []
    versions = {
        json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"],
        json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())["version"],
    }
    if versions != {state.get("pluginVersion")}:
        issues.append("plugin version drift")
    skills = len([p for p in (ROOT / "skills").glob("*/SKILL.md")
                  if not p.parent.name.startswith("_")])
    agents = len(list((ROOT / "agents").glob("*.md")))
    hooks = list((ROOT / "hooks").glob("*.sh"))
    hard = len([p for p in hooks if BLOCK_RE.search(p.read_text(encoding="utf-8"))])
    actual = {"skills": skills, "subagents": agents, "hooks": len(hooks),
              "hardGates": hard, "softHooks": len(hooks) - hard}
    if state.get("inventory") != actual:
        issues.append(f"inventory drift: {actual}")
    try:
        reviewed = dt.date.fromisoformat(str(state.get("reviewedAt")))
        max_age = int(state.get("maxAgeDays"))
        age = ((today or dt.date.today()) - reviewed).days
        if age < 0 or age > max_age or not 1 <= max_age <= 90:
            issues.append("freshness window violated")
    except Exception:
        issues.append("freshness metadata invalid")
    digest = hashlib.sha256((ROOT / "docs" / "HARNESS_CONFORMANCE_CONTRACT.json").read_bytes()).hexdigest()
    if state.get("conformanceContractSha256") != digest:
        issues.append("conformance digest drift")
    if state.get("canonicalMap") != "docs/HARNESS_ENGINEERING_MAP.md":
        issues.append("canonical map path drift")
    if state.get("conformanceReport") != "docs/HARNESS_CONFORMANCE_REPORT.md":
        issues.append("conformance report path drift")
    if state.get("qualityLedger") != "docs/QUALITY.json":
        issues.append("quality ledger path drift")
    map_text = (ROOT / "docs" / "HARNESS_ENGINEERING_MAP.md").read_text(encoding="utf-8")
    marker = "<!-- harness-docs-state: docs/HARNESS_DOCS_STATE.json -->"
    if marker not in map_text:
        issues.append("map lacks machine-state marker")
    current_claim = (f"{skills} skills, {agents} subagents, {len(hooks)} hooks, "
                     f"{hard} hard gates, {len(hooks)-hard} soft hooks")
    if current_claim not in map_text:
        issues.append("map current inventory claim drift")
    if "Итог: 5,0/5,0" not in map_text or "HARNESS_CONFORMANCE_REPORT.md" not in map_text:
        issues.append("map final score/report claim drift")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"{skills} skills + {agents} specialized agents" not in readme:
        issues.append("README skill/agent claim drift")
    if "11 hard gates vs 18 soft" not in readme or "11/18/29 split" not in readme:
        issues.append("README taxonomy narrative drift")
    for stale in ("All 28 hooks", "10/18/28 split", "Все 8 блокирующих", "16 soft-хуков"):
        if stale in map_text or stale in readme:
            issues.append(f"stale active narrative: {stale}")
    stale_guard_docs = stale_live_guard_claims(active_documentation())
    if stale_guard_docs:
        issues.append("obsolete live-workflow guard instruction: " + ", ".join(stale_guard_docs))

    report = (ROOT / "docs" / "HARNESS_CONFORMANCE_REPORT.md").read_text(encoding="utf-8")
    live = json.loads((ROOT / "tests" / "fixtures" / "live-model-evidence" / "latest.json").read_text())
    report_markers = (
        "Результат: 5,0/5,0",
        f"v{state.get('pluginVersion')}",
        str(state.get("conformanceContractSha256")),
        str(live.get("runId")),
        "16 контрольных случаев",
        "срок 30 дней",
    )
    if any(marker not in report for marker in report_markers):
        issues.append("conformance report evidence/limitation drift")

    quality = json.loads((ROOT / "docs" / "QUALITY.json").read_text())
    if quality.get("reviewedAt") != state.get("reviewedAt"):
        issues.append("quality ledger review date drift")
    quality_rows = {row.get("id"): row for row in quality.get("modules", []) if isinstance(row, dict)}
    harness_row = quality_rows.get("harness-engineering-conformance", {})
    required_quality_evidence = {
        "docs/HARNESS_CONFORMANCE_REPORT.md",
        "docs/HARNESS_CONFORMANCE_CONTRACT.json",
        "docs/HARNESS_DOCS_STATE.json",
        "tests/verify_harness_conformance.py",
        "tests/fixtures/live-model-evidence/latest.json",
    }
    if (harness_row.get("grade") != "A"
            or harness_row.get("verification") != "passing"
            or harness_row.get("reviewedAt") != state.get("reviewedAt")
            or not required_quality_evidence.issubset(set(harness_row.get("evidence", [])))):
        issues.append("quality ledger harness-conformance row drift")

    scorecard = json.loads((ROOT / "docs" / "QUALITY_SCORECARD.json").read_text())
    probes = {probe.get("id"): probe for probe in scorecard.get("probes", []) if isinstance(probe, dict)}
    modules = {module.get("id"): module for module in scorecard.get("modules", []) if isinstance(module, dict)}
    harness_probe = probes.get("harness-conformance", {})
    if (not str(harness_probe.get("command") or "").startswith(
            "sh skills/_shared/itd_py.sh tests/verify_harness_conformance.py --axis all")
            or harness_probe.get("attempts") != 2
            or harness_probe.get("passFailParser") != "stdout_contains"
            or harness_probe.get("expectedOutput") != "ITD_PROBE_OK: harness-conformance"):
        issues.append("quality scorecard conformance probe drift")
    for probe_id, probe in probes.items():
        if (not str(probe.get("command") or "").startswith("sh skills/_shared/itd_py.sh ")
                or probe.get("passFailParser") != "stdout_contains"
                or not str(probe.get("expectedOutput") or "").startswith("ITD_PROBE_OK:")):
            issues.append(f"quality scorecard launcher/result marker drift: {probe_id}")
    if "harness-engineering-conformance" not in modules:
        issues.append("quality scorecard harness module missing")
    return issues


def main() -> int:
    state = json.loads((ROOT / "docs" / "HARNESS_DOCS_STATE.json").read_text())
    issues = validate(state)
    checks = [("current harness documentation state is fresh", not issues)]
    mutated = json.loads(json.dumps(state))
    mutated["inventory"]["hooks"] -= 1
    checks.append(("mutation: inventory drift fails closed", bool(validate(mutated))))
    mutated = json.loads(json.dumps(state))
    mutated["reviewedAt"] = "2020-01-01"
    checks.append(("mutation: stale review date fails closed", bool(validate(mutated))))
    stale_mutation = {"tests/references/mutated.md": "Для активации: убрать `if: false` guard"}
    checks.append(("mutation: obsolete live-workflow guard instruction fails closed",
                   bool(stale_live_guard_claims(stale_mutation))))
    failed = 0
    for name, condition in checks:
        print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f" [{'; '.join(issues)}]" if not condition and issues else ""))
        failed += int(not condition)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
