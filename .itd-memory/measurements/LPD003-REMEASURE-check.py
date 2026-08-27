#!/usr/bin/env python3
"""LPD003-REMEASURE (N6): fail-closed сверка записанных чисел перемера.

Пересчитывает разрез GATE G0 (дубль-критерий S05: тройка commandSha256/
stdoutSha256/exitCode на треке unitId; оба варианта ключа амендмента — без
run-all и с run-all; эры PRE/POST по 2026-08-24, merge LPD-003-1 #230) по
квитанциям обеих локаций .itd-memory/verification-loop и сравнивает с
зафиксированным артефактом LPD003-REMEASURE-n6.json.

Срез заморожен по времени: учитываются только квитанции с createdAt <
CUTOFF (до активации юнита N6) — иначе квитанции маршрута самого N6
двигали бы замер, который он публикует.

Запуск: python3 -I .itd-memory/measurements/LPD003-REMEASURE-check.py
Exit 0 — числа артефакта совпадают с пересчётом; 1 — расхождение.
"""
import json, sys, statistics
import datetime as dt
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
VL = ROOT / '.itd-memory' / 'verification-loop'
ART = Path(__file__).with_name('LPD003-REMEASURE-n6.json')
ERA_SPLIT = dt.datetime(2026, 8, 24, tzinfo=dt.timezone.utc)
CUTOFF = dt.datetime(2026, 8, 27, 18, 45, tzinfo=dt.timezone.utc)

def parse(s):
    return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))

class InvertedInterval(Exception):
    def __init__(self, secs):
        self.secs = secs

def dur(run):
    # fail-closed: битый/отсутствующий таймстемп — ошибка корпуса, а не
    # «0 секунд» (находка pub6); инвертированный интервал — тоже ошибка,
    # а не зажим в ноль (находка pub7): малформленная квитанция не имеет
    # права занижать пересчитанные суммы, совпадая с артефактом. Известные
    # исторические инверсии (clock-skew старых эр) задекларированы в
    # артефакте поимённо и дают вклад 0.0; любая новая — ошибка.
    secs = (parse(run['completedAt']) - parse(run['startedAt'])).total_seconds()
    if secs < 0:
        raise InvertedInterval(secs)
    return secs

class Era:
    def __init__(self):
        self.total = self.runall = 0.0
        self.dup_no = self.dup_with = 0.0
        self.per_unit_no = defaultdict(float)
        self.per_unit_with = defaultdict(float)
        self.seen = defaultdict(set)

eras = {'PRE': Era(), 'POST': Era()}
files = sorted(VL.glob('receipts/*/*.json')) + sorted(VL.glob('*.json'))
# fail-closed по корпусу (находка ревьюера pub6): нечитаемый JSON, квитанция
# machine-verification без валидного createdAt и прогон с битым таймстемпом —
# ошибки корпуса, а не молчаливый пропуск. Файлы других kind (промпты, отчёты,
# checker/adjudication-квитанции) — классификация, не пропуск.
errors = []
_art_doc = json.loads(ART.read_text(encoding='utf-8'))
declared_inverted = {(x['file'], x['run'], x['seconds'])
                     for x in _art_doc.get('declaredInvertedRuns', [])}
for f in files:
    if '-prompt' in f.name:
        # классификация по роли: продюсер пишет промпт-транскрипты (сырые
        # байты, видимые модели) в файлы *-prompt*.json — это не квитанции
        # и не обязаны быть JSON; любой ДРУГОЙ нечитаемый файл — ошибка
        continue
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'unreadable JSON: {f.name}: {exc}')
        continue
    if not isinstance(d, dict) or d.get('kind') != 'machine-verification':
        continue
    try:
        created = parse(d.get('createdAt'))
    except Exception:
        errors.append(f'machine receipt without valid createdAt: {f.name}')
        continue
    if created >= CUTOFF:
        continue
    e = eras['POST' if created >= ERA_SPLIT else 'PRE']
    unit = str(d.get('unitId') or '?')
    for i, r in enumerate(d.get('runs') or []):
        try:
            secs = dur(r)
        except InvertedInterval as inv:
            if (f.name, i, round(inv.secs, 1)) in declared_inverted:
                secs = 0.0  # задекларированная историческая инверсия
            else:
                errors.append(f'inverted run interval: {f.name}#run{i} ({inv.secs:.1f}s)')
                continue
        except Exception:
            errors.append(f'run without valid timestamps: {f.name}#run{i}')
            continue
        is_runall = 'run-all.sh' in str(r.get('command') or '')
        key = (r.get('commandSha256'), r.get('stdoutSha256'), r.get('exitCode'))
        e.total += secs
        if is_runall:
            e.runall += secs
        if key in e.seen[unit]:
            e.dup_with += secs
            e.per_unit_with[unit] += secs
            if not is_runall:
                e.dup_no += secs
                e.per_unit_no[unit] += secs
        else:
            e.seen[unit].add(key)

if errors:
    print('CORPUS ERRORS (fail-closed):')
    for line in errors[:20]:
        print(' ', line)
    sys.exit(1)

def snap(e):
    vals_no = sorted(e.per_unit_no.get(u, 0.0) / 60 for u in e.seen)
    vals_w = sorted(e.per_unit_with.get(u, 0.0) / 60 for u in e.seen)
    def s(vals):
        if not vals:
            return {'median': 0.0, 'max': 0.0, 'over30': 0}
        return {'median': round(statistics.median(vals), 2),
                'max': round(max(vals), 1),
                'over30': sum(1 for v in vals if v >= 30)}
    return {
        'units': len(e.seen),
        'totalMin': round(e.total / 60, 1),
        'runallMin': round(e.runall / 60, 1),
        'ceilingNoRunallMin': round(e.dup_no / 60, 1),
        'ceilingWithRunallMin': round(e.dup_with / 60, 1),
        'perUnitNoRunall': s(vals_no),
        'perUnitWithRunall': s(vals_w),
    }

computed = {'PRE': snap(eras['PRE']), 'POST': snap(eras['POST'])}
recorded = json.loads(ART.read_text(encoding='utf-8'))['eras']
if computed != recorded:
    print('MISMATCH')
    print('recorded:', json.dumps(recorded, ensure_ascii=False))
    print('computed:', json.dumps(computed, ensure_ascii=False))
    sys.exit(1)
print('OK: recorded remeasure figures match the receipts recomputation')
print(json.dumps(computed, ensure_ascii=False))
sys.exit(0)
