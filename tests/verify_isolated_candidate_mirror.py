#!/usr/bin/env python3
"""Зеркало обязано быть зелёным ВНУТРИ изолированного staged-tree кандидата.

Почему отдельный оракул. Машинный продюсер `itd_verification_loop.py machine`
всегда исполняет запечатанную команду в режиме `isolated-staged-tree`, то есть
в клоне вне рабочего чекаута. Хостовый прогон зеркала этого не проверяет: он
идёт по чекауту, где живут host-owned входы, кэш и накопленное состояние. Пока
разрыв между двумя местами не измеряется, любая красная строка внутри кандидата
всплывает только в момент чеканки квитанции — и обездвиживает сразу все гейты,
которым эта квитанция нужна (переход юнита, кэш ревью, гейт коммита, профиль
реестра). Ровно это и случилось 2026-09-10: `verify_review_broker` падал внутри
кандидата, а стандартный хостовый прогон был зелёным.

Что именно проверяется: последняя строка `bash tests/run-all.sh --quick`,
исполненного внутри материализованного изолированного кандидата, совпадает
БАЙТ В БАЙТ с запечатанной строкой `EXPECTED_LAST_LINE`. Строка не «зелёная
вообще», а именно ожидаемая: `verify_reviewer_provider_freshness` красен по
построению (его улика — живой пин свежести провайдера), и молча считать его
зелёным было бы ложным зелёным.

Оракул НЕ входит в зеркало (иначе рекурсия) — он объявлен классом
`mirror-runner` в `tests/OUT_OF_MIRROR.json`.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Запечатанная строка кандидата. `verify_reviewer_provider_freshness` красен по
# построению: его вход — живой пин свежести провайдера, которого в дереве нет.
EXPECTED_LAST_LINE = "DONE fails: verify_reviewer_provider_freshness"
# Кандидат материализуется ВНЕ репозитория: внутри `.itd-memory/` он делает
# `verify_host_neutral_memory` красным (замер 2026-09-10), то есть оракул
# ловил бы собственную площадку, а не дефект кандидата.
DEFAULT_CANDIDATE_ROOT = pathlib.Path.home() / ".cache" / "itd-isolated-tmp"
# Площадка уникальна на процесс: путь один и тот же делали бы два прогона
# сразу (хостовый и вложенный внутри машинной квитанции), и они сносили бы
# каталог друг у друга - `Directory not empty` вместо вердикта о кандидате.
CANDIDATE_NAME = f"verify-isolated-candidate-mirror-{os.getpid()}"
# Сьют, ради которого оракул и написан: если он выпадет из зеркала, проверка
# станет пустой (последняя строка сойдётся, а гарантии не будет).
REQUIRED_IN_MIRROR = "verify_review_broker"
SELF_SUITE = "verify_isolated_candidate_mirror"
MIRROR_TIMEOUT_SECONDS = 1800


def fail(why: str, fix: str) -> int:
    print(f"FAIL isolated candidate mirror\n  WHY: {why}\n  FIX: {fix}")
    return 1


def candidate_root() -> pathlib.Path:
    raw = os.environ.get("ITD_ISOLATED_CANDIDATE_ROOT")
    return pathlib.Path(raw).expanduser() if raw else DEFAULT_CANDIDATE_ROOT


def materialise(destination: pathlib.Path) -> str:
    """Клон текущего ИНДЕКСА: тот же кандидат, что видит машинный продюсер."""
    tree = subprocess.run(
        ["git", "write-tree"], cwd=ROOT, text=True, check=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--shared", "--no-checkout", "--quiet",
         str(ROOT), str(destination)],
        check=True,
    )
    subprocess.run(
        ["git", "read-tree", "--reset", "-u", tree], cwd=destination, check=True
    )
    # Host-owned входы не лежат в дереве (`.itd-memory/` git-ignored), но и не
    # являются содержимым кандидата: без них сьюты с хостовым пином красны по
    # отсутствию входа, а не по дефекту. Продюсер снабжает кандидата тем же.
    host_inputs = ROOT / ".itd-memory" / "host-inputs"
    if host_inputs.is_dir():
        shutil.copytree(
            host_inputs, destination / ".itd-memory" / "host-inputs",
            dirs_exist_ok=True,
        )
    return tree


def mirror_suites(runner: pathlib.Path) -> str:
    return runner.read_text(encoding="utf-8")


def suite_list(runner_text: str, name: str) -> list[str]:
    """Точный список сьютов из присваивания `NAME="..."` в tests/run-all.sh.

    Поиск подстроки здесь был бы ложной гарантией: имя `verify_review_broker`
    содержится и в `verify_review_broker_policy`, и в комментариях, поэтому
    сьют мог бы покинуть исполняемый набор, а проверка осталась бы зелёной
    (находка независимого ревьюера). Членство проверяется по ТОКЕНАМ реального
    присваивания, а его согласованность с тем, что зеркало действительно
    прогнало, дополнительно сверяется со строкой MIRROR-COVERAGE.
    """
    matches = re.findall(rf'(?m)^{name}="([^"]*)"', runner_text)
    # Ровно одно присваивание. Bash исполняет ПОСЛЕДНЕЕ, а разбор по первому
    # принял бы набор, который не исполняется: переприсваивание такого же
    # размера без нужного сьюта прошло бы и проверку членства, и сверку по
    # числу (находка независимого ревьюера). Неоднозначность - отказ.
    if len(matches) != 1:
        return []
    return matches[0].split()


def main() -> int:
    runner_text = mirror_suites(ROOT / "tests" / "run-all.sh")
    core = suite_list(runner_text, "CORE")
    full = suite_list(runner_text, "FULL")
    if not core:
        return fail(
            "в tests/run-all.sh не найдено присваивание CORE=\"…\", поэтому "
            "исполняемый набор быстрого профиля неизвестен",
            "верни присваивание в прежней форме или перепиши разбор в этом "
            "оракуле под новую форму — молча доверять последней строке нельзя",
        )
    if REQUIRED_IN_MIRROR not in core:
        return fail(
            f"{REQUIRED_IN_MIRROR} отсутствует в исполняемом наборе CORE, "
            "поэтому совпадение последней строки ничего не гарантировало бы",
            f"верни {REQUIRED_IN_MIRROR} в CORE или перепиши этот оракул под "
            "сьют, который действительно ловит дефект",
        )
    # Гард рекурсии намеренно шире разбора наборов: зеркало гоняет сьюты не
    # только из CORE/FULL, но и хвостовыми проверками (`run_tail`, что прямо
    # признано в tests/OUT_OF_MIRROR.json). Через такой путь оракул запустил бы
    # сам себя, и вместо контролируемого отказа вышла бы неограниченная
    # рекурсия (находка независимого ревьюера). Поэтому здесь достаточно
    # УПОМИНАНИЯ имени где угодно в раннере - fail-closed в сторону отказа.
    if SELF_SUITE in runner_text:
        return fail(
            f"имя {SELF_SUITE} встречается в tests/run-all.sh, а этот оракул сам "
            "запускает зеркало — любой путь запуска (CORE, FULL или хвостовые "
            "проверки) сделал бы прогон рекурсивным",
            f"убери {SELF_SUITE} из раннера целиком; его место — класс "
            "mirror-runner в tests/OUT_OF_MIRROR.json",
        )

    destination = candidate_root() / CANDIDATE_NAME
    try:
        destination.resolve().relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        return fail(
            f"кандидат материализуется внутри репозитория: {destination}",
            "укажи ITD_ISOLATED_CANDIDATE_ROOT вне рабочего дерева "
            f"(по умолчанию {DEFAULT_CANDIDATE_ROOT})",
        )

    tree = materialise(destination)
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        TMPDIR=str(candidate_root()),
    )
    # Ограниченное время: без него отказ мог бы стать не отказом, а вечным
    # ожиданием. Быстрый профиль на этом хосте укладывается в ~4 минуты.
    try:
        completed = subprocess.run(
            ["bash", "tests/run-all.sh", "--quick"], cwd=destination, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=MIRROR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as expired:
        # `TimeoutExpired.output` документирован как БАЙТЫ даже при text=True,
        # поэтому прямая запись подменила бы осмысленный отказ на TypeError
        # (находка независимого ревьюера).
        captured = expired.output
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", errors="replace")
        (destination / "isolated-mirror.log").write_text(
            captured or "", encoding="utf-8"
        )
        return fail(
            f"зеркало внутри кандидата {tree[:12]} не уложилось в "
            f"{MIRROR_TIMEOUT_SECONDS} секунд",
            f"разбери хвост в {destination / 'isolated-mirror.log'}; молчаливое "
            "ожидание здесь было бы хуже красного вердикта",
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    log = destination / "isolated-mirror.log"
    log.write_text(completed.stdout, encoding="utf-8")
    # Разбор присваивания и фактический прогон обязаны сойтись по числу: свою
    # границу покрытия зеркало печатает само, и расхождение означает, что этот
    # оракул рассуждает о другом наборе, чем исполнился.
    expected_ran = sum(1 for suite in core if suite.startswith("verify_"))
    coverage = re.search(
        r"(?m)^MIRROR-COVERAGE: (\d+) of \d+ tests/verify_\*\.py run here "
        r"\(quick profile\)$",
        completed.stdout,
    )
    if coverage is None or int(coverage.group(1)) != expected_ran:
        observed = coverage.group(1) if coverage else "строка отсутствует"
        return fail(
            f"зеркало отчиталось о покрытии {observed}, а разобранный CORE даёт "
            f"{expected_ran} сьютов — оракул рассуждает не о том наборе, который "
            "исполнился",
            f"сверь присваивание CORE и печать MIRROR-COVERAGE в {log}; пока "
            "они расходятся, совпадение последней строки не является уликой",
        )
    if last != EXPECTED_LAST_LINE:
        return fail(
            f"последняя строка зеркала внутри кандидата {tree[:12]} — {last!r}, "
            f"а запечатана {EXPECTED_LAST_LINE!r}",
            f"разбери красные сьюты в {log}; зелёный хостовый прогон того же "
            "дерева НЕ является ответом — расхождение и есть предмет проверки",
        )
    print(json.dumps({
        "status": "PASSED",
        "tree": tree,
        "candidate": str(destination),
        "lastLine": last,
    }, sort_keys=True))
    # Зелёную площадку убираем: она больше не улика, а красную оставляем -
    # её лог назван в тексте отказа выше.
    shutil.rmtree(destination, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
