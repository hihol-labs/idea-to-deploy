#!/usr/bin/env python3
"""Mutation tests for prompt-bearing MCP/tool trust inventory."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "itd_harness_controls", ROOT / "skills/_shared/itd_harness_controls.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "integration"), default="all")
    args = parser.parse_args()
    registry = json.loads(
        (ROOT / "docs/templates/itd/TOOL_CAPABILITY_REGISTRY.json").read_text())
    checks: list[tuple[str, bool]] = [
        ("current tool trust inventory passes", not MOD.validate_tool_trust(registry))
    ]
    mutated = copy.deepcopy(registry)
    target = next(row for row in mutated["tools"] if row["type"] == "mcp")
    del target["trust"]["source"]
    checks.append(("missing MCP provenance fails closed",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    target = next(row for row in mutated["tools"] if row["type"] == "research")
    target["trust"]["disposition"] = "allow"
    target["trust"]["promptTextReviewed"] = False
    checks.append(("unreviewed prompt surface cannot be allow",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    target = next(row for row in mutated["tools"] if row["type"] == "mcp")
    target["type"] = "local"
    target["trust"]["disposition"] = "allow"
    target["trust"]["promptTextReviewed"] = False
    checks.append(("retyping MCP as local cannot bypass prompt trust",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    mutated["trustPolicy"]["defaultForUnknownPromptBearingProvider"] = "allow"
    checks.append(("unknown provider cannot default allow",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    mutated["tools"][0]["trust"]["undeclared"] = True
    checks.append(("undeclared nested trust metadata fails closed",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    mutated["tools"][0]["capabilities"]["undeclared"] = True
    checks.append(("undeclared nested capability metadata fails closed",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    target = next(row for row in mutated["tools"] if row["id"] == "filesystem")
    target["trust"]["disposition"] = "allow"
    target["trust"]["promptTextReviewed"] = False
    checks.append(("unreviewed local prompt surface cannot be allow",
                   bool(MOD.validate_tool_trust(mutated))))
    mutated = copy.deepcopy(registry)
    target = next(row for row in mutated["tools"] if row["type"] == "mcp")
    target["trust"]["disposition"] = "allow"
    target["trust"]["promptTextReviewed"] = True
    target["trust"]["reviewEvidence"] = "README.md"
    checks.append(("prompt-bearing allow requires provider-bound review evidence",
                   bool(MOD.validate_tool_trust(mutated))))
    if args.phase == "all":
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (ROOT / "docs/templates/itd/TOOL_CAPABILITY_REGISTRY.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        checks.append(("current registry satisfies its executable JSON Schema",
                       not list(Draft202012Validator(schema).iter_errors(registry))))
        tool_schema = schema["properties"]["tools"]["items"]
        trust_schema = tool_schema["properties"]["trust"]
        nested = [
            tool_schema["properties"][name]
            for name in ("capabilities", "demandGate", "semanticNavigation")
        ]
        nested.extend([
            tool_schema["properties"]["semanticNavigation"]["properties"][name]
            for name in ("coverage", "confidence", "fallback")
        ])
        checks.append(("nested JSON schemas are closed",
                       schema.get("additionalProperties") is False
                       and schema["properties"]["trustPolicy"].get("additionalProperties") is False
                       and tool_schema.get("additionalProperties") is False
                       and trust_schema.get("additionalProperties") is False
                       and all(item.get("additionalProperties") is False for item in nested)))
        mutated = copy.deepcopy(registry)
        mutated["tools"][0]["trust"]["undeclared"] = True
        checks.append(("JSON Schema rejects undeclared nested trust metadata",
                       bool(list(Draft202012Validator(schema).iter_errors(mutated)))))
        mutated = copy.deepcopy(registry)
        target = next(row for row in mutated["tools"] if row["id"] == "filesystem")
        target["trust"]["promptTextReviewed"] = False
        checks.append(("JSON Schema rejects unreviewed local allow",
                       bool(list(Draft202012Validator(schema).iter_errors(mutated)))))

    if args.phase in {"all", "integration"}:
        adopt = (ROOT / "skills/adopt/SKILL.md").read_text(encoding="utf-8")
        security = (ROOT / "skills/security-audit/references/security-checklist.md").read_text(
            encoding="utf-8")
        contracts = (ROOT / "docs/CONTRACTS.md").read_text(encoding="utf-8")
        run_all = (ROOT / "tests/run-all.sh").read_text(encoding="utf-8")
        workflows = "\n".join(
            path.read_text(encoding="utf-8") for path in (
                ROOT / ".github/workflows/meta-review.yml",
                ROOT / ".github/workflows/windows-verify.yml",
            )
        )
        normalized_adopt = " ".join(adopt.split())
        checks.append(("adopt inventories prompt-bearing providers read-only",
                       all(fragment in normalized_adopt for fragment in (
                           "prompt-bearing", "auto-install", "auto-update",
                           "authenticate", "grant permissions", "mark a provider trusted",
                       ))))
        checks.append(("security audit includes MCP/tool trust check",
                       "MEM-8" in security and "TOOL_CAPABILITY_REGISTRY" in security))
        checks.append(("contract catalog names prompt trust",
                       "prompt-trust" in contracts))
        checks.append(("MEM-8 sensor is wired into local suites",
                       "verify_tool_trust_inventory" in run_all))
        checks.append(("MEM-8 sensor is wired into Linux and Windows CI",
                       workflows.count("verify_tool_trust_inventory") >= 2))

    failed = 0
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        failed += int(not passed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
