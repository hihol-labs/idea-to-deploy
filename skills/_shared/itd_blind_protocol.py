#!/usr/bin/env python3
"""Слепая семантическая приёмка категорий вердикта (PILOT-P02, v1.103.0).

ADVISORY-RSI-2026-08-27-v4 §5 требует smoke-приёмки пилота таксономии:
владелец категоризует выборку НОВЫХ находок по тексту находки, авторская
метка скрыта, инструкция — описания значений словаря; совпадение не ниже
порога принимает пилот.

Разделение обязанностей намеренное и соответствует §5 «setup -> observation
-> decision»: этот модуль — ЗАМОРОЖЕННАЯ машинерия (выборка, лист, скоринг),
а вердикт выносит отдельный юнит, когда популяция накопится. Порог, размер
выборки и правила лежат в `BLIND_PROTOCOL.json` и хешируются: реализация не
меняет собственный экзамен.

stdlib-only, кросс-платформенно; читается и из установленного runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL_FILE = "BLIND_PROTOCOL.json"
TAXONOMY_FILE = "VERDICT_TAXONOMY.json"
SEAL_DIR = ".itd-memory/blind-protocol"
# Семантика, которую реализует ЭТОТ модуль. Контракт, объявляющий другое,
# обязан отказать загрузку: молча делать не то, что написано в замороженном
# экзамене, — ровно тот docs-vs-code, который ловит собственный словарь.
SUPPORTED_PROTOCOL_VERSION = 1
SEED_BYTES_MAX = 32  # длина дайджеста sha256
SUPPORTED_RNG = "sha256-counter"
SUPPORTED_RULE = "exact-category-match"
SUPPORTED_VOCABULARY_SOURCE = "bySource"
REFUSE = "refuse"


class ProtocolError(Exception):
    """Отказ протокола. Причина обязана называть, ЧТО не так и ЧТО делать:
    молчаливый или безымянный отказ в приёмке ничем не лучше подгонки."""


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _shared_dir(root: Path) -> Path:
    """Каталог словарей: сначала переданный корень, потом установленный runtime.

    Корень имеет приоритет намеренно: замер обязан читать протокол и словарь
    ТОГО дерева, которое он размечает, иначе установленная копия молча
    подменяла бы экзамен проверяемой ветки."""
    candidate = Path(root) / "skills" / "_shared"
    if (candidate / PROTOCOL_FILE).is_file():
        return candidate
    here = Path(__file__).resolve().parent
    if (here / PROTOCOL_FILE).is_file():
        return here
    raise ProtocolError(
        "словарь протокола не найден. FIX: восстанови "
        "skills/_shared/%s" % PROTOCOL_FILE)


def load_protocol(root) -> dict:
    """Прочитать и СТРУКТУРНО проверить протокол.

    Проверка строгая и fail-closed: протокол — это экзамен, и битый экзамен
    обязан отказать, а не молча принять умолчания."""
    path = _shared_dir(Path(root)) / PROTOCOL_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProtocolError("протокол нечитаем: %s. FIX: почини %s"
                            % (exc, path)) from exc
    if not isinstance(data, dict):
        raise ProtocolError("протокол не объект. FIX: почини %s" % path)

    version = data.get("protocol_version")
    # Ровно поддержанная версия, а не «любая положительная»: чужая версия
    # означает другой замер, и загрузить её молча значит исполнить не тот
    # экзамен, к которому привязаны печати и вердикты.
    # type(...) is int, а не равенство: bool наследует int, а 1.0 равно 1,
    # поэтому `true` и `1.0` проходили бы как объявленная версия.
    if type(version) is not int or version != SUPPORTED_PROTOCOL_VERSION:
        raise ProtocolError(
            "protocol_version=%r не поддержан (модуль реализует %d). "
            "FIX: почини %s" % (version, SUPPORTED_PROTOCOL_VERSION, path))

    sample = data.get("sample")
    if not isinstance(sample, dict):
        raise ProtocolError("нет блока sample. FIX: почини %s" % path)
    size = sample.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ProtocolError("sample.size обязан быть целым > 0. FIX: почини %s"
                            % path)

    scoring = data.get("scoring")
    if not isinstance(scoring, dict):
        raise ProtocolError("нет блока scoring. FIX: почини %s" % path)
    threshold = scoring.get("threshold")
    if not isinstance(threshold, int) or isinstance(threshold, bool) \
            or not 0 < threshold <= size:
        raise ProtocolError(
            "scoring.threshold обязан быть целым в (0, sample.size]. "
            "FIX: почини %s" % path)

    population = data.get("population")
    if not isinstance(population, dict) \
            or not isinstance(population.get("ledger"), str) \
            or not population["ledger"].strip() \
            or not isinstance(population.get("includeRotatedGenerations"), bool) \
            or not isinstance(population.get("sourceIn"), list) \
            or not population["sourceIn"] \
            or any(not isinstance(s, str) or not s
                   for s in population["sourceIn"]):
        raise ProtocolError(
            "population.sourceIn обязан быть непустым списком строк, а "
            "includeRotatedGenerations — булевым, а ledger — непустой строкой "
            "пути: неявное умолчание молча сузило бы популяцию до одного "
            "поколения, а отсутствующий путь падал бы уже при чтении, мимо "
            "машиночитаемого отказа. FIX: почини %s" % path)

    worksheet_spec = data.get("worksheet")
    if not isinstance(worksheet_spec, dict) \
            or not isinstance(worksheet_spec.get("visibleFields"), list) \
            or not worksheet_spec["visibleFields"] \
            or any(not isinstance(f, str) or not f
                   for f in worksheet_spec["visibleFields"]):
        raise ProtocolError(
            "worksheet.visibleFields обязан быть непустым списком строк. "
            "FIX: почини %s" % path)
    # Поле метки НЕ имеет права оказаться видимым: это отменило бы слепоту,
    # ради которой протокол и существует.
    if "category" in worksheet_spec["visibleFields"]:
        raise ProtocolError(
            "worksheet.visibleFields показывает category — это отменяет "
            "слепоту. FIX: убери category из видимых полей в %s" % path)

    marking = data.get("honestMarking")
    if not isinstance(marking, str) or not marking.strip():
        raise ProtocolError(
            "honestMarking обязана быть непустой: приёмка без честной "
            "маркировки читается как гарантия точности. FIX: почини %s" % path)

    on_fail = data.get("onFail")
    if not isinstance(on_fail, dict) \
            or not isinstance(on_fail.get("action"), str) \
            or not on_fail["action"].strip() \
            or not isinstance(on_fail.get("then"), str) \
            or not on_fail["then"].strip():
        # Именно СТРОКИ, а не «что-нибудь истинное»: вердикт склеивает эти
        # поля в текст последствия, и истинное не-строковое значение падало
        # бы TypeError ровно на провальном замере — там, где машиночитаемый
        # отказ нужнее всего.
        raise ProtocolError(
            "onFail.action и onFail.then обязаны быть непустыми строками. "
            "FIX: почини %s" % path)

    # Ниже — поля, которые ОПИСЫВАЮТ поведение замера. Раньше они лежали в
    # контракте как проза, а модуль зашивал своё: контракт с другим значением
    # загружался молча и переставал описывать то, что исполняется.
    if sample.get("withoutReplacement") is not True:
        raise ProtocolError(
            "sample.withoutReplacement обязан быть true: жеребьёвку с "
            "возвратом модуль не реализует. FIX: почини %s" % path)
    if sample.get("rng") != SUPPORTED_RNG:
        raise ProtocolError(
            "sample.rng=%r не поддержан (модуль реализует %r). FIX: почини %s"
            % (sample.get("rng"), SUPPORTED_RNG, path))
    seed_bytes = sample.get("seedBytes")
    if not isinstance(seed_bytes, int) or isinstance(seed_bytes, bool) \
            or not 0 < seed_bytes <= SEED_BYTES_MAX:
        # Верхняя граница — не вкусовая: seed выводится усечением ОДНОГО
        # дайджеста sha256, и объявленные 64 байта молча дали бы 32. Контракт,
        # который нельзя исполнить как написано, обязан отказать.
        raise ProtocolError(
            "sample.seedBytes обязан быть целым в (0, %d]: seed выводится из "
            "одного дайджеста sha256 и длиннее быть не может. FIX: почини %s"
            % (SEED_BYTES_MAX, path))

    if scoring.get("rule") != SUPPORTED_RULE:
        raise ProtocolError(
            "scoring.rule=%r не поддержан (модуль реализует %r). FIX: почини %s"
            % (scoring.get("rule"), SUPPORTED_RULE, path))
    if type(scoring.get("outOf")) is not int or scoring["outOf"] != size:
        raise ProtocolError(
            "scoring.outOf=%r расходится с sample.size=%d: порог считался бы "
            "не от той выборки. FIX: почини %s"
            % (scoring.get("outOf"), size, path))
    for field in ("missingAnswer", "answerOutsideVocabulary"):
        if scoring.get(field) != REFUSE:
            raise ProtocolError(
                "scoring.%s=%r не поддержан: несостоявшийся замер обязан "
                "отказывать, а не засчитываться промахом. FIX: почини %s"
                % (field, scoring.get(field), path))

    attempts = data.get("attempts")
    if not isinstance(attempts, dict) \
            or type(attempts.get("perSeal")) is not int \
            or attempts["perSeal"] != 1:
        raise ProtocolError(
            "attempts.perSeal обязан быть 1: другого числа попыток модуль не "
            "реализует. FIX: почини %s" % path)

    for flag in ("requireTaxonomyVersion", "requireCategory",
                 "requireCategoryInVocabulary"):
        if not isinstance(population.get(flag), bool):
            raise ProtocolError(
                "population.%s обязан быть булевым: неявное умолчание меняло "
                "бы популяцию замера. FIX: почини %s" % (flag, path))

    if worksheet_spec.get("vocabularyFrom") != SUPPORTED_VOCABULARY_SOURCE:
        raise ProtocolError(
            "worksheet.vocabularyFrom=%r не поддержан (модуль реализует %r). "
            "FIX: почини %s"
            % (worksheet_spec.get("vocabularyFrom"),
               SUPPORTED_VOCABULARY_SOURCE, path))
    return data


def protocol_digest(protocol: dict) -> str:
    return _digest(protocol)


def taxonomy_digest(root: Path) -> str:
    """Дайджест словаря: он тоже определяет замер.

    Печать связывала протокол и находки, но не словарь, а именно словарь
    решает, какие значения предлагаются разметчику и какие принимаются на
    скоринге. Правка описаний или `bySource` после печати меняла бы правила
    внутри открытого окна, не задев ни одной другой привязки."""
    return _digest(_load_taxonomy(root))


def _load_taxonomy(root: Path) -> dict:
    path = _shared_dir(root) / TAXONOMY_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProtocolError("словарь вердикта нечитаем: %s. FIX: почини %s"
                            % (exc, path)) from exc
    # Тип проверяется ЗДЕСЬ, у единственного входа: валидный JSON-список,
    # число или null иначе доезжали бы до `.get` и роняли AttributeError
    # мимо машиночитаемого отказа.
    if not isinstance(data, dict):
        raise ProtocolError(
            "словарь вердикта обязан быть объектом, получено %s. FIX: почини "
            "%s" % (type(data).__name__, path))
    return data


def _ledger_paths(root: Path, protocol: dict) -> list[Path]:
    base = Path(root) / protocol["population"]["ledger"]
    paths = [base]
    if protocol["population"].get("includeRotatedGenerations"):
        paths.extend(sorted(base.parent.glob(base.name + ".*")))
    return paths


def _iter_rows(root: Path, protocol: dict):
    for path in _ledger_paths(root, protocol):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                # Оборванный фрагмент — не запись; читатель пропускает его так
                # же, как это делает писатель леджера.
                continue
            if isinstance(row, dict):
                yield line, row


def eligible(root, protocol: dict, taxonomy: dict | None = None) -> list[dict]:
    """Популяция: КАЖДАЯ новая находка ревьюера с меткой, а не первая в записи.

    Единица замера — находка: одна запись леджера несёт их несколько (в живом
    леджере 260 записей против 286 находок), и брать только первую значило бы
    молча сузить популяцию, из которой якобы случайно тянется выборка.

    Каждое условие отсекает конкретную подмену: без штампа версии запись
    писалась до валидации; без категории нечего сравнивать; чужой источник
    размечается другим словарём."""
    spec = protocol["population"]
    sources = set(spec["sourceIn"])
    # Снимок берётся ОДИН раз и здесь, если его не передали: иначе проверка
    # принадлежности словарю перечитывала бы файл на каждой находке, снова
    # открывая окно между чтениями.
    if taxonomy is None:
        taxonomy = _load_taxonomy(Path(root))
    pool = []
    for line, row in _iter_rows(Path(root), protocol):
        if spec.get("requireTaxonomyVersion") and not row.get("taxonomy_version"):
            continue
        source = row.get("source")
        # Строка проверяется ДО принадлежности множеству: нехешируемое
        # значение (список, объект) в испорченной строке леджера роняло бы
        # TypeError мимо всех обработчиков — трейсбек вместо отказа.
        if not isinstance(source, str) or source not in sources:
            continue
        findings = row.get("findings")
        if not isinstance(findings, list) or not findings:
            continue
        lineage = row.get("lineage")
        if not lineage:
            continue
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            category = finding.get("category")
            if spec.get("requireCategory") and not category:
                continue
            if spec.get("requireCategoryInVocabulary") \
                    and str(category) not in _vocabulary(Path(root), source,
                                                         taxonomy)[0]:
                # Метка вне словаря источника — не «несогласие», а
                # испорченный вход: разметчик выбирает ТОЛЬКО из словаря,
                # поэтому совпадение с такой меткой недостижимо, и её
                # присутствие в выборке молча занижало бы согласие.
                continue
            pool.append({
                # Позиция входит в личность: две находки одной записи обязаны
                # различаться и в печати, и в листе.
                "ref": "%s#%d" % (lineage, index),
                "lineage": str(lineage),
                "index": index,
                "source": str(source),
                "category": str(category),
                "finding": finding,
                # Дайджест накрывает находку ВМЕСТЕ с источником записи, но
                # не всю строку: правка соседней находки не отменяет замер по
                # этой, а вот подмена источника — отменяет. Источник решает,
                # каким словарём размечается позиция, поэтому его смена на
                # другой, где та же категория тоже допустима, молча меняла бы
                # предмет замера уже после печати.
                "digest": hashlib.sha256(_canonical({
                    "source": str(source), "finding": finding})).hexdigest(),
            })
    # Устойчивый порядок ДО жеребьёвки: иначе «тот же seed» давал бы разную
    # выборку от прогона к прогону, и замер нельзя было бы перепроверить.
    pool.sort(key=lambda item: (item["lineage"], item["index"]))
    seen: dict = {}
    for item in pool:
        if item["ref"] in seen:
            # Личность позиции строится из (lineage, index), а леджер её
            # уникальность не гарантирует: повтор строки давал бы две
            # находки с одной ссылкой, и поиск по словарю молча возвращал бы
            # чужую. Замер на такой популяции обязан отказать, а не выбрать
            # наугад.
            raise ProtocolError(
                "в популяции повторяется ссылка %s: леджер содержит записи с "
                "одинаковым lineage. FIX: почини провенанс записей — на "
                "неоднозначной популяции замер невозможен." % item["ref"])
        seen[item["ref"]] = item
    return pool


def _draw(pool: list[dict], size: int, seed: str) -> list[dict]:
    """Жеребьёвка без возврата, воспроизводимая по seed.

    Собственный счётчик на sha256, а не `random`: генератор stdlib не обязан
    давать одну и ту же последовательность между версиями Python, а замер
    обязан перепроверяться на любой машине."""
    remaining = list(pool)
    chosen = []
    counter = 0
    while len(chosen) < size:
        raw = hashlib.sha256(("%s:%d" % (seed, counter)).encode("utf-8")).digest()
        counter += 1
        index = int.from_bytes(raw[:8], "big") % len(remaining)
        chosen.append(remaining.pop(index))
    return chosen


def _derive_seed(protocol: dict, population: list) -> str:
    """Seed выводится ИЗ ПОПУЛЯЦИИ, а не выбирается вызывающим.

    Свободный seed оставлял оператору решающую степень свободы: перебирая
    значения, можно было намолотить удобную выборку и предъявить её как
    случайную — печать при этом оставалась внутренне согласованной. Здесь
    выборка становится чистой функцией популяции: чтобы её изменить, надо
    изменить сам леджер, а это ловит сверка с живой популяцией."""
    width = int(protocol["sample"].get("seedBytes", 16)) * 2
    material = _canonical({
        "protocol": protocol_digest(protocol),
        "population": population,
    })
    return hashlib.sha256(material).hexdigest()[:width]


def seal(root, protocol: dict) -> dict:
    """Заморозить выборку. Печать НЕ содержит авторских меток в открытом виде —
    только сами находки по хешу, поэтому лист остаётся слепым, а правка
    находки после печати ломает скоринг."""
    root = Path(root)
    snapshot = _load_taxonomy(root)
    pool = eligible(root, protocol, snapshot)
    size = int(protocol["sample"]["size"])
    if len(pool) < size:
        raise ProtocolError(
            "популяция мала: пригодных находок %d, протокол требует %d. "
            "FIX: дождись накопления новых находок — приёмка на неполной "
            "выборке не является приёмкой." % (len(pool), size))
    population = [{"ref": item["ref"], "digest": item["digest"]}
                  for item in pool]
    seed = _derive_seed(protocol, population)
    drawn = _draw(population, size, seed)
    return {
        "protocolDigest": protocol_digest(protocol),
        "taxonomyDigest": _digest(snapshot),
        # Популяция записывается ЦЕЛИКОМ: без неё выборку нельзя пересобрать,
        # и печать пришлось бы принимать на веру. С ней жеребьёвка становится
        # детерминированной функцией популяции, а не списком, который можно
        # переписать под удобный результат.
        "population": population,
        "populationDigest": _digest(population),
        "populationSize": len(pool),
        "seed": seed,
        "sealedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": [{
            "id": "item-%02d" % (n + 1),
            "ref": entry["ref"],
            "digest": entry["digest"],
        } for n, entry in enumerate(drawn)],
    }


def _require_seal_shape(sealed) -> None:
    """Форма печати проверяется ДО любого её чтения по существу.

    Отсутствующий protocolDigest ронял лист KeyError, а отсутствующий
    sealedAt — скоринг; оба мимо машиночитаемого отказа. Проверка вынесена
    отдельно, чтобы звать её первой на обоих путях."""
    if not isinstance(sealed, dict):
        raise ProtocolError(
            "печать обязана быть объектом, получено %s. FIX: печать "
            "повреждена — сделай новую." % type(sealed).__name__)
    for field in ("protocolDigest", "taxonomyDigest", "populationDigest",
                  "populationSize", "seed", "sealedAt", "population", "items"):
        if field not in sealed:
            raise ProtocolError(
                "в печати нет обязательного поля %s. FIX: печать повреждена — "
                "сделай новую." % field)
    stamped = sealed["sealedAt"]
    if not isinstance(stamped, str):
        raise ProtocolError(
            "sealedAt обязан быть строкой времени, получено %s. FIX: печать "
            "повреждена — сделай новую." % type(stamped).__name__)
    try:
        datetime.fromisoformat(stamped.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolError(
            "sealedAt не разбирается как момент времени (%r). FIX: печать "
            "повреждена — сделай новую." % stamped) from exc


def _verify_seal(root: Path, protocol: dict, sealed: dict,
                 pool: list, taxonomy: dict) -> None:
    """Печать обязана быть ТОЙ, что выдала жеребьёвка, а не списком позиций.

    Без этой проверки скоринг принимал бы `items` на веру: правка seal.json
    подменяла бы случайную выборку удобными находками (или дублировала одну
    и ту же) и выдавала проходной вердикт, обнуляя разом и заморозку выборки,
    и tamper-evidence, и одну попытку. Пересборка по записанному seed делает
    выборку детерминированной функцией печати, а не её содержимым.

    Популяция печати сверяется с ЖИВОЙ популяцией, а не только сама с собой:
    дайджест внутри печати считается по её же содержимому, поэтому редактор
    мог подставить десяток удобных находок, пересчитать дайджест и подобрать
    items под тот же seed — и подделка прошла бы, оставаясь внутренне
    согласованной. Сверка с `eligible()` убирает эту степень свободы."""
    if not isinstance(sealed, dict):
        # Печать читается из файла, поэтому её верхний уровень тоже вход:
        # валидный JSON-список или строка иначе роняли бы AttributeError
        # вместо машиночитаемого отказа.
        raise ProtocolError(
            "печать обязана быть объектом, получено %s. FIX: печать "
            "повреждена — сделай новую." % type(sealed).__name__)
    # Обязательные поля печати проверяются ЗДЕСЬ, а не там, где их впервые
    # читают: отсутствующий protocolDigest ронял лист KeyError, а
    # отсутствующий sealedAt — скоринг, оба мимо машиночитаемого отказа.
    _require_seal_shape(sealed)
    population = sealed.get("population")
    if not isinstance(population, list) or not population:
        raise ProtocolError(
            "печать не содержит популяции, по которой тянулась выборка. "
            "FIX: сделай новую печать текущей версией протокола.")
    for entry in population:
        # Именно СТРОКИ: нестроковая ссылка роняла бы TypeError уже во
        # множестве, а не отказывала по имени.
        if not isinstance(entry, dict) \
                or not isinstance(entry.get("ref"), str) or not entry["ref"] \
                or not isinstance(entry.get("digest"), str) \
                or not entry["digest"]:
            raise ProtocolError(
                "популяция в печати повреждена: ожидались объекты со "
                "строковыми ref и digest. FIX: сделай новую печать.")
    if sealed.get("populationDigest") != _digest(population):
        raise ProtocolError(
            "дайджест популяции не сходится с самой популяцией в печати. "
            "FIX: печать правлена — сделай новую.")
    if sealed.get("populationSize") != len(population):
        raise ProtocolError(
            "размер популяции в печати не сходится с её составом. "
            "FIX: печать правлена — сделай новую.")
    if sealed.get("taxonomyDigest") != _digest(taxonomy):
        raise ProtocolError(
            "словарь вердикта изменился после печати: он решает, какие "
            "значения предлагаются разметчику и принимаются на скоринге, "
            "поэтому его правка внутри окна замера меняет сам замер. "
            "FIX: сделай новую печать.")
    if len(population) < int(protocol["sample"]["size"]):
        raise ProtocolError(
            "популяция печати (%d) меньше размера выборки (%d): такой печати "
            "не могло быть. FIX: печать правлена — сделай новую."
            % (len(population), int(protocol["sample"]["size"])))
    live = [{"ref": item["ref"], "digest": item["digest"]} for item in pool]
    if population != live:
        raise ProtocolError(
            "популяция печати (%d) не совпадает с текущей популяцией леджера "
            "(%d) поимённо. Окно замера обязано быть закрытым: и подмена "
            "популяции удобным подмножеством, и появление новых находок между "
            "печатью и разметкой делают выборку неслучайной. FIX: сделай "
            "новую печать и размечай по ней."
            % (len(population), len(live)))

    seed = sealed.get("seed")
    if not isinstance(seed, str) or not seed:
        raise ProtocolError("печать без seed. FIX: сделай новую печать.")
    size = int(protocol["sample"]["size"])
    items = sealed.get("items")
    if isinstance(items, list) and any(not isinstance(entry, dict)
                                       for entry in items):
        raise ProtocolError(
            "позиции печати повреждены: ожидались объекты. FIX: печать "
            "правлена — сделай новую.")
    if not isinstance(items, list) or len(items) != size:
        raise ProtocolError(
            "в печати %s позиций, протокол требует %d. FIX: печать правлена — "
            "сделай новую." % (len(items) if isinstance(items, list) else "?",
                               size))
    if [entry.get("id") for entry in items] != ["item-%02d" % (n + 1)
                                                for n in range(size)]:
        raise ProtocolError(
            "позиции печати переименованы или переставлены. FIX: печать "
            "правлена — сделай новую.")
    if any(not isinstance(entry.get("ref"), str) or not entry["ref"]
           for entry in items):
        # Строка проверяется ДО множества: нехешируемое значение (список,
        # объект) роняло бы TypeError мимо машиночитаемого отказа.
        raise ProtocolError(
            "ссылки позиций печати обязаны быть непустыми строками. FIX: "
            "печать повреждена — сделай новую.")
    if len({entry["ref"] for entry in items}) != size:
        raise ProtocolError(
            "в печати повторяются находки. FIX: печать правлена — сделай "
            "новую.")

    if seed != _derive_seed(protocol, population):
        raise ProtocolError(
            "seed не выводится из этой популяции: он не выбирается, а "
            "вычисляется, иначе его можно было бы перебирать до удобной "
            "выборки. FIX: печать правлена — сделай новую.")
    redrawn = _draw(population, size, seed)
    if [entry["ref"] for entry in redrawn] != [entry.get("ref")
                                               for entry in items]:
        raise ProtocolError(
            "выборка не пересобирается по записанному seed: печать содержит "
            "не то, что вытянула жеребьёвка. FIX: печать правлена — сделай "
            "новую.")
    for drawn, entry in zip(redrawn, items):
        if drawn["digest"] != entry.get("digest"):
            raise ProtocolError(
                "дайджест позиции %s в печати не сходится с популяцией той же "
                "печати. FIX: печать правлена — сделай новую." % entry.get("id"))


def _vocabulary(root: Path, source: str,
                taxonomy: dict | None = None) -> tuple[list, dict]:
    """Словарь берётся из ПЕРЕДАННОГО снимка, если он есть.

    Перечитывание файла на каждом обращении давало окно между проверкой
    дайджеста и использованием: подмена словаря между чтениями смешивала
    версии в одной популяции или меняла словарь позиции уже после того, как
    его дайджест приняли."""
    taxonomy = taxonomy if taxonomy is not None else _load_taxonomy(root)
    # Каждый вложенный контейнер проверяется отдельно: валидный JSON вида
    # {"category": []} или {"category": {"meaning": []}} иначе доезжал до
    # `.get` и ронял AttributeError мимо машиночитаемого отказа.
    for name, holder in (("category", taxonomy),):
        if not isinstance(holder.get(name, {}), dict):
            raise ProtocolError(
                "словарь вердикта повреждён: %s обязан быть объектом. FIX: "
                "почини %s" % (name, TAXONOMY_FILE))
    category = taxonomy.get("category") or {}
    for name in ("meaning", "bySource"):
        if not isinstance(category.get(name, {}), dict):
            raise ProtocolError(
                "словарь вердикта повреждён: category.%s обязан быть "
                "объектом. FIX: почини %s" % (name, TAXONOMY_FILE))
    meaning = category.get("meaning") or {}
    by_source = category.get("bySource") or {}
    values = by_source.get(source)
    if not isinstance(values, list) or not values:
        raise ProtocolError(
            "словарь не объявляет значений для источника %r. FIX: почини "
            "bySource в %s" % (source, TAXONOMY_FILE))
    # Значения обязаны быть строками до любого их склеивания в текст: иначе
    # `", ".join(...)` в отказе сам падал бы TypeError.
    bad = [v for v in values if not isinstance(v, str) or not v]
    if bad:
        raise ProtocolError(
            "словарь источника %r содержит нестроковые значения. FIX: почини "
            "bySource в %s" % (source, TAXONOMY_FILE))
    missing = [v for v in values if not meaning.get(v)]
    if missing:
        raise ProtocolError(
            "у значений %s нет описания, а инструкция разметчика состоит "
            "именно из описаний. FIX: допиши meaning в %s"
            % (", ".join(missing), TAXONOMY_FILE))
    return list(values), {v: meaning[v] for v in values}


def worksheet(root, protocol: dict, sealed: dict) -> dict:
    """Лист для разметчика: текст находки и словарь, БЕЗ авторской метки.

    Видимые поля берутся белым списком, а не вычитанием: чёрный список
    пропустил бы любое новое поле записи, и метка утекла бы вместе с ним.

    Словарь резолвится ДЛЯ КАЖДОЙ позиции по её собственному источнику:
    популяция допускает несколько источников, а у них разные разрешённые
    значения, и один словарь на весь лист показывал бы части выборки
    заведомо недостижимую метку."""
    root = Path(root)
    _require_seal_shape(sealed)
    if sealed.get("protocolDigest") != protocol_digest(protocol):
        # Лист СТРОИТСЯ по протоколу: видимые поля и честная маркировка берутся
        # из него. Без этой сверки лист собирался бы по новому протоколу, но
        # нёс дайджест старого, то есть ложно приписывался бы запечатанному.
        raise ProtocolError(
            "протокол изменился после печати. FIX: не правь протокол внутри "
            "окна замера — сделай новую печать и новую выборку.")
    visible = list(protocol["worksheet"]["visibleFields"])
    snapshot = _load_taxonomy(root)
    live_pool = eligible(root, protocol, snapshot)
    # Лист строится ТОЛЬКО по проверенной печати: иначе повреждённый seal.json
    # ронял бы разметчика трейсбеком вместо машиночитаемого отказа, и правка
    # печати обнаруживалась бы лишь на скоринге — после всей работы вручную.
    _verify_seal(root, protocol, sealed, live_pool, snapshot)
    pool = {item["ref"]: item for item in live_pool}
    cache: dict = {}
    items = []
    union: list = []
    meanings: dict = {}
    for entry in sealed["items"]:
        found = pool.get(entry["ref"])
        if found is None:
            raise ProtocolError(
                "находка %s из печати исчезла из популяции. FIX: не правь "
                "леджер между печатью и разметкой." % entry["ref"])
        if found["source"] not in cache:
            cache[found["source"]] = _vocabulary(root, found["source"],
                                                snapshot)
        values, meaning = cache[found["source"]]
        shown = {"id": entry["id"], "vocabulary": list(values)}
        for field in visible:
            if field in found["finding"]:
                shown[field] = found["finding"][field]
        items.append(shown)
        for value in values:
            if value not in meanings:
                union.append(value)
                meanings[value] = meaning[value]
    return {
        "protocolDigest": sealed["protocolDigest"],
        "instruction": (
            "Отнеси каждую находку к ОДНОМУ значению из словаря ЭТОЙ позиции, "
            "опираясь только на её текст. Авторская метка скрыта намеренно."),
        "honestMarking": protocol["honestMarking"],
        "vocabulary": union,
        "meaning": meanings,
        "items": items,
    }


DIRECTORY_SYNC_SUPPORTED = os.name != "nt"


def _sync_directory(directory: Path) -> None:
    """Синхронизировать КАТАЛОГ после связывания, а не только файл.

    Содержимое вердикта попадало на диск, а запись каталога — нет: крах
    системы терял бы опубликованный вердикт при уже вернувшемся успехе
    скоринга, и единственная попытка открывалась бы заново.

    На Windows синхронизации каталога не существует — там это названное
    ограничение платформы в контракте, а не тихий пропуск: отказывать в
    замере целиком было бы хуже, чем честно назвать более слабую
    долговечность."""
    if not DIRECTORY_SYNC_SUPPORTED:
        return
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_verdict(path: Path, payload: str) -> None:
    """Опубликовать вердикт АТОМАРНО: файла-полуфабриката не существует никогда.

    Заявка через O_EXCL с последующей записью оставляла окно, в котором файл
    уже есть, а вердикта в нём ещё нет: смерть процесса в этом окне навсегда
    съедала единственную попытку, хотя замер не состоялся. Здесь содержимое
    сначала целиком ложится во временный файл и синхронизируется на диск, и
    только потом одним неделимым шагом появляется по целевому имени.

    Переиспользовать чужой неполный остаток НЕЛЬЗЯ: проверка «файл пуст, значит
    брошен» — это гонка, в которой второй скорер сносит заявку первого, ещё
    живого. Поэтому посторонний файл называется в отказе, а решение принимает
    человек."""
    # Имя временного файла УНИКАЛЬНО (mkstemp), а не выведено из PID: сирота
    # от упавшего скорера с тем же PID давала FileExistsError ещё ДО публикации,
    # и score() принимал её за коллизию по целевому имени — единственная попытка
    # блокировалась замером, который вердикта не вынес (r4). Теперь
    # FileExistsError может прийти только от os.link, то есть от целевого пути.
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                                    dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(tmp), str(path))
        except FileExistsError:
            raise
        except (OSError, NotImplementedError, AttributeError) as exc:
            # Отката НЕТ. Прямая запись в целевой файл вернула бы ровно то
            # окно, ради закрытия которого этот путь и существует: читатель
            # увидел бы полувердикт, а смерть процесса съела бы попытку.
            # Невозможность атомарной публикации — названный отказ, а не
            # тихое понижение гарантии.
            raise ProtocolError(
                "файловая система не поддерживает атомарную публикацию "
                "вердикта жёсткой ссылкой (%s). FIX: проводи замер на "
                "файловой системе, где она есть — понижать гарантию до "
                "прямой записи нельзя." % exc) from exc
        # Синхронизация каталога — ОТДЕЛЬНОЙ веткой, после состоявшейся
        # публикации. Внутри try она попадала в обработчик ссылки и
        # превращалась в отказ «нет жёстких ссылок» при уже лежащем на диске
        # вердикте: неуспешный вызов съедал единственную попытку, а сообщение
        # было ложным. Вердикт существует, отказывать нельзя; более слабая
        # долговечность названа ограничением контракта.
        try:
            _sync_directory(path.parent)
        except OSError:
            pass
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _acquire_ledger_lock(root: Path, protocol: dict):
    """Взять ТУ ЖЕ блокировку, что держат писатели леджера.

    Модуль словаря вердикта (`itd_verdict_taxonomy`) сериализует свои
    дозаписи блокировкой на скрытом файле рядом с журналом. Замер обязан
    брать именно её, а не свою: две разные блокировки не мешали бы друг
    другу, и дозапись по-прежнему вклинивалась бы между финальной сверкой и
    публикацией вердикта."""
    ledger = Path(root) / protocol["population"]["ledger"]
    writer = _writer_module()
    fd = writer._acquire_ledger_lock(ledger)
    return (writer, fd)


def _release_ledger_lock(lock) -> None:
    writer, fd = lock
    writer._release_ledger_lock(fd)


def _writer_module():
    """Модуль писателей резолвится рядом с этим файлом, без установки пакета."""
    import importlib.util
    path = Path(__file__).resolve().parent / "itd_verdict_taxonomy.py"
    spec = importlib.util.spec_from_file_location("itd_verdict_taxonomy_lock",
                                                  path)
    if spec is None or spec.loader is None:
        raise ProtocolError(
            "модуль писателей леджера недоступен, взять общую блокировку "
            "нечем. FIX: восстанови %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verdict_path(root: Path, sealed: dict) -> Path:
    """Имя вердикта — дайджест полей, ОПРЕДЕЛЯЮЩИХ замер, а не всей печати.

    Шестнадцать символов seed давали общее пространство имён: две разные
    печати с одинаковым префиксом считались одной попыткой, а при
    seedBytes=1 имён всего 256 — чужая популяция наследовала бы уже
    потраченную попытку.

    `sealedAt` в личность НЕ входит, и это осознанно: он меняется от печати
    к печати, поэтому его привязка дала бы новое имя при каждой повторной
    печати неизменной популяции и тем самым вернула бы возможность
    переиграть замер пересдачей. Метка времени — информационное поле; она
    проверяется на форму и помечена в вердикте как неаутентифицированная,
    вместо того чтобы выдавать её за часть привязки."""
    directory = Path(root) / SEAL_DIR
    directory.mkdir(parents=True, exist_ok=True)
    identity = _digest({
        "protocolDigest": sealed.get("protocolDigest"),
        "taxonomyDigest": sealed.get("taxonomyDigest"),
        "populationDigest": sealed.get("populationDigest"),
        "seed": sealed.get("seed"),
    })
    return directory / ("verdict-%s.json" % identity)


def score(root, protocol: dict, sealed: dict, answers: dict) -> dict:
    """Сравнить ответы разметчика с авторскими метками и применить порог.

    Отказ, а не «промах», на неполном и внесловарном листе: несостоявшийся
    замер обязан выглядеть как несостоявшийся, иначе порог начинает измерять
    аккуратность заполнения, а не согласие."""
    root = Path(root)
    # Форма печати проверяется ДО первого обращения к её полям по существу:
    # иначе валидный JSON-список ронял бы AttributeError уже на сверке
    # дайджеста, а отсутствующее поле — KeyError, не дойдя до отказа.
    _require_seal_shape(sealed)
    if sealed.get("protocolDigest") != protocol_digest(protocol):
        raise ProtocolError(
            "протокол изменился после печати. FIX: не правь протокол внутри "
            "окна замера — сделай новую печать и новую выборку.")

    if not isinstance(answers, dict):
        # Проверка в САМОЙ воронке, а не только в CLI: любой вызывающий,
        # передавший не отображение, обязан получить названный отказ, а не
        # TypeError из внутренностей скоринга.
        raise ProtocolError(
            "лист ответов обязан быть объектом {позиция: значение}, получено "
            "%s. FIX: передай JSON-объект." % type(answers).__name__)
    snapshot = _load_taxonomy(root)
    live_pool = eligible(root, protocol, snapshot)
    _verify_seal(root, protocol, sealed, live_pool, snapshot)
    pool = {item["ref"]: item for item in live_pool}
    cache: dict = {}

    expected_ids = [entry["id"] for entry in sealed["items"]]
    missing = [i for i in expected_ids if i not in answers]
    if missing:
        raise ProtocolError(
            "лист ответов неполон: нет %s. FIX: разметь все позиции — "
            "неполный лист не является замером." % ", ".join(missing))
    extra = [i for i in answers if i not in expected_ids]
    if extra:
        # Ключи приводятся к строкам ДО сортировки и склейки: смешанные типы
        # роняли бы TypeError в самом тексте отказа.
        raise ProtocolError(
            "лист ответов содержит позиции вне печати: %s. FIX: размечай "
            "только выданную выборку." % ", ".join(sorted(repr(x) for x in extra)))

    matches = 0
    detail = []
    for entry in sealed["items"]:
        found = pool.get(entry["ref"])
        if found is None or found["digest"] != entry["digest"]:
            raise ProtocolError(
                "находка %s изменилась после печати. FIX: не правь леджер "
                "внутри окна замера — сделай новую печать." % entry["ref"])
        if found["source"] not in cache:
            cache[found["source"]] = _vocabulary(root, found["source"],
                                                snapshot)
        values, _ = cache[found["source"]]
        answer = answers[entry["id"]]
        # Словарь проверяется ПО ИСТОЧНИКУ ЭТОЙ позиции: у другого источника
        # он другой, и общий список пропустил бы недопустимый здесь ответ.
        if answer not in values:
            raise ProtocolError(
                "ответ %r на позиции %s вне словаря источника %s. FIX: "
                "выбирай значение из словаря позиции — свободный ответ не "
                "промах, а несостоявшийся замер."
                % (answer, entry["id"], found["source"]))
        agreed = answer == found["category"]
        matches += 1 if agreed else 0
        detail.append({
            "id": entry["id"],
            "ref": entry["ref"],
            "author": found["category"],
            "labeller": answer,
            "agreed": agreed,
        })

    threshold = int(protocol["scoring"]["threshold"])
    passed = matches >= threshold
    verdict = {
        "verdict": "PASSED" if passed else "FAILED",
        "matches": matches,
        "outOf": len(sealed["items"]),
        "threshold": threshold,
        "protocolDigest": sealed["protocolDigest"],
        "populationDigest": sealed["populationDigest"],
        "populationSize": sealed["populationSize"],
        "seed": sealed["seed"],
        "sealedAt": sealed["sealedAt"],
        # Названо честно: метка времени НЕ входит в привязку вердикта, иначе
        # каждая повторная печать получала бы новое имя и попытку можно было
        # бы переиграть пересдачей.
        "sealedAtAuthenticated": False,
        "scoredAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "honestMarking": protocol["honestMarking"],
        "consequence": (
            protocol["onFail"]["action"] + "; " + protocol["onFail"]["then"]
            if not passed else "пилот принят по smoke-критерию"),
        "items": detail,
    }

    # Попытка занимается АТОМАРНО и только после того, как замер состоялся:
    # проверка существования с последующей записью — гонка, в которой два
    # скорера оба видят «файла нет» и затирают друг друга, а «одна попытка на
    # печать» превращается в необязательное пожелание. Отказавший замер
    # попытку не тратит: отказ — это не вердикт.
    # Популяция пересверяется НЕПОСРЕДСТВЕННО перед публикацией: между первой
    # сверкой и записью успевают пройти проверка ответов и сборка вердикта, и
    # дозапись в леджер в этом промежутке дала бы вердикт, привязанный к уже
    # неактуальной популяции — то самое окно, которое протокол объявляет
    # закрытым, только сдвинутое внутрь скоринга.
    path = _verdict_path(root, sealed)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(verdict, ensure_ascii=False, indent=2) + "\n"
    # Финальная сверка и публикация идут ПОД ТОЙ ЖЕ блокировкой, которую
    # берут писатели леджера: обещание «не пишите во время замера» — это не
    # tamper-evidence, а надежда, и подпирать им привязку к живой популяции
    # нельзя. Под блокировкой дозапись физически не может вклиниться между
    # проверкой и записью вердикта.
    lock = _acquire_ledger_lock(root, protocol)
    try:
        # Под блокировкой протокол и словарь перечитываются С ДИСКА и
        # сверяются с печатью. Снимок нужен для СОГЛАСОВАННОСТИ внутри фазы,
        # но он же слепнет к подмене файла в окне замера: переиздать его и
        # сравнить дайджесты — единственный способ отличить «читаю одно и то
        # же» от «читаю то же, что было в печати».
        fresh_protocol = load_protocol(root)
        if protocol_digest(fresh_protocol) != sealed["protocolDigest"]:
            raise ProtocolError(
                "протокол на диске изменился к моменту публикации. FIX: не "
                "правь протокол внутри окна замера — сделай новую печать.")
        fresh_taxonomy = _load_taxonomy(Path(root))
        if _digest(fresh_taxonomy) != sealed["taxonomyDigest"]:
            raise ProtocolError(
                "словарь вердикта на диске изменился к моменту публикации. "
                "FIX: не правь словарь внутри окна замера — сделай новую "
                "печать.")
        _verify_seal(root, fresh_protocol, sealed,
                     eligible(root, fresh_protocol, fresh_taxonomy),
                     fresh_taxonomy)
        _publish_verdict(path, payload)
    except FileExistsError as exc:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and existing.get("verdict"):
            raise ProtocolError(
                "по этой печати вердикт уже вынесен (%s). FIX: пересдача на "
                "той же выборке — подгонка; сделай новую печать."
                % path.name) from exc
        raise ProtocolError(
            "по пути вердикта лежит посторонний файл (%s), это не вынесенный "
            "вердикт. FIX: убедись, что замер не идёт в другом процессе, и "
            "удали файл вручную — снос чужой заявки автоматом был бы гонкой."
            % path.name) from exc
    finally:
        _release_ledger_lock(lock)
    return verdict


def _seal_path(root: Path) -> Path:
    return Path(root) / SEAL_DIR / "seal.json"


def _sheet_path(root: Path) -> Path:
    return Path(root) / SEAL_DIR / "worksheet.json"


def main(argv=None) -> int:
    """CLI замера: seal -> worksheet -> score.

    Три отдельные команды, а не одна: между печатью и скорингом обязан
    поместиться человек, и порядок должен быть виден в истории оболочки."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["seal", "worksheet", "score"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--answers", default=None,
                        help="JSON-файл {item-01: category, ...} для score")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        protocol = load_protocol(root)
        if args.command == "seal":
            sealed = seal(root, protocol)
            path = _seal_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sealed, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
            print(json.dumps({"status": "SEALED", "seal": str(path),
                              "seed": sealed["seed"],
                              "populationSize": sealed["populationSize"]},
                             ensure_ascii=False))
            return 0
        sealed = json.loads(_seal_path(root).read_text(encoding="utf-8"))
        if args.command == "worksheet":
            sheet = worksheet(root, protocol, sealed)
            path = _sheet_path(root)
            path.write_text(json.dumps(sheet, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
            print(json.dumps({"status": "READY", "worksheet": str(path),
                              "items": len(sheet["items"])},
                             ensure_ascii=False))
            return 0
        if not args.answers:
            raise ProtocolError(
                "score требует --answers. FIX: заполни лист и передай JSON "
                "вида {\"item-01\": \"correctness\", ...}")
        answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            raise ProtocolError(
                "файл ответов обязан содержать объект {позиция: значение}, "
                "получено %s. FIX: почини %s"
                % (type(answers).__name__, args.answers))
        verdict = score(root, protocol, sealed, answers)
        print(json.dumps(verdict, ensure_ascii=False))
        return 0 if verdict["verdict"] == "PASSED" else 1
    except ProtocolError as exc:
        # Отказ печатается машиночитаемо и уходит НЕнулевым кодом: замер,
        # который не состоялся, не имеет права выглядеть как пройденный.
        print(json.dumps({"status": "REFUSED", "why": str(exc)},
                         ensure_ascii=False))
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "why": str(exc)},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
