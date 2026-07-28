#!/usr/bin/env python3
"""Plan, generate, and validate derived project context for `/adopt`.

The index records only directly observed file facts. It never interprets
domain intent, architecture, or plan state, and it never writes normative
`.itd` contracts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys
import unicodedata
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
CONTRACT_PATH = REPO_ROOT / "docs" / "templates" / "itd" / "AGENT_CONTEXT_CONTRACT.json"


class ContextError(ValueError):
    """A fail-closed, user-actionable context error."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextError(f"{label} is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError(f"{label} is unreadable JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContextError(f"{label} must contain a JSON object: {path}")
    return value


def is_link_or_reparse(path: pathlib.Path) -> bool:
    if path.is_symlink():
        return True
    junction_probe = getattr(path, "is_junction", None)
    try:
        if callable(junction_probe) and junction_probe():
            return True
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except (FileNotFoundError, OSError):
        return False
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_flag)


def inside(root: pathlib.Path, candidate: pathlib.Path, label: str) -> pathlib.Path:
    """Return the lexical path after containment and symlink-chain checks."""
    resolved_root = root.resolve()
    try:
        lexical_relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ContextError(f"{label} escapes the project root: {candidate}") from exc
    if ".." in lexical_relative.parts:
        raise ContextError(f"{label} contains parent traversal: {candidate}")
    cursor = root
    for part in lexical_relative.parts:
        cursor = cursor / part
        if is_link_or_reparse(cursor):
            raise ContextError(f"{label} contains a symlink/reparse component: {cursor}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ContextError(f"{label} escapes the project root: {candidate}") from exc
    return candidate


def relative_source(root: pathlib.Path, path: pathlib.Path) -> str:
    logical = inside(root, path, "context source")
    if not logical.is_file():
        raise ContextError(f"context source is not a regular in-project file: {path}")
    return logical.relative_to(root).as_posix()


def first_regular_file(root: pathlib.Path, relative_dir: str) -> pathlib.Path | None:
    directory = inside(root, root / relative_dir, "source root")
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
        inside(root, candidate, "source file")
        if candidate.is_file():
            return candidate
    return None


def claim(topic: str, condition: str, value: str, root: pathlib.Path,
          source: pathlib.Path) -> dict[str, str]:
    relative = relative_source(root, source)
    digest = sha256_file(source.resolve())
    claim_id = sha256_bytes(
        f"{topic}\0{condition}\0{value}\0{relative}\0{digest}".encode("utf-8"))[:20]
    return {
        "id": claim_id,
        "topic": topic,
        "condition": condition,
        "value": value,
        "sourcePath": relative,
        "sourceSha256": digest,
        "trustClass": "observed",
    }


def safe_markdown_scalar(value: str) -> str:
    """Render untrusted path text without Markdown/control injection."""
    rendered: list[str] = []
    for character in value:
        codepoint = ord(character)
        if (character in {"`", "\\"}
                or codepoint < 32 or codepoint == 127
                or not character.isprintable()
                or unicodedata.category(character) == "Cf"):
            rendered.append(f"\\u{codepoint:04x}")
        else:
            rendered.append(character)
    return "".join(rendered)


def observed_claims(root: pathlib.Path, contract: dict[str, Any]) -> list[dict[str, str]]:
    policy = contract.get("sourcePolicy") or {}
    claims: list[dict[str, str]] = []

    for relative in policy.get("normative") or []:
        source = root / str(relative)
        if source.is_file() and not source.is_symlink():
            claims.append(claim(
                "normative-contract",
                "Load before interpreting project-specific constraints or allowed changes.",
                "Observed project guidance or contract.",
                root, source))

    for relative in policy.get("manifests") or []:
        source = root / str(relative)
        if source.is_file() and not source.is_symlink():
            claims.append(claim(
                "project-manifest",
                "Load when changing build, dependency, package, or runtime metadata.",
                "Observed project manifest.",
                root, source))

    for relative in policy.get("sourceRoots") or []:
        source = first_regular_file(root, str(relative))
        if source is not None:
            claims.append(claim(
                "source-layout",
                f"Load when work may touch the {relative}/ source area.",
                f"Observed source area {relative}/.",
                root, source))

    for relative in policy.get("testRoots") or []:
        source = first_regular_file(root, str(relative))
        if source is not None:
            claims.append(claim(
                "test-layout",
                "Load when selecting, adding, or changing project verification.",
                f"Observed test area {relative}/.",
                root, source))

    claims.sort(key=lambda row: (row["topic"], row["sourcePath"], row["id"]))
    if not claims:
        raise ContextError(
            "no observed context source was found; keep context generation disabled "
            "until the project has a manifest, guidance contract, source, or test file")
    return claims


def module_markdown(module: dict[str, Any], claims: list[dict[str, str]]) -> str:
    title = pathlib.PurePosixPath(str(module["path"])).stem.replace("-", " ").title()
    selected = [row for row in claims if row["topic"] in set(module.get("topics") or [])]
    lines = [
        f"# {title} context",
        "",
        "> Derived, non-normative view. `.itd` and project source remain authoritative.",
        "",
        f"Applicability: {module['condition']}",
        "",
    ]
    if not selected:
        lines.extend([
            "No directly observed claims currently apply to this module.",
            "",
        ])
    else:
        for row in selected:
            lines.extend([
                f"- {row['value']}",
                f"  - source data: `{safe_markdown_scalar(row['sourcePath'])}`",
                f"  - source sha256: `{row['sourceSha256']}`",
                f"  - trust: `{row['trustClass']}`",
                f"  - condition: {row['condition']}",
            ])
        lines.append("")
    return "\n".join(lines)


def desired_files(root: pathlib.Path) -> tuple[pathlib.Path, dict[str, bytes]]:
    contract = read_object(CONTRACT_PATH, "agent context contract")
    if (contract.get("version") != 1
            or contract.get("authority") != "derived-non-normative"
            or contract.get("trustClasses") != ["observed"]
            or contract.get("inferredClaimsRequireHumanApproval") is not True):
        raise ContextError("agent context template is malformed or weakens trust boundaries")
    output_relative = pathlib.PurePosixPath(str(contract.get("outputDirectory") or ""))
    if output_relative.is_absolute() or ".." in output_relative.parts:
        raise ContextError("agent context output directory must stay project-relative")
    output = inside(root, root / pathlib.Path(*output_relative.parts), "context output")
    claims = observed_claims(root, contract)
    files: dict[str, bytes] = {}
    module_rows: list[dict[str, Any]] = []
    for module in contract.get("modules") or []:
        relative = pathlib.PurePosixPath(str(module.get("path") or ""))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ContextError(f"invalid context module path: {relative}")
        body = module_markdown(module, claims).encode("utf-8")
        files[relative.as_posix()] = body
        topics = set(module.get("topics") or [])
        module_rows.append({
            "path": relative.as_posix(),
            "condition": module.get("condition"),
            "claimIds": [row["id"] for row in claims if row["topic"] in topics],
            "sha256": sha256_bytes(body),
        })
    index = {
        "version": 1,
        "authority": "derived-non-normative",
        "generator": "idea-to-deploy/adopt-context-v1",
        "contract": {
            "path": "docs/templates/itd/AGENT_CONTEXT_CONTRACT.json",
            "sha256": sha256_file(CONTRACT_PATH),
        },
        "claims": claims,
        "modules": module_rows,
        "unsupportedClaims": 0,
    }
    files["index.json"] = json.dumps(
        index, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    return output, files


def write_atomic(path: pathlib.Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def exact_inventory(output: pathlib.Path, expected_files: set[str]) -> dict[str, list[str]]:
    expected_dirs = {
        parent.as_posix()
        for relative in expected_files
        for parent in pathlib.PurePosixPath(relative).parents
        if parent.as_posix() != "."
    }
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    if output.exists():
        inside(output.parent, output, "context output")
        for item in sorted(output.rglob("*"), key=lambda path: path.as_posix()):
            inside(output, item, "context inventory")
            relative = item.relative_to(output).as_posix()
            if item.is_dir():
                actual_dirs.add(relative)
            elif item.is_file():
                actual_files.add(relative)
            else:
                raise ContextError(f"context inventory contains a special file: {relative}")
    return {
        "unexpectedFiles": sorted(actual_files - expected_files),
        "missingFiles": sorted(expected_files - actual_files),
        "unexpectedDirectories": sorted(actual_dirs - expected_dirs),
        "missingDirectories": sorted(expected_dirs - actual_dirs),
    }


def plan_context(root: pathlib.Path) -> dict[str, Any]:
    output, files = desired_files(root)
    result = {
        "status": "plan",
        "writes": [
            {"path": (output / relative).relative_to(root).as_posix(),
             "sha256": sha256_bytes(content)}
            for relative, content in sorted(files.items())
        ],
        "productSourceWrites": 0,
        "normativeContractWrites": 0,
        "inventory": exact_inventory(output, set(files)),
    }
    result["planSha256"] = sha256_bytes(canonical(result))
    return result


def reject_unexpected_inventory(output: pathlib.Path, files: dict[str, bytes]) -> None:
    inventory = exact_inventory(output, set(files))
    unexpected = (inventory["unexpectedFiles"]
                  + inventory["unexpectedDirectories"])
    if unexpected:
        raise ContextError(
            "context output contains unowned or stale artifacts: "
            + ", ".join(unexpected)
            + "; preserve them for review and remove only with explicit owner approval")


def apply_context(root: pathlib.Path) -> dict[str, Any]:
    output, files = desired_files(root)
    inside(root, output, "context output")
    if output.exists() and not output.is_dir():
        raise ContextError(f"context output is not a regular directory: {output}")
    reject_unexpected_inventory(output, files)
    output.mkdir(parents=True, exist_ok=True)
    for relative, content in sorted(files.items()):
        target = inside(output, output / relative, "context artifact")
        if target.exists() and not target.is_file():
            raise ContextError(f"context artifact is not a regular file: {target}")
        if not target.exists() or target.read_bytes() != content:
            write_atomic(target, content)
    return {
        "status": "applied",
        "authority": "derived-non-normative",
        "output": output.relative_to(root).as_posix(),
        "files": sorted(files),
    }


def validate_context(root: pathlib.Path) -> dict[str, Any]:
    contract = read_object(CONTRACT_PATH, "agent context contract")
    output_relative = pathlib.PurePosixPath(str(contract.get("outputDirectory") or ""))
    output = inside(root, root / pathlib.Path(*output_relative.parts), "context output")
    if not output.is_dir():
        raise ContextError("generated context directory is missing or unsafe")
    index_path = inside(output, output / "index.json", "agent context index")
    index = read_object(index_path, "agent context index")
    if (index.get("version") != 1
            or index.get("authority") != "derived-non-normative"
            or index.get("unsupportedClaims") != 0):
        raise ContextError("agent context index authority or version is invalid")
    contract_binding = index.get("contract") or {}
    if contract_binding.get("sha256") != sha256_file(CONTRACT_PATH):
        raise ContextError("agent context template changed; regenerate the derived index")
    claims = index.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ContextError("agent context index has no observed claims")
    claim_ids: set[str] = set()
    required = {"id", "topic", "condition", "value", "sourcePath",
                "sourceSha256", "trustClass"}
    for row in claims:
        if not isinstance(row, dict) or not required <= set(row):
            raise ContextError("agent context claim is malformed")
        if row.get("trustClass") != "observed":
            raise ContextError("unapproved inferred context is forbidden")
        source_relative = pathlib.PurePosixPath(str(row.get("sourcePath") or ""))
        if source_relative.is_absolute() or ".." in source_relative.parts:
            raise ContextError(f"context source path escapes the project: {source_relative}")
        source = inside(root, root / pathlib.Path(*source_relative.parts), "context source")
        if not source.is_file():
            raise ContextError(f"context source is missing or unsafe: {source_relative}")
        if sha256_file(source) != row.get("sourceSha256"):
            raise ContextError(f"context source is stale: {source_relative}")
        claim_id = str(row.get("id") or "")
        if not claim_id or claim_id in claim_ids:
            raise ContextError("context claim ids must be nonempty and unique")
        claim_ids.add(claim_id)
    modules = index.get("modules")
    if not isinstance(modules, list):
        raise ContextError("agent context module inventory is malformed")
    for row in modules:
        if not isinstance(row, dict):
            raise ContextError("agent context module entry is malformed")
        relative = pathlib.PurePosixPath(str(row.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ContextError(f"context module escapes the output directory: {relative}")
        module = inside(output, output / pathlib.Path(*relative.parts), "context module")
        if not module.is_file():
            raise ContextError(f"context module is missing or unsafe: {relative}")
        if sha256_file(module) != row.get("sha256"):
            raise ContextError(f"context module changed without regeneration: {relative}")
        if not set(row.get("claimIds") or []) <= claim_ids:
            raise ContextError(f"context module references unknown claims: {relative}")
    _, expected = desired_files(root)
    inventory = exact_inventory(output, set(expected))
    if any(inventory.values()):
        raise ContextError("generated context inventory drifted: "
                           + json.dumps(inventory, sort_keys=True))
    for relative, content in expected.items():
        actual = output / relative
        if not actual.is_file() or actual.read_bytes() != content:
            raise ContextError(f"generated context drifted: {relative}")
    return {
        "status": "valid",
        "authority": "derived-non-normative",
        "claims": len(claims),
        "modules": len(modules),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan/apply/validate source-backed derived project context.")
    parser.add_argument("action", choices=("plan", "apply", "validate"))
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--approved", action="store_true",
                        help="assert explicit approval of the shown /adopt write plan")
    parser.add_argument(
        "--plan-sha256",
        help="bind approved apply to the exact planSha256 emitted by plan")
    args = parser.parse_args()
    try:
        root = args.root.expanduser().resolve()
        if not root.is_dir():
            raise ContextError(f"project root does not exist: {root}")
        if args.action == "apply" and not args.approved:
            raise ContextError(
                "apply requires --approved after the user accepts the /adopt plan")
        current_plan = plan_context(root)
        if (args.action == "apply" and args.plan_sha256
                and args.plan_sha256 != current_plan["planSha256"]):
            raise ContextError(
                "approved plan digest is stale; show the new exact plan before applying")
        if args.action == "plan":
            result = current_plan
        elif args.action == "apply":
            result = apply_context(root)
        else:
            result = validate_context(root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContextError, OSError) as exc:
        print(json.dumps({
            "status": "FAILED",
            "why": str(exc),
            "fix": "repair the observed source/path or rerun approved context generation",
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
