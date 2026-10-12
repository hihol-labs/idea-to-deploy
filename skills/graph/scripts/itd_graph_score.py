#!/usr/bin/env python3
"""Version 2 study oracle: explicit blind judgments, no heuristic seed credit.

Pure API: build_queue(manifest, results, salt=...) and score(..., verdicts, salt=...).
The returned queue is safe to give a judge. Never give the judge the input files
or the private association map. Verdicts are an EXACT mapping of queue IDs to
JSON booleans. Unknown/unverifiable claims should be judged false. Queue IDs bind
the complete inputs and salt, so any input change invalidates old judgments.

All rates, gain, sign-test p and cost ratios are exact Fraction strings. Empty
precision is defined as 1 (no asserted claims); no defects gives catch rate 0
and cannot WIN. Pure functions permit smaller complete paired studies for tests;
the CLI requires eight tasks, GK/KG pairs and G/K arms for each task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

DEFAULT_SALT = 'fixed-study-v2'
OBSERVATION_FIELDS = ('file', 'line', 'function', 'contractId', 'precondition',
                      'input', 'expected', 'actual', 'claim', 'evidence')
BEHAVIOR_FIELDS = ('function', 'contractId', 'description', 'precondition',
                   'input', 'expected', 'actual', 'oracleEvidence')
# Attribution belongs in provenance, not in a behavioral example. Only explicit
# narrative attribution is replaced; semantic values are preserved or refused.
ORIGIN_PHRASES = re.compile(
    r'\b(?:(?:according to|as reported by|reported by|per|from)\s+(?:the\s+)?(?:hunter|skeptic)(?:\s+agent)?'
    r'|(?:hunter|skeptic)(?:\s+and\s+(?:hunter|skeptic))?\s+(?:reports?|says?|claims?|found|findings?)'
    r'|(?:hunter|skeptic)\s*:'
    r'|(?:по данным|со слов|согласно|от)\s+(?:охотник\w*|скептик\w*)'
    r'|(?:охотник\w*|скептик\w*)\s+(?:сообщил\w*|наш[её]л\w*|утвержда\w*))\b', re.I)
ARM_PHRASES = re.compile(
    r'\b(?:(?:graph|single|control|treatment)\s+(?:(?:arm|route|policy)\s+)?(?-i:GK|KG|G|K)'
    r'|(?:arm|route|policy)\s+(?-i:GK|KG|G|K))\b', re.I)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError('inputs must contain finite JSON values') from exc


def _identifier(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')


def _validate(manifest, results, study=False):
    _object(manifest, 'manifest')
    _object(results, 'results')
    _canonical([manifest, results])
    if type(manifest.get('version')) is not int or manifest['version'] != 2:
        raise ValueError('manifest version must be 2')
    if type(results.get('version')) is not int or results['version'] != 2:
        raise ValueError('results version must be 2')
    defects, runs = manifest.get('defects'), results.get('runs')
    if not isinstance(defects, list) or not isinstance(runs, list) or not runs:
        raise ValueError('defects and nonempty runs must be arrays')
    if 'basePath' in results:
        _identifier(results['basePath'], 'basePath')
    slots, run_ids, tasks, pairs = set(), set(), set(), set()
    for run in runs:
        _object(run, 'run')
        run_id = _identifier(run.get('id'), 'run id')
        task = _identifier(run.get('task'), 'task')
        pair = _identifier(run.get('pair'), 'pair')
        arm, route = run.get('arm'), run.get('route')
        if arm not in ('G', 'K') or route not in ('graph', 'single'):
            raise ValueError('invalid arm or route')
        if arm == 'K' and route != 'single':
            raise ValueError('control K must use single route')
        if 'basePath' in run:
            _identifier(run['basePath'], 'run basePath')
        duration = run.get('durationNs')
        if type(duration) is not int or duration <= 0:
            raise ValueError('durationNs must be a positive integer')
        slot = (task, pair, arm)
        if slot in slots or run_id in run_ids:
            raise ValueError('duplicate run id or task/pair/arm')
        slots.add(slot)
        run_ids.add(run_id)
        tasks.add(task)
        pairs.add(pair)
        if not isinstance(run.get('findings'), list):
            raise ValueError('findings must be an array')
        finding_ids = set()
        for finding in run['findings']:
            _object(finding, 'finding')
            fid = _identifier(finding.get('findingId'), 'finding id')
            if fid in finding_ids:
                raise ValueError('duplicate finding id within run')
            finding_ids.add(fid)
            for field in OBSERVATION_FIELDS:
                if field not in finding:
                    raise ValueError('finding missing ' + field)
            for field in ('file', 'function', 'contractId', 'claim'):
                _identifier(finding[field], 'finding ' + field)
            if type(finding['line']) is not int or finding['line'] <= 0:
                raise ValueError('finding line must be a positive integer')
    expected = {(task, pair, arm) for task in tasks for pair in pairs for arm in ('G', 'K')}
    if slots != expected:
        raise ValueError('incomplete paired task/arm grid')
    if study and (len(tasks) != 8 or pairs != {'GK', 'KG'}):
        raise ValueError('study CLI requires eight tasks and pairs GK/KG')
    seed_ids = set()
    for defect in defects:
        _object(defect, 'defect')
        sid = _identifier(defect.get('id'), 'defect id')
        if sid in seed_ids:
            raise ValueError('duplicate defect id')
        seed_ids.add(sid)
        if defect.get('task') not in tasks:
            raise ValueError('defect refers to a foreign task')
        for field in BEHAVIOR_FIELDS:
            if field not in defect:
                raise ValueError('defect missing ' + field)
        for field in ('function', 'contractId', 'description'):
            _identifier(defect[field], 'defect ' + field)
    return defects, runs


def _logical_file(file, task):
    # Physical run/arm directory names must not reach the judge.
    parts = file.replace('\\', '/').split('/')
    if task in parts:
        return '/'.join(parts[parts.index(task):])
    if not file.replace('\\', '/').startswith('/') and not re.match(r'^[A-Za-z]:', file):
        return '/'.join(parts)
    roles = {'G', 'K', 'GK', 'KG', 'hunter', 'skeptic'}
    boundaries = [i for i, part in enumerate(parts[:-1]) if part in roles]
    if boundaries:
        return '/'.join(parts[boundaries[-1] + 1:])
    raise ValueError('absolute finding path requires a task-qualified public location')


def _physical_roots(runs):
    roots = set()
    for run in runs:
        for finding in run['findings']:
            physical = finding['file'].replace('\\', '/')
            logical = _logical_file(physical, run['task'])
            prefix = physical[:-len(logical)] if physical.endswith(logical) else ''
            parts = set(prefix.strip('/').split('/'))
            if parts & {run['id'], 'G', 'K', 'GK', 'KG', 'hunter', 'skeptic'}:
                roots.add(prefix)
    return sorted(roots, key=lambda x: (-len(x), x))


def _blind(value, hidden, physical_roots=()):
    changed = False
    def walk(item, narrative=False, depth=0):
        nonlocal changed
        if isinstance(item, str):
            out = item
            if not narrative and any(root in out for root in physical_roots):
                raise ValueError('physical study path in semantic value cannot be safely blinded')
            if not narrative and any(re.search(r'(?<!\w)' + re.escape(identifier) + r'(?!\w)', out) for identifier in hidden):
                raise ValueError('study identifier in semantic value cannot be safely blinded')
            for root in physical_roots:
                out = out.replace(root, '')
            for identifier in hidden:
                out = re.sub(r'(?<!\w)' + re.escape(identifier) + r'(?!\w)', '[blinded]', out)
            if narrative:
                out = ORIGIN_PHRASES.sub('[blinded]', out)
                out = ARM_PHRASES.sub('[blinded]', out)
            elif ORIGIN_PHRASES.search(out) or ARM_PHRASES.search(out):
                raise ValueError('study attribution in semantic value must be removed from provenance before judging')
            changed = changed or out != item
            return out
        if isinstance(item, list):
            return [walk(x, narrative, depth + 1) for x in item]
        if isinstance(item, dict):
            # Do not rewrite JSON keys: two distinct behavior keys must never collapse.
            for key in item:
                if any(root in key for root in physical_roots):
                    raise ValueError('physical study path in semantic key cannot be safely blinded')
                if any(re.search(r'(?<!\w)' + re.escape(identifier) + r'(?!\w)', key) for identifier in hidden):
                    raise ValueError('study identifier in semantic key cannot be safely blinded')
            # view.finding/view.behavior dictionaries are at depth 1.
            # Set narrative on their named field BEFORE walking the depth-2 string;
            # nested semantic input.claim remains data and must not be redacted.
            return {key: walk(v, narrative or (depth == 1 and key in ('claim', 'description')), depth + 1) for key, v in item.items()}
        return item
    return walk(value), changed


def _queue_records(manifest, results, salt=DEFAULT_SALT):
    defects, runs = _validate(manifest, results)
    _identifier(salt, 'salt')
    binding = hashlib.sha256(_canonical([manifest, results]).encode('utf-8')).hexdigest()
    hidden = sorted({d['id'] for d in defects} | {r['id'] for r in runs} |
                    {f['findingId'] for r in runs for f in r['findings']}, key=lambda x: (-len(x), x))
    by_task = defaultdict(list)
    for defect in defects:
        by_task[defect['task']].append(defect)
    physical_roots = _physical_roots(runs)
    items, records = [], {}
    for run in runs:
        for finding in run['findings']:
            observation = {key: finding[key] for key in OBSERVATION_FIELDS}
            observation['file'] = _logical_file(finding['file'], run['task'])
            context = {'task': run['task']}
            base_path = run.get('basePath', results.get('basePath'))
            if base_path is not None:
                parts = set(base_path.replace('\\', '/').strip('/').split('/'))
                if parts & {run['id'], 'G', 'K', 'GK', 'KG', 'hunter', 'skeptic'}:
                    raise ValueError('basePath must name the public pinned base, not a measured arm clone')
                context['basePath'] = base_path
            for defect in [None] + by_task[run['task']]:
                kind = 'real' if defect is None else 'semantic'
                opaque = hashlib.sha256(_canonical([salt, binding, kind, run['id'],
                    finding['findingId'], None if defect is None else defect['id']]).encode('utf-8')).hexdigest()
                if kind == 'real':
                    question = ('Does this observation demonstrate a violation of the stated current contract on valid inputs '
                                'in the task base? Check preconditions, the claim and evidence. Caller blocking is separate '
                                'and must not erase a demonstrated helper-contract failure. Production exploitation is not '
                                'required. Unknown or unverifiable means false.')
                else:
                    question = ('Does this observation demonstrate the same concrete behavior and violated contract as '
                                'the candidate behavior, including precondition, input, expected and actual outcomes? '
                                'Shared location, function or category alone is insufficient. Unknown means false.')
                view = {'context': context, 'finding': observation}
                if defect is not None:
                    view['behavior'] = {key: defect[key] for key in BEHAVIOR_FIELDS}
                blind, redacted = _blind(view, hidden, physical_roots)
                item = {'id': opaque, 'kind': kind, 'question': question +
                    ' Marked redactions replace known study identifiers, physical arm paths or explicit narrative attribution; if they prevent a decision, answer false.',
                    **blind, 'redacted': redacted}
                if opaque in records:
                    raise ValueError('queue id collision')
                items.append(item)
                records[opaque] = {'kind': kind, 'run': run['id'], 'finding': finding['findingId'],
                                  'seed': None if defect is None else defect['id']}
    items.sort(key=lambda item: item['id'])
    return {'version': 2, 'items': items}, records


def build_queue(manifest, results, salt=DEFAULT_SALT):
    """Return only blind questions, never the private identity association map."""
    return _queue_records(manifest, results, salt)[0]


def _maximum_matching(edges):
    owner = {}
    def augment(finding, seen):
        for seed in sorted(edges.get(finding, ())):
            if seed in seen:
                continue
            seen.add(seed)
            if seed not in owner or augment(owner[seed], seen):
                owner[seed] = finding
                return True
        return False
    for finding in sorted(edges):
        augment(finding, set())
    return owner


def score(manifest, results, verdicts, salt=DEFAULT_SALT):
    """Score exact, complete blind judgments. Raises ValueError on ambiguous data."""
    _, records = _queue_records(manifest, results, salt)
    _object(verdicts, 'verdicts')
    if set(verdicts) != set(records) or any(type(value) is not bool for value in verdicts.values()):
        raise ValueError('verdicts must cover exactly the queue with boolean values')
    real, edges = {}, defaultdict(lambda: defaultdict(set))
    for opaque, record in records.items():
        if record['kind'] == 'real':
            real[(record['run'], record['finding'])] = verdicts[opaque]
    for opaque, record in records.items():
        if record['kind'] == 'semantic' and verdicts[opaque]:
            if not real[(record['run'], record['finding'])]:
                raise ValueError('semantic true contradicts real false')
            edges[record['run']][record['finding']].add(record['seed'])
    runs = results['runs']
    defects = manifest['defects']
    pairs = {r['pair'] for r in runs}
    seeded_tasks = {d['task'] for d in defects}
    caught = defaultdict(int)
    claims = {a: Counter(total=0, real=0, rejected=0, matched=0, duplicate=0, extra=0) for a in ('G', 'K')}
    clean = {a: Counter(runs=0, claims=0, confirmedReal=0, falsePositives=0) for a in ('G', 'K')}
    routing = {a: Counter(graph=0, single=0) for a in ('G', 'K')}
    duration = {}
    for run in runs:
        arm, rid = run['arm'], run['id']
        routing[arm][run['route']] += 1
        duration[(run['task'], run['pair'], arm)] = run['durationNs']
        matched = _maximum_matching(edges[rid])
        matched_findings = set(matched.values())
        for seed in matched:
            caught[(seed, arm)] += 1
        claims[arm]['matched'] += len(matched)
        is_clean = run['task'] not in seeded_tasks
        if is_clean:
            clean[arm]['runs'] += 1
        for finding in run['findings']:
            fid = finding['findingId']
            confirmed = real[(rid, fid)]
            claims[arm]['total'] += 1
            claims[arm]['real' if confirmed else 'rejected'] += 1
            if confirmed and fid not in matched_findings:
                claims[arm]['duplicate' if edges[rid].get(fid) else 'extra'] += 1
            if is_clean:
                clean[arm]['claims'] += 1
                clean[arm]['confirmedReal' if confirmed else 'falsePositives'] += 1
    catches = {arm: Fraction(sum(caught[(d['id'], arm)] for d in defects), len(defects) * len(pairs))
               if defects else Fraction(0) for arm in ('G', 'K')}
    precision = {arm: Fraction(claims[arm]['real'], claims[arm]['total']) if claims[arm]['total']
                 else Fraction(1) for arm in ('G', 'K')}
    wins = sum(caught[(d['id'], 'G')] > caught[(d['id'], 'K')] for d in defects)
    losses = sum(caught[(d['id'], 'G')] < caught[(d['id'], 'K')] for d in defects)
    n = wins + losses
    p = Fraction(sum(math.comb(n, k) for k in range(wins, n + 1)), 2 ** n)
    ratios = sorted(Fraction(duration[(task, pair, 'G')], duration[(task, pair, 'K')])
                    for task, pair, arm in duration if arm == 'G')
    mid = len(ratios) // 2
    median = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    gain = catches['G'] - catches['K']
    conditions = {'gain': gain >= Fraction(1, 4), 'signTest': p <= Fraction(1, 10),
                  'precision': precision['G'] >= precision['K'] - Fraction(1, 10),
                  'cost': median <= 3,
                  'operationalCompleteness': not any(run.get('workFailure') for run in runs
                                                     if run['arm'] == 'G')}
    return {'version': 2, 'outcome': 'WIN' if all(conditions.values()) else 'LOSE',
            'catchRate': {a: str(x) for a, x in catches.items()}, 'gain': str(gain),
            'signTest': {'wins': wins, 'losses': losses, 'ties': len(defects) - n,
                         'pValue': str(p), 'unit': 'unique-defect'},
            'precision': {a: str(x) for a, x in precision.items()}, 'medianCostRatio': str(median),
            'conditions': conditions, 'claims': claims, 'cleanTasks': clean, 'routing': routing,
            'tasks': len({r['task'] for r in runs}), 'pairsPerTask': len(pairs),
            'uniqueDefects': len(defects), 'runs': len(runs),
            'definitions': {'emptyPrecision': '1', 'catchRate': 'unique defects averaged over task pairs',
                            'cleanFalsePositives': 'claims judged not real on tasks with no seeded defects'}}


def _read(path):
    def refuse_constant(value):
        raise ValueError('nonfinite JSON constant ' + value)
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), parse_constant=refuse_constant,
                      object_pairs_hook=object_pairs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('queue', 'score'))
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--results', required=True)
    parser.add_argument('--verdicts')
    parser.add_argument('--output', required=True)
    parser.add_argument('--salt', default=DEFAULT_SALT)
    args = parser.parse_args(argv)
    try:
        manifest, results = _read(args.manifest), _read(args.results)
        _validate(manifest, results, study=True)
        if args.command == 'score':
            if not args.verdicts:
                raise ValueError('score requires --verdicts')
            output = score(manifest, results, _read(args.verdicts), args.salt)
        else:
            if args.verdicts:
                raise ValueError('queue does not accept --verdicts')
            output = build_queue(manifest, results, args.salt)
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    except (ValueError, OSError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
