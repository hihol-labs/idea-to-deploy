#!/usr/bin/env python3
"""Root-bounded, provider-neutral semantic navigation.

Python uses the standard-library AST. TypeScript support intentionally covers
common top-level declarations and identifier call/reference sites; its
confidence is therefore declared as medium. Unsupported or unparseable input
falls back to honestly labelled literal search.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 50_000_000
MAX_FILES = 5_000
MAX_ENTRIES = 6_000
MAX_RESULTS = 500
IGNORED_PARTS = {
    ".git", ".itd-memory", ".mypy_cache", ".pytest_cache", ".tox", ".venv",
    "__pycache__", "build", "dist", "node_modules", "venv",
}
EXTENSIONS = {"python": {".py"}, "typescript": {".ts", ".tsx"}}
OPERATIONS = {"definitions", "references", "outline"}
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
TS_DECLARATION = re.compile(
    r"^\s*(?:(?:export|declare|default|async|abstract)\s+)*"
    r"(?:(function|class|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*))"
)


class NavigationError(RuntimeError):
    pass


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def read_atomic(path: Path, root: Path) -> tuple[str | None, str | None]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None, f"unreadable:{path.relative_to(root).as_posix()}"
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_FILE_BYTES:
            return None, f"nonregular-or-oversize:{path.relative_to(root).as_posix()}"
        resolved = path.resolve(strict=True)
        current = os.stat(path, follow_symlinks=False)
        if (not inside(resolved, root)
                or not stat.S_ISREG(current.st_mode)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
            return None, f"containment-race:{path.relative_to(root).as_posix()}"
        chunks: list[bytes] = []
        observed = 0
        while observed <= MAX_FILE_BYTES:
            chunk = os.read(descriptor, min(65_536, MAX_FILE_BYTES + 1 - observed))
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        if observed > MAX_FILE_BYTES:
            return None, f"grew-oversize:{path.relative_to(root).as_posix()}"
        try:
            return b"".join(chunks).decode("utf-8"), None
        except UnicodeDecodeError:
            return None, f"invalid-utf8:{path.relative_to(root).as_posix()}"
    finally:
        os.close(descriptor)


def source_files(root: Path, language: str | None = None) -> tuple[list[tuple[Path, str]], list[str]]:
    suffixes = EXTENSIONS.get(language or "")
    files: list[tuple[Path, str]] = []
    warnings: list[str] = []
    total_bytes = 0
    entries_seen = 0
    directories = [root]
    while directories:
        current = directories.pop()
        bounded_entries: list[tuple[str, Path, bool]] = []
        try:
            iterator = os.scandir(current)
        except OSError:
            warnings.append(f"unreadable-directory:{current.relative_to(root).as_posix()}")
            continue
        with iterator:
            for entry in iterator:
                entries_seen += 1
                if entries_seen > MAX_ENTRIES:
                    warnings.append(f"corpus-entry-limit:{MAX_ENTRIES}")
                    return files, warnings
                path = Path(entry.path)
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    warnings.append(f"unreadable:{path.relative_to(root).as_posix()}")
                    continue
                if is_directory and entry.name not in IGNORED_PARTS:
                    bounded_entries.append((entry.name, path, True))
                elif is_file:
                    bounded_entries.append((entry.name, path, False))
                elif entry.is_symlink():
                    warnings.append(f"symlink-skipped:{path.relative_to(root).as_posix()}")
        child_directories: list[Path] = []
        for name, path, is_directory in sorted(bounded_entries):
            if is_directory:
                child_directories.append(path)
                continue
            try:
                resolved = path.resolve(strict=True)
                size = resolved.stat().st_size
            except OSError:
                warnings.append(f"unreadable:{path.relative_to(root).as_posix()}")
                continue
            if not inside(resolved, root):
                warnings.append(f"outside-root-skipped:{path.relative_to(root).as_posix()}")
                continue
            if suffixes is not None and resolved.suffix.lower() not in suffixes:
                continue
            if size > MAX_FILE_BYTES:
                warnings.append(f"oversize-skipped:{path.relative_to(root).as_posix()}")
                continue
            if len(files) >= MAX_FILES:
                warnings.append(f"corpus-file-limit:{MAX_FILES}")
                return files, warnings
            text, warning = read_atomic(path, root)
            if warning:
                warnings.append(warning)
                continue
            assert text is not None
            observed_size = len(text.encode("utf-8"))
            if total_bytes + observed_size > MAX_TOTAL_BYTES:
                warnings.append(f"corpus-byte-limit:{MAX_TOTAL_BYTES}")
                return files, warnings
            files.append((resolved, text))
            total_bytes += observed_size
        directories.extend(reversed(child_directories))
    return files, warnings


def has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def add_result(results: list[dict[str, Any]], priority: list[dict[str, Any]],
               item: dict[str, Any], operation: str, query_symbol: str,
               warnings: list[str]) -> None:
    destination = (priority if operation == "outline"
                   and item["symbol"] == query_symbol else results)
    if len(destination) < MAX_RESULTS:
        destination.append(item)
    elif "result-limit" not in warnings:
        warnings.append("result-limit")


def row(root: Path, path: Path, line: int, column: int, kind: str,
        symbol: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "line": line,
        "column": column,
        "kind": kind,
        "symbol": symbol,
    }


def python_definition_nodes(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    found: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append((node.name, node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    found.append((target.id, target))
    return found


def python_results(
    root: Path, operation: str, symbol: str
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    results: list[dict[str, Any]] = []
    priority: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    paths, warnings = source_files(root, "python")
    for path, text in paths:
        try:
            tree = ast.parse(text, filename=path.as_posix())
        except SyntaxError:
            parse_errors.append(path.relative_to(root).as_posix())
            continue
        definitions = python_definition_nodes(tree)
        if operation == "definitions":
            for name, node in definitions:
                if name == symbol:
                    add_result(results, priority, row(
                        root, path, node.lineno, node.col_offset + 1,
                        "definition", name), operation, symbol, warnings)
        elif operation == "references":
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == symbol:
                    add_result(results, priority, row(
                        root, path, node.lineno, node.col_offset + 1,
                        "reference", node.id), operation, symbol, warnings)
        else:
            for name, node in definitions:
                add_result(results, priority, row(
                    root, path, node.lineno, node.col_offset + 1,
                    "symbol", name), operation, symbol, warnings)
    return priority + results, parse_errors, warnings


def strip_typescript(text: str) -> tuple[list[str], bool]:
    """Mask strings/comments while preserving lines and identifier columns."""
    output: list[str] = []
    block_comment = False
    balanced = {"{": 0, "(": 0, "[": 0}
    pairs = {"}": "{", ")": "(", "]": "["}
    for raw in text.splitlines():
        chars = list(raw)
        i = 0
        quote = ""
        while i < len(chars):
            if block_comment:
                end = raw.find("*/", i)
                if end < 0:
                    for pos in range(i, len(chars)):
                        chars[pos] = " "
                    i = len(chars)
                    continue
                for pos in range(i, end + 2):
                    chars[pos] = " "
                block_comment = False
                i = end + 2
                continue
            if quote:
                chars[i] = " "
                if raw[i] == "\\" and i + 1 < len(chars):
                    chars[i + 1] = " "
                    i += 2
                    continue
                if raw[i] == quote:
                    quote = ""
                i += 1
                continue
            if raw.startswith("//", i):
                for pos in range(i, len(chars)):
                    chars[pos] = " "
                break
            if raw.startswith("/*", i):
                chars[i] = chars[i + 1] = " "
                block_comment = True
                i += 2
                continue
            if raw[i] in {"'", '"', "`"}:
                quote = raw[i]
                chars[i] = " "
                i += 1
                continue
            if raw[i] in balanced:
                balanced[raw[i]] += 1
            elif raw[i] in pairs:
                opener = pairs[raw[i]]
                balanced[opener] -= 1
                if balanced[opener] < 0:
                    return output + ["".join(chars)], False
            i += 1
        output.append("".join(chars))
        if quote:
            return output, False
    return output, not block_comment and all(value == 0 for value in balanced.values())


def typescript_results(root: Path, operation: str,
                       symbol: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    results: list[dict[str, Any]] = []
    priority: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    token = re.compile(rf"(?<![\w$]){re.escape(symbol)}(?![\w$])")
    paths, warnings = source_files(root, "typescript")
    for path, text in paths:
        lines, balanced = strip_typescript(text)
        if not balanced:
            parse_errors.append(path.relative_to(root).as_posix())
            continue
        declarations: list[tuple[str, int, int, tuple[int, int]]] = []
        brace_depth = 0
        for line_number, line in enumerate(lines, 1):
            match = TS_DECLARATION.match(line)
            if match and brace_depth == 0:
                name = match.group(2) or match.group(3)
                start, end = match.span(2) if match.group(2) else match.span(3)
                declarations.append((name, line_number, start + 1, (start, end)))
            brace_depth += line.count("{") - line.count("}")
        if operation == "definitions":
            for name, line_number, column, _ in declarations:
                if name == symbol:
                    add_result(results, priority, row(
                        root, path, line_number, column,
                        "definition", name), operation, symbol, warnings)
        elif operation == "references":
            declaration_spans = {(line_number, span) for name, line_number, _, span
                                 in declarations if name == symbol}
            for line_number, line in enumerate(lines, 1):
                for match in token.finditer(line):
                    if any(number == line_number and start <= match.start() < end
                           for number, (start, end) in declaration_spans):
                        continue
                    add_result(results, priority, row(
                        root, path, line_number, match.start() + 1,
                        "reference", symbol), operation, symbol, warnings)
        else:
            for name, line_number, column, _ in declarations:
                add_result(results, priority, row(
                    root, path, line_number, column, "symbol", name),
                    operation, symbol, warnings)
    return priority + results, parse_errors, warnings


def textual_results(root: Path, symbol: str) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    paths, warnings = source_files(root)
    for path, text in paths:
        for line_number, line in enumerate(text.splitlines(), 1):
            start = 0
            while len(results) < MAX_RESULTS:
                column = line.find(symbol, start)
                if column < 0:
                    break
                results.append(row(root, path, line_number, column + 1,
                                   "textual-match", symbol))
                start = column + max(1, len(symbol))
            if len(results) >= MAX_RESULTS:
                if "result-limit" not in warnings:
                    warnings.append("result-limit")
                return results, warnings
    return results, warnings


def payload(root: Path, language: str, operation: str, symbol: str) -> dict[str, Any]:
    if language == "python":
        results, parse_errors, scan_warnings = python_results(
            root, operation, symbol)
        confidence = "high"
        coverage = "Python 3 syntax accepted by the running stdlib ast parser"
    elif language == "typescript":
        results, parse_errors, scan_warnings = typescript_results(
            root, operation, symbol)
        confidence = "medium"
        coverage = "top-level function/class/interface/type/enum/namespace and variable declarations; identifier references"
    else:
        textual, textual_warnings = textual_results(root, symbol)
        return {
            "version": 1,
            "language": language,
            "operation": operation,
            "symbol": symbol,
            "semantic": False,
            "confidence": "textual",
            "coverage": "literal UTF-8 search in root-bounded regular files",
            "results": textual,
            "warnings": ["unsupported-language-textual-fallback", *textual_warnings],
        }
    hard_errors = [
        warning for warning in scan_warnings
        if not warning.startswith((
            "corpus-", "oversize-", "outside-root-", "symlink-skipped:"
        ))
        and warning != "result-limit"
    ]
    if hard_errors or (parse_errors and not results):
        textual, textual_warnings = textual_results(root, symbol)
        return {
            "version": 1,
            "language": language,
            "operation": operation,
            "symbol": symbol,
            "semantic": False,
            "confidence": "textual",
            "coverage": coverage,
            "results": textual,
            "warnings": [
                "parse-or-read-failure-textual-fallback",
                *parse_errors,
                *scan_warnings,
                *[warning for warning in textual_warnings
                  if warning not in scan_warnings],
            ],
        }
    warnings = ([f"skipped-unparseable:{path}" for path in parse_errors]
                if parse_errors else []) + scan_warnings
    if parse_errors or scan_warnings:
        confidence = "medium"
    ordered = sorted(results, key=lambda item: (
        0 if operation == "outline" and item["symbol"] == symbol else 1,
        item["path"], item["line"], item["column"], item["kind"], item["symbol"]
    ))
    return {
        "version": 1,
        "language": language,
        "operation": operation,
        "symbol": symbol,
        "semantic": True,
        "confidence": confidence,
        "coverage": coverage,
        "results": ordered[:MAX_RESULTS],
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provider-neutral semantic navigation")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--language", required=True)
    parser.add_argument("--operation", required=True, choices=sorted(OPERATIONS))
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args(argv)
    try:
        if has_symlink_component(args.root):
            raise NavigationError("root path must not contain symlink components")
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise NavigationError("root must be a directory")
        if not args.symbol or "\x00" in args.symbol:
            raise NavigationError("symbol must be non-empty and contain no NUL")
        if args.language in EXTENSIONS and not IDENTIFIER.fullmatch(args.symbol):
            raise NavigationError("semantic queries require a valid identifier")
        print(json.dumps(payload(root, args.language.lower(), args.operation,
                                 args.symbol), ensure_ascii=False, sort_keys=True))
        return 0
    except (NavigationError, OSError) as exc:
        print(json.dumps({"status": "UNVERIFIED", "why": str(exc),
                          "fix": "Use an existing directory root and a valid query."},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
