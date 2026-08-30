#!/usr/bin/env python3
"""itd_verdict_taxonomy.py — закрытые словари схемы вердикта (PILOT P0-1).

Единственная реализация «принять или отклонить запись» для ОБОИХ писателей
review-findings ledger:
  * hooks/verdict-contract.sh        — вердикты субагентов;
  * skills/retro/scripts/itd_review_import.py — внешние GitHub-ревью.
Читатель (skills/retro/scripts/itd_retro_scan.py) берёт отсюда же legacyMapping
и счётчик отклонённых.

Инварианты (ADVISORY-RSI-2026-08-27-v4 §5 PILOT):
  * словари объявлены ровно в одном месте — VERDICT_TAXONOMY.json рядом;
  * валидация forward-only: записи БЕЗ taxonomy_version не переписываются и не
    проверяются, они нормализуются только на чтении через legacyMapping;
  * отклонение != потеря: невалидная запись целиком уходит в карантин
    review-findings-rejected.jsonl с машиночитаемой причиной, счётчик причин
    ведётся в review-findings-rejected.count.jsonl;
  * недоступный/битый файл словарей — это ПРИЧИНА taxonomy-unavailable, а не
    молчаливый пропуск и не тихая запись в канонический леджер.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TAXONOMY_FILE = "VERDICT_TAXONOMY.json"
FINDINGS_FILE = "review-findings.jsonl"
REJECTED_FILE = "review-findings-rejected.jsonl"
REJECTED_COUNT_FILE = "review-findings-rejected.count.jsonl"
FINDINGS_SOFT_BYTES = 64 * 1024  # bound как у errors.log: на переполнении — хвост
REASON_TAXONOMY_UNAVAILABLE = "taxonomy-unavailable"
REASON_TOO_LARGE = "record:too-large"
MAX_RECORD_BYTES_DEFAULT = 16 * 1024
# Причины, которые говорят о СОСТОЯНИИ ХОСТА, а не о самой записи: при них
# писателю имеет смысл повторить попытку позже. Всё остальное - свойство
# содержимого, повтор ничего не изменит.
TRANSIENT_REASON_PREFIXES = (REASON_TAXONOMY_UNAVAILABLE, "admit-error:")


def is_transient(reasons) -> bool:
    """True, если отказ вызван состоянием хоста и повтор осмыслен."""
    return any(str(r).startswith(TRANSIENT_REASON_PREFIXES)
               for r in (reasons or []))
# Источник-ревьюер: он всегда судит сам, поэтому послабления
# externalOnly к нему не применяются ни при каком словаре.
SOURCE_REVIEWER = "subagent-verdict"


def taxonomy_path() -> Path:
    """Путь к словарям. `hooks/` и `skills/` — сиблинги и в репо, и в установке
    (~/.claude), поэтому один относительный резолв работает в обоих случаях."""
    env = os.environ.get("ITD_VERDICT_TAXONOMY", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / TAXONOMY_FILE


def load_taxonomy(path: Path | None = None):
    """Словари или None. None означает «валидировать нечем» — вызывающий обязан
    отправить запись в карантин, а не принять её и не выбросить."""
    try:
        data = json.loads((path or taxonomy_path()).read_text(encoding="utf-8"))
        # bool — подкласс int в Python, поэтому `taxonomy_version: true`
        # прошёл бы голую isinstance-проверку и был бы проштампован в записи.
        # bool — подкласс int, а 0 и отрицательные значения не являются
        # версией: и то и другое проштамповалось бы в записи как «валидное».
        version = data["taxonomy_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            return None
        for key in ("source", "severity", "category"):
            if not isinstance(data[key]["values"], list) or not data[key]["values"]:
                return None
        for key in ("source", "severity", "category"):
            for v in data[key]["values"]:
                if not isinstance(v, str) or not v.strip():
                    return None
        declared_sources = set(data["source"]["values"])
        for key in ("severity", "category"):
            by = data[key]["bySource"]
            if not isinstance(by, dict) or not by:
                return None
            # Политика обязана существовать для КАЖДОГО объявленного источника
            # и не для посторонних: иначе словарь без записи, например, для
            # manual-entry принимался бы, а писатель с этим источником не имел
            # бы ни одного разрешённого значения — отказ выглядел бы дефектом
            # писателя, а не испорченного словаря.
            if set(by) != declared_sources:
                return None
            # Значения bySource обязаны лежать в объявленном словаре: иначе
            # семантически испорченный файл расширял бы «закрытый» перечень,
            # оставаясь синтаксически валидным. Исключение для не-ревьюеров
            # объявлено ДАННЫМИ (externalOnly), а не зашито в коде.
            declared = set(data[key]["values"])
            external_only = data[key].get("externalOnly") or []
            if not isinstance(external_only, list):
                return None
            # Послабление externalOnly принадлежит ТОЛЬКО не-ревьюерам: иначе
            # словарь, положивший лишнее значение в externalOnly и в
            # bySource.subagent-verdict, расширял бы закрытый перечень ревьюера,
            # оставаясь валидным.
            for value in external_only:
                if not isinstance(value, str) or not value.strip():
                    return None
                if value in declared:
                    return None
            for source_key, allowed in by.items():
                if not isinstance(allowed, list) or not allowed:
                    return None
                permitted = declared
                if source_key != SOURCE_REVIEWER:
                    permitted = declared | set(external_only)
                if not set(allowed) <= permitted:
                    return None
        legacy = data["legacyMapping"]
        for key in ("category", "severity"):
            table = legacy[key]
            if not isinstance(table, dict):
                return None
            # Цель отображения обязана быть значением словаря: иначе чтение
            # легаси возвращало бы строки вне закрытого перечня, и /retro
            # показывал бы как «сведённые» те значения, которых в словаре нет.
            allowed = set(data[key]["values"]) | set(
                data[key].get("externalOnly") or [])
            for source_value, target in table.items():
                # Пустой ключ легитимен: именно так выглядит легаси-severity ""
                # в 13 существующих записях. Проверяется ЦЕЛЬ отображения.
                if not isinstance(source_value, str):
                    return None
                if target not in allowed:
                    return None
        rej_file_raw = data["rejection"]["file"]
        # Именно строка, а не то, что можно привести к строке: `[]` не должен
        # превращаться в имя файла "[]" и молча стать карантином.
        if not isinstance(rej_file_raw, str):
            return None
        rej_file = rej_file_raw.strip()
        # Голое имя файла и заведомо не канонический леджер: иначе испорченный
        # словарь направил бы карантин прямо в приёмный журнал.
        if (not rej_file or rej_file in (FINDINGS_FILE, REJECTED_COUNT_FILE)
                or rej_file != Path(rej_file).name
                or rej_file.startswith(".")):
            return None
        limits = data.get("limits")
        if limits is not None:
            if not isinstance(limits, dict):
                return None
            cap = limits.get("maxRecordBytes")
            # Предел объявляется данными, но не может быть объявлен настолько
            # малым, что ни одна нормальная находка в него не влезет.
            if cap is not None and (isinstance(cap, bool)
                                    or not isinstance(cap, int) or cap < 1024):
                return None
        defaults = data.get("writerDefaults")
        if defaults is not None:
            if not isinstance(defaults, dict):
                return None
            # Значение по умолчанию, недопустимое для своего же источника,
            # обрекало бы писателя на вечный карантин.
            for source_name, values in defaults.items():
                if source_name not in declared_sources:
                    return None
                if not isinstance(values, dict):
                    return None
                if values.get("source") not in (None, source_name):
                    return None
                for key in ("severity", "category"):
                    value = values.get(key)
                    if value is None:
                        continue
                    if value not in data[key]["bySource"].get(source_name, []):
                        return None
        return data
    except Exception:
        return None


def validate_record(rec, tax) -> list:
    """Причины отклонения (пустой список = запись валидна). Причина — короткая
    машиночитаемая строка `поле[индекс]:значение`, чтобы /retro считал классы
    промахов словаря без разбора прозы."""
    reasons = []
    if not isinstance(rec, dict):
        return ["record:not-an-object"]
    src = rec.get("source")
    sources = tax["source"]["values"]
    if not isinstance(src, str) or not src.strip() or src not in sources:
        reasons.append("source:%r" % (src,))
    # Провенанс объявлен как source+lineage (§7): пустой lineage делает запись
    # неотслеживаемой, поэтому он такая же часть схемы, как и source.
    lineage = rec.get("lineage")
    if not isinstance(lineage, str) or not lineage.strip():
        reasons.append("lineage:%r" % (lineage,))
    # Разрешённые значения берутся ТОЛЬКО из bySource: молчаливый откат к
    # глобальному списку означал бы, что битая или неполная таксономия
    # расширяет права источника (глобальный severity содержит unspecified).
    allowed_sev = tax["severity"].get("bySource", {}).get(src)
    categories = tax["category"].get("bySource", {}).get(src)
    if not allowed_sev or not categories:
        reasons.append("taxonomy:bySource-missing-for:%r" % (src,))
        allowed_sev, categories = [], []
    findings = rec.get("findings")
    if not isinstance(findings, list):
        return reasons + ["findings:not-a-list"]
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            reasons.append("finding[%d]:not-an-object" % i)
            continue
        sev = f.get("severity")
        cat = f.get("category")
        if sev not in allowed_sev:
            reasons.append("severity[%d]:%r" % (i, sev))
        if cat not in categories:
            reasons.append("category[%d]:%r" % (i, cat))
    return reasons


def ledger_dir(cwd: str) -> Path:
    """Проектный .itd-memory, иначе глобальный tmp-леджер (как SKILL_BYPASS)."""
    if cwd:
        mem = Path(cwd) / ".itd-memory"
        if mem.is_dir():
            return mem
    return Path(tempfile.gettempdir())


def _name(directory: Path, base: str) -> Path:
    """В tmp-фоллбэке имена префиксуются claude-, как у писателя v1.86."""
    if directory == Path(tempfile.gettempdir()):
        return directory / ("claude-" + base)
    return directory / base


def _dir(cwd: str, directory=None) -> Path:
    """Каталог леджера: явный (импортёр знает свой `--dir`) или выведенный из
    cwd (хук знает только проект)."""
    return Path(directory) if directory else ledger_dir(cwd)


def canonical_path(cwd: str, directory=None) -> Path:
    return _name(_dir(cwd, directory), FINDINGS_FILE)


def rejected_path(cwd: str, tax=None, directory=None) -> Path:
    base = REJECTED_FILE
    if tax:
        base = str(tax.get("rejection", {}).get("file") or REJECTED_FILE)
    return _name(_dir(cwd, directory), base)


def rejected_count_path(cwd: str, directory=None) -> Path:
    return _name(_dir(cwd, directory), REJECTED_COUNT_FILE)


def _size_or_zero(path: Path) -> int:
    """Размер файла или 0, если его уже отротировал параллельный писатель."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _rotate_oversized(path: Path) -> None:
    """Отротировать переполненный леджер атомарным переименованием в свободное
    поколение. Отдельная функция, а не ветка внутри записи, потому что её
    поведение — часть контракта («ничего не теряется, канонический путь на
    месте, чужая гонка не отменяет запись») и должно проверяться напрямую, а
    не через удачно случившуюся гонку."""
    for generation in range(1, 1000):
        candidate = path.with_name("%s.%d" % (path.name, generation))
        try:
            claim = os.open(str(candidate),
                            os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        except OSError:
            return
        os.close(claim)
        try:
            os.replace(path, candidate)
        except OSError:
            # Переименование НЕ состоялось: заявка пуста, её можно снять.
            # Кто-то отротировал раньше; запись уже дописана и durable,
            # ротация — только уборка, поэтому её сбой не станет отказом.
            try:
                candidate.unlink()
            except OSError:
                pass
            return
        # Дальше candidate содержит ВЕСЬ леджер, и удалять его нельзя ни при
        # какой ошибке: отдельный try, иначе неудача пересоздания (ENOSPC)
        # стирала бы историю, которую ротация только что сохранила.
        try:
            # Канонический путь обязан существовать сразу после ротации:
            # потребитель, читающий только его, иначе увидел бы «леджера нет»
            # вместо «леджер пуст, история в поколениях».
            os.close(os.open(str(path), os.O_CREAT | os.O_WRONLY, 0o600))
        except OSError:
            pass
        return


def _append_bounded(path: Path, line: str) -> None:
    """Дописать строку и, при переполнении, ОТРОТИРОВАТЬ файл, а не обрезать
    его. Обрезание удаляло бы легаси-записи, которые контракт обещает не
    трогать; ротация сохраняет их в соседнем поколении."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if _size_or_zero(path) > FINDINGS_SOFT_BYTES:
        _rotate_oversized(path)


def bump_rejected_counter(cwd: str, reasons, directory=None,
                          identity: str = "") -> None:
    """Счётчик отклонённых переживает урезание карантина по размеру, поэтому он
    отдельный файл. Форма — append-only JSONL: у записи НЕТ фазы
    read-modify-write, поэтому два писателя (хук и импортёр) не могут ни
    затереть общий tmp, ни потерять обновление друг друга. Агрегат считает
    читатель (`rejected_summary`)."""
    p = rejected_count_path(cwd, directory)
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reasons": [str(r) for r in (reasons or ["unspecified"])],
        "identity": identity,
    }, ensure_ascii=False)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _identity_present(path: Path, identity: str) -> bool:
    """Есть ли уже такая пара (запись, классы причин) в текущем поколении.
    Поиск по подстроке достаточен: identity — шестнадцатеричный дайджест."""
    try:
        return identity in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def reject(cwd: str, rec, reasons, tax=None, directory=None) -> Path:
    """Запись не принята — но и не потеряна: целиком уходит в карантин."""
    path = rejected_path(cwd, tax, directory)
    classes = sorted({str(r).split(":", 1)[0].split("[", 1)[0]
                      for r in (reasons or [])})
    try:
        payload = json.dumps(rec, ensure_ascii=False, sort_keys=True, default=repr)
    except Exception:
        payload = repr(rec)
    identity = hashlib.sha256(
        ("|".join(classes) + "\u0000" + payload).encode("utf-8", "replace")).hexdigest()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reasons": list(reasons),
        "identity": identity,
        "record": rec,
    }
    # Идемпотентность: та же запись, отклонённая по тем же классам причин, не
    # дописывается второй раз. Повтор временного отказа (пока чинят словарь)
    # обязан быть возможен, но он не должен раздувать улику и счётчик.
    if _identity_present(path, identity):
        return path
    # Ввод-вывод карантина не имеет права уронить писателя: переполненный или
    # недоступный на запись каталог — это состояние хоста, а не повод сорвать
    # сессию. Отказ уже возвращён вызывающему как результат admit().
    # Карантин никогда не УСЕКАЕТ запись — он и есть улика; размер файла
    # держит та же ротация, что и у канонического леджера.
    # default=repr: reject принимает ЛЮБОЙ вход, включая несериализуемый.
    # Без него сериализация карантина падала бы ровно на той записи, ради
    # сохранения которой карантин и существует.
    try:
        _append_bounded(path, json.dumps(entry, ensure_ascii=False, default=repr))
    except Exception:
        pass
    try:
        bump_rejected_counter(cwd, reasons, directory, identity)
    except Exception:
        pass
    return path


def admit(cwd: str, rec, tax=None, directory=None) -> tuple:
    """Единственная точка записи. Возвращает (accepted: bool, reasons: list).

    Порядок намеренный: сначала словари, потом валидация, и только потом
    канонический леджер. Нет ветки, в которой запись исчезает."""
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None:
        reject(cwd, rec, [REASON_TAXONOMY_UNAVAILABLE], None, directory)
        return False, [REASON_TAXONOMY_UNAVAILABLE]
    try:
        # Никакого приведения типа: dict(rec or {}) превращал бы не-объект
        # (None, список пар) в валидное отображение и тем самым обходил
        # собственную проверку record:not-an-object.
        # Предел на ОДНУ запись проверяется ДО валидации: иначе огромная
        # НЕВАЛИДНАЯ запись уходила бы в карантин целиком, и ограничение
        # действовало бы ровно на тех записях, которые и так в порядке.
        cap = int((taxonomy.get("limits") or {}).get("maxRecordBytes")
                  or MAX_RECORD_BYTES_DEFAULT)
        try:
            encoded = json.dumps(rec, ensure_ascii=False, default=repr).encode("utf-8")
        except Exception:
            encoded = repr(rec).encode("utf-8", "replace")
        if len(encoded) > cap:
            # Предел закрывает вход в КАНОНИЧЕСКИЙ леджер. В карантин запись
            # уходит ЦЕЛИКОМ: «леджер ограничен» и «отклонённая запись
            # сохранена полностью» не противоречат друг другу, потому что
            # размер карантина держит РОТАЦИЯ, а не усечение записи.
            # Ротация сохраняет, усечение уничтожает.
            reasons = ["%s:%d" % (REASON_TOO_LARGE, len(encoded))]
            reject(cwd, rec, reasons, taxonomy, directory)
            return False, reasons
        if not isinstance(rec, dict):
            reasons = ["record:not-an-object"]
            reject(cwd, rec, reasons, taxonomy, directory)
            return False, reasons
        rec = dict(rec)
        # Штамп версии ставится ТОЛЬКО при приёме: пометив запись до
        # валидации, карантин хранил бы уже изменённый вход, а он обязан
        # сохранять ровно то, что пришло.
        supplied = rec.get("taxonomy_version")
        reasons = validate_record(rec, taxonomy)
        if supplied is not None and supplied != taxonomy["taxonomy_version"]:
            reasons = reasons + ["taxonomy_version:%r" % (supplied,)]
    except Exception as exc:
        # Инвариант «запись не теряется» держится ОДНОЙ воронкой, а не
        # перечислением веток: любая неожиданная ошибка разбора или словаря
        # даёт названную причину и карантин, а не тихий дроп через общий
        # except писателя (r4: структурно битый, но парсящийся словарь).
        reasons = ["admit-error:%s" % type(exc).__name__]
        # taxonomy, а не None: словарь загружен и валиден, поэтому даже
        # аварийный отказ обязан писать в НАСТРОЕННЫЙ файл карантина.
        reject(cwd, rec, reasons, taxonomy, directory)
        return False, reasons
    if reasons:
        reject(cwd, rec, reasons, taxonomy, directory)
        return False, reasons
    try:
        rec = dict(rec)
        rec["taxonomy_version"] = taxonomy["taxonomy_version"]
        _append_bounded(canonical_path(cwd, directory),
                        json.dumps(rec, ensure_ascii=False))
    except Exception as exc:
        reasons = ["admit-error:%s" % type(exc).__name__]
        # taxonomy, а не None: словарь загружен и валиден, поэтому даже
        # аварийный отказ обязан писать в НАСТРОЕННЫЙ файл карантина.
        reject(cwd, rec, reasons, taxonomy, directory)
        return False, reasons
    return True, []


def writer_defaults(source: str, tax=None):
    """Значения, которыми писатель заполняет поля, если не может судить сам.
    Берутся из словаря: литерал в писателе был бы второй копией контракта."""
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None:
        return {}
    got = (taxonomy.get("writerDefaults") or {}).get(source)
    return dict(got) if isinstance(got, dict) else {}


def normalize_category(value, tax=None):
    """Чтение легаси: свободная строка -> значение enum или None. Леджер при
    этом НЕ переписывается."""
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None or value is None:
        return None
    value = str(value)
    if value in taxonomy["category"]["values"]:
        return value
    return taxonomy["legacyMapping"]["category"].get(value)


def normalize_severity(value, tax=None):
    taxonomy = tax if tax is not None else load_taxonomy()
    if taxonomy is None:
        return None
    value = "" if value is None else str(value)
    if value in taxonomy["severity"]["values"]:
        return value
    return taxonomy["legacyMapping"]["severity"].get(value)


def rejected_summary(cwd: str, directory=None) -> dict:
    """Счётчик для /retro: сколько записей словарь не принял и по каким классам.
    Агрегируется из append-only журнала, поэтому битая строка теряет одну
    запись, а не весь счёт."""
    p = rejected_count_path(cwd, directory)
    total = 0
    by_reason: dict = {}
    counted: set = set()
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        # Валидный JSON, но не объект (`null`, `[]`) — тоже испорченная строка:
        # обещание «битая строка теряет одну запись» не должно превращаться в
        # падение всего /retro на .get().
        if not isinstance(entry, dict):
            continue
        # Счёт ведётся по РАЗЛИЧНЫМ личностям записи, а не по строкам журнала.
        # Предзапись-дедуп — это чтение-и-дозапись, то есть под конкуренцией
        # он в принципе не может быть точным; измерение же точно по
        # построению, без блокировок: одна и та же отклонённая запись с теми
        # же классами причин считается один раз, сколько бы писателей ни
        # записали её одновременно.
        identity = entry.get("identity")
        key_id = identity if isinstance(identity, str) and identity else ("#%d" % total)
        if key_id in counted:
            continue
        counted.add(key_id)
        total += 1
        for r in (entry.get("reasons") or ["unspecified"]):
            key = str(r).split(":", 1)[0].split("[", 1)[0] or "unspecified"
            by_reason[key] = by_reason.get(key, 0) + 1
    if not total:
        return {}
    return {"total": total, "byReason": by_reason}
