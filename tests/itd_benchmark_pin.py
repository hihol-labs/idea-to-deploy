"""Единственный источник правды пина live-бенчмарка (LPD-003-2).

До этого юнита пин хешировал десять корней целиком (~231 файл), а бенчмарк
исполнял малую долю: замер по 52 записанным транскриптам успешных прогонов
дал 19 структурно читаемых/исполняемых файлов (артефакт замера —
`.itd-memory/measurements/LPD003-2-transcript-impact.json`; метод: только
события command_execution, листинги ls/find/tree не считаются чтением).
Каждая правка вне исполняемой поверхности инвалидировала evidence и требовала
~10-минутного живого прогона — шесть ложных инвалидаций за одну сессию
(записанное трение, feedback 2026-08-12).

Пин сужен до ИЗМЕРЕННОГО влияния. Набор ниже — объединение двух источников,
и у каждого элемента записана причина:

- static: prepare_adopted_project вшивает файл в исполняемые артефакты
  проекта (шаблоны .itd, codex-хуки и их диспетчер, AGENTS-шаблон, манифесты
  плагина, host-adapter контракт, идущий в промпт ноги);
- dynamic: путь структурно читался/исполнялся в записанных транскриптах.

Оба потребителя (раннер и оракул) импортируют ЭТОТ модуль: две копии списка
расходились бы молча — класс дефекта, дважды пойманный ревьюером в LPD-003-3.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

# причина -> кортеж корней (файл или каталог, repo-relative POSIX)
BENCHMARK_PIN_REASONS: dict[str, tuple[str, ...]] = {
    "static": (
        "AGENTS.md",
        ".claude-plugin",
        ".codex-plugin",
        "docs/templates/itd",
        "docs/templates/itd-memory",
        "docs/HOST_ADAPTER_CONTRACT.md",
        "docs/host-adapters.json",
        "skills/adopt/references/agents-md-template.md",
        "skills/adopt/references/codex-project-hooks.json",
        "hooks/codex-dispatch.py",
    ),
    "dynamic": (
        "skills/blueprint",
        "agents/devils-advocate.md",
        "skills/_shared/subagent-contract.md",
        "skills/_shared/itd_operating_loops.py",
        "skills/_shared/itd_unit_lifecycle.py",
        "hooks/validate_state_core.py",
        "hooks/wip-gate.sh",
        "scripts/validate_state.py",
    ),
}

BENCHMARK_PIN_ROOTS: tuple[str, ...] = tuple(
    root for roots in BENCHMARK_PIN_REASONS.values() for root in roots
)


def _git_ignored(root: Path, relatives: list[str]) -> set[str]:
    if not relatives:
        return set()
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"], cwd=root,
        input="\0".join(relatives).encode("utf-8") + b"\0",
        capture_output=True, timeout=60,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            "git check-ignore failed while pinning the methodology tree: "
            + result.stderr.decode("utf-8", errors="replace").strip()[:200]
        )
    return {item for item in result.stdout.decode("utf-8").split("\0") if item}


def pinned_files(root: Path) -> list[Path]:
    """Файлы пина в детерминированном порядке; git-ignored исключены."""
    files: list[Path] = []
    for raw in BENCHMARK_PIN_ROOTS:
        path = root / raw
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*")
                         if candidate.is_file()
                         and "__pycache__" not in candidate.parts
                         and candidate.suffix != ".pyc")
    ignored = _git_ignored(
        root, [path.relative_to(root).as_posix() for path in files])
    files = [path for path in files
             if path.relative_to(root).as_posix() not in ignored]
    return sorted(set(files), key=lambda item: item.relative_to(root).as_posix())


def tree_sha256(root: Path) -> str:
    """Контентный хеш пин-набора (length-prefixed путь+содержимое, как раньше)."""
    digest = hashlib.sha256()
    for path in pinned_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()
