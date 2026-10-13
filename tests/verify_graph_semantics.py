#!/usr/bin/env python3
"""Synthetic-only regressions for the version 2 blind semantic study oracle."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/graph/scripts/itd_graph_score.py'
if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location('semantic_score', SCRIPT)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
else:
    scorer = None


def fixture(tasks=1, seeds=1):
    manifest = {'version': 2, 'defects': []}
    results = {'version': 2, 'basePath': '/synthetic/base', 'runs': []}
    for task in range(tasks):
        name = 'module-' + str(task)
        for seed in range(seeds):
            manifest['defects'].append({'id': name + '-defect-' + str(seed), 'task': name,
                'function': 'parse', 'contractId': 'reject-empty', 'description': 'Empty input accepted',
                'precondition': 'empty text', 'input': '', 'expected': 'error', 'actual': 'ok',
                'oracleEvidence': 'synthetic assert'})
        for pair in ('GK', 'KG'):
            for arm in ('G', 'K'):
                results['runs'].append({'id': name + pair + arm, 'task': name, 'pair': pair,
                    'arm': arm, 'route': 'graph' if arm == 'G' else 'single', 'durationNs': 100,
                    'findings': []})
    return manifest, results


def finding(number=0, **updates):
    result = {'findingId': 'claim-' + str(number), 'file': '/private/G/hunter/module.js',
        'line': 17, 'function': 'parse', 'contractId': 'reject-empty', 'precondition': 'empty text',
        'input': '', 'expected': 'error', 'actual': 'ok', 'claim': 'Empty input accepted',
        'evidence': 'assert parse returns ok', 'class': 'boundary', 'severity': 'high',
        'origin': 'hunter', 'status': 'confirmed', 'reachability': 'reachable'}
    result.update(updates)
    return result


def add(results, arm='G', count=1):
    for run in results['runs']:
        if run['arm'] == arm:
            run['findings'] = [finding(i) for i in range(count)]


def verdicts(manifest, results, real=True, semantic=True):
    return {item['id']: real if item['kind'] == 'real' else semantic
        for item in scorer.build_queue(manifest, results)['items']}


class SemanticsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(scorer, 'semantic evaluator must exist')

    def test_relative_file_paths_keep_distinct_directory_identity(self):
        m, r = fixture()
        add(r, count=2)
        for run in r['runs']:
            if run['findings']:
                run['findings'][0]['file'] = 'src/imports/format.py'
                run['findings'][1]['file'] = 'lib/export/format.py'
        files = {item['finding']['file'] for item in scorer.build_queue(m, r)['items']}
        self.assertEqual({'src/imports/format.py', 'lib/export/format.py'}, files)
        self.assertEqual('src/imports/format.py', scorer._logical_file('/private/G/hunter/src/imports/format.py', 'module-0'))

    def test_queue_requires_real_and_every_same_task_candidate(self):
        m, r = fixture(seeds=2)
        add(r, count=2)
        q = scorer.build_queue(m, r)
        self.assertEqual(12, len(q['items']))
        self.assertEqual(4, sum(x['kind'] == 'real' for x in q['items']))
        self.assertTrue(all(x['question'] and x['context']['task'] == 'module-0' for x in q['items']))
        self.assertTrue(all(x['context']['basePath'] == '/synthetic/base' for x in q['items']))

    def test_queue_does_not_match_different_tasks(self):
        m, r = fixture(tasks=2)
        add(r)
        q = scorer.build_queue(m, r)
        self.assertEqual(8, len(q['items']))

    def test_queue_blinds_roles_metadata_and_identifiers(self):
        m, r = fixture()
        add(r)
        for run in r['runs']:
            for f in run['findings']:
                f['claim'] = 'hunter and skeptic report graph arm G versus single K'
                f['claim'] += ' claim-0 module-0GKG module-0-defect-0'
        q = scorer.build_queue(m, r)
        encoded = json.dumps(q)
        for word in ('hunter', 'skeptic', 'module-0GKG', 'module-0-defect-0', 'claim-0', 'confirmed', 'boundary', 'severity', 'origin', 'status', 'reachability', '/private/G'):
            self.assertNotIn(word, encoded)
        self.assertIn('[blinded]', encoded)
        self.assertIn('module.js', encoded)
        self.assertIn('redacted', encoded)

    def test_queue_is_deterministic_salted_and_content_bound(self):
        m, r = fixture()
        add(r)
        q = scorer.build_queue(m, r)
        self.assertEqual(q, scorer.build_queue(m, r))
        self.assertNotEqual(q, scorer.build_queue(m, r, salt='other'))
        r['runs'][0]['findings'][0]['actual'] = 'crash'
        self.assertNotEqual(q['items'][0]['id'], scorer.build_queue(m, r)['items'][0]['id'])

    def test_file_line_class_never_auto_credit(self):
        m, r = fixture()
        add(r)
        s = scorer.score(m, r, verdicts(m, r, semantic=False))
        self.assertEqual(Fraction(0), Fraction(s['catchRate']['G']))
        self.assertEqual(Fraction(1), Fraction(s['precision']['G']))
        self.assertEqual('LOSE', s['outcome'])

    def test_real_false_cannot_semantically_match(self):
        m, r = fixture()
        add(r)
        with self.assertRaises(ValueError):
            scorer.score(m, r, verdicts(m, r, real=False))

    def test_unknown_and_unverifiable_need_judgment(self):
        m, r = fixture()
        add(r)
        for run in r['runs']:
            for f in run['findings']:
                f.update(status='unknown', reachability='unverifiable')
        s = scorer.score(m, r, verdicts(m, r, real=False, semantic=False))
        self.assertEqual('0', s['precision']['G'])
        self.assertEqual('0', s['catchRate']['G'])

    def test_maximum_matching_not_greedy(self):
        m, r = fixture(seeds=2)
        add(r, count=2)
        v = verdicts(m, r)
        for pair in ('GK', 'KG'):
            run = next(x for x in r['runs'] if x['pair'] == pair and x['arm'] == 'G')
            # f0 matches both; f1 only d0. Greedy f0->d0 would lose d1.
            private = scorer._queue_records(m, r, 'fixed-study-v2')[1]
            for opaque, record in private.items():
                if record['run'] == run['id'] and record['kind'] == 'semantic' and record['finding'] == 'claim-1' and record['seed'] == 'module-0-defect-1':
                    v[opaque] = False
        s = scorer.score(m, r, v)
        self.assertEqual('1', s['catchRate']['G'])
        self.assertEqual(4, s['claims']['G']['matched'])

    def test_single_finding_never_credits_multiple_defects(self):
        m, r = fixture(seeds=2)
        add(r)
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('1/2', s['catchRate']['G'])

    def test_duplicate_claims_count_in_precision_and_duplicates(self):
        m, r = fixture()
        add(r, count=3)
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('1', s['catchRate']['G'])
        self.assertEqual(6, s['claims']['G']['total'])
        self.assertEqual(4, s['claims']['G']['duplicate'])
        self.assertEqual('1', s['precision']['G'])

    def test_unmatched_real_claims_are_extra(self):
        m, r = fixture()
        add(r)
        s = scorer.score(m, r, verdicts(m, r, semantic=False))
        self.assertEqual(2, s['claims']['G']['extra'])

    def test_sign_test_uses_unique_defects_and_exact_fractions(self):
        m, r = fixture(tasks=4)
        add(r)
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('1/16', s['signTest']['pValue'])
        self.assertEqual(4, s['signTest']['wins'])
        self.assertEqual('1', s['gain'])
        self.assertEqual('WIN', s['outcome'])

    def test_pair_average_preserves_fractional_catches(self):
        m, r = fixture()
        r['runs'][0]['findings'] = [finding()]
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('1/2', s['catchRate']['G'])
        self.assertEqual('1/2', s['signTest']['pValue'])

    def test_tied_defects_excluded_from_sign_test(self):
        m, r = fixture()
        add(r, 'G')
        add(r, 'K')
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual(0, s['signTest']['wins'])
        self.assertEqual(1, s['signTest']['ties'])
        self.assertEqual('1', s['signTest']['pValue'])

    def test_median_cost_uses_all_pairs_including_clean_tasks(self):
        m, r = fixture(tasks=2)
        m['defects'] = m['defects'][:1]
        for run in r['runs']:
            if run['task'] == 'module-1' and run['arm'] == 'G':
                run['durationNs'] = 700
        s = scorer.score(m, r, {})
        self.assertEqual('4', s['medianCostRatio'])
        self.assertFalse(s['conditions']['cost'])
        self.assertEqual(4, s['routing']['G']['graph'])

    def test_clean_false_positives_are_judged_and_reported(self):
        m, r = fixture(seeds=0)
        add(r)
        s = scorer.score(m, r, verdicts(m, r, real=False))
        self.assertEqual(2, s['cleanTasks']['G']['falsePositives'])
        self.assertEqual('0', s['precision']['G'])
        self.assertEqual('0', s['catchRate']['G'])
        self.assertEqual('LOSE', s['outcome'])

    def test_precision_and_cost_gate_win(self):
        m, r = fixture(tasks=4)
        add(r, count=2)
        v = verdicts(m, r)
        records = scorer._queue_records(m, r, 'fixed-study-v2')[1]
        for key, rec in records.items():
            if rec['finding'] == 'claim-1':
                v[key] = False
        s = scorer.score(m, r, v)
        self.assertFalse(s['conditions']['precision'])
        self.assertEqual('LOSE', s['outcome'])
        for run in r['runs']:
            if run['arm'] == 'G':
                run['durationNs'] = 301
        s = scorer.score(m, r, verdicts(m, r))
        self.assertFalse(s['conditions']['cost'])
        self.assertEqual('LOSE', s['outcome'])

    def test_verdicts_are_complete_exact_and_boolean_only(self):
        m, r = fixture()
        add(r)
        good = verdicts(m, r)
        variants = [{}, dict(good, foreign=True)]
        for bad in (1, 0, 'true', None, float('nan')):
            candidate = dict(good)
            candidate[next(iter(candidate))] = bad
            variants.append(candidate)
        for v in variants:
            with self.subTest(v=v), self.assertRaises(ValueError):
                scorer.score(m, r, v)

    def test_invalid_study_shapes_are_refused(self):
        m, r = fixture()
        cases = []
        a = copy.deepcopy(r); a['runs'].pop(); cases.append((m, a))
        a = copy.deepcopy(r); a['runs'].append(copy.deepcopy(a['runs'][0])); cases.append((m, a))
        for value in (0, -1, True, 1.5, float('nan')):
            a = copy.deepcopy(r); a['runs'][0]['durationNs'] = value; cases.append((m, a))
        a = copy.deepcopy(r); a['runs'][0]['arm'] = 'X'; cases.append((m, a))
        a = copy.deepcopy(r); a['runs'][1]['route'] = 'graph'; cases.append((m, a))
        a = copy.deepcopy(m); a['defects'].append(copy.deepcopy(a['defects'][0])); cases.append((a, r))
        a = copy.deepcopy(m); a['defects'][0]['task'] = 'foreign'; cases.append((a, r))
        a = copy.deepcopy(r); a['runs'][0]['findings'] = [finding(), finding()]; cases.append((m, a))
        a = copy.deepcopy(r); a['runs'][0]['findings'] = [finding(input=float('nan'))]; cases.append((m, a))
        for a, b in cases:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                scorer.build_queue(a, b)

    def test_exact_precision_and_cost_thresholds_are_inclusive(self):
        m, r = fixture(tasks=4)
        add(r, count=10)
        for run in r['runs']:
            if run['arm'] == 'G':
                run['durationNs'] = 300
        v = verdicts(m, r)
        for opaque, rec in scorer._queue_records(m, r)[1].items():
            if rec['finding'] == 'claim-9':
                v[opaque] = False
        s = scorer.score(m, r, v)
        self.assertEqual('9/10', s['precision']['G'])
        self.assertEqual('3', s['medianCostRatio'])
        self.assertTrue(s['conditions']['precision'])
        self.assertTrue(s['conditions']['cost'])
        self.assertEqual('WIN', s['outcome'])

    def test_three_unique_wins_fail_significance(self):
        m, r = fixture(tasks=3)
        add(r)
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('1/8', s['signTest']['pValue'])
        self.assertFalse(s['conditions']['signTest'])
        self.assertEqual('LOSE', s['outcome'])

    def test_conditional_single_route_allowed_and_counted(self):
        m, r = fixture()
        r['runs'][0]['route'] = 'single'
        s = scorer.score(m, r, {})
        self.assertEqual(1, s['routing']['G']['single'])
        self.assertEqual(1, s['routing']['G']['graph'])

    def test_cli_rejects_duplicate_verdict_keys_and_writes_nothing(self):
        m, r = fixture(tasks=8)
        add(r)
        v = verdicts(m, r)
        key = next(iter(v))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'm.json').write_text(json.dumps(m))
            (p / 'r.json').write_text(json.dumps(r))
            (p / 'v.json').write_text('{"' + key + '":true,"' + key + '":false}')
            output = p / 'out.json'
            proc = subprocess.run([sys.executable, str(SCRIPT), 'score', '--manifest', str(p / 'm.json'),
                '--results', str(p / 'r.json'), '--verdicts', str(p / 'v.json'), '--output', str(output)], capture_output=True)
            self.assertNotEqual(0, proc.returncode)
            self.assertFalse(output.exists())
            self.assertIn(b'duplicate JSON key', proc.stderr)
    def test_mutation_helper_refuses_missing_repeated_and_noop_markers(self):
        for source, marker, replacement in (('a a', 'a', 'b'), ('a', 'z', 'b'), ('a', 'a', 'a')):
            with self.subTest(source=source, marker=marker), self.assertRaises(ValueError):
                _mutate_source(source, marker, replacement)
        self.assertEqual('b', _mutate_source('a', 'a', 'b'))


    def test_real_question_preserves_helper_contract_failures(self):
        m, r = fixture()
        add(r)
        for run in r['runs']:
            for f in run['findings']:
                f.update(claim='Helper violates current contract; caller blocking prevents external use', reachability='caller-blocked')
        q = scorer.build_queue(m, r)
        for item in q['items']:
            if item['kind'] == 'real':
                self.assertIn('current contract', item['question'])
                self.assertIn('valid inputs', item['question'])
                self.assertIn('Caller blocking', item['question'])
                self.assertIn('must not erase', item['question'])
                self.assertNotIn('real, reachable', item['question'])
        self.assertEqual('1', scorer.score(m, r, verdicts(m, r))['catchRate']['G'])

    def test_run_public_base_path_overrides_global_base(self):
        m, r = fixture(tasks=2)
        add(r)
        for run in r['runs']:
            run['basePath'] = '/public/pinned/' + run['task']
        q = scorer.build_queue(m, r)
        for item in q['items']:
            self.assertEqual('/public/pinned/' + item['context']['task'], item['context']['basePath'])

    def test_semantic_values_preserve_legitimate_role_like_words(self):
        m, r = fixture()
        add(r)
        value = {'k': 'single item', 'G': 'graph traversal', 'control': 'control flow'}
        evidence = "assert parse({'k': 'single item'}) == 'control flow'; graph traversal"
        for run in r['runs']:
            for f in run['findings']:
                f.update(input=value, expected='single item', actual='control flow', evidence=evidence,
                         claim='A single item breaks control flow during graph traversal')
        q = scorer.build_queue(m, r)
        for item in q['items']:
            self.assertEqual(value, item['finding']['input'])
            self.assertEqual('single item', item['finding']['expected'])
            self.assertEqual('control flow', item['finding']['actual'])
            self.assertEqual(evidence, item['finding']['evidence'])
            self.assertEqual('A single item breaks control flow during graph traversal', item['finding']['claim'])

    def test_explicit_english_and_russian_narrative_attribution_is_blinded(self):
        m, r = fixture()
        add(r)
        for run in r['runs']:
            for f in run['findings']:
                f['claim'] = 'According to the hunter: empty input accepted; по данным скептика: helper violates contract'
        q = scorer.build_queue(m, r)
        for item in q['items']:
            self.assertNotIn('hunter', item['finding']['claim'])
            self.assertNotIn('скептика', item['finding']['claim'])
            self.assertIn('empty input accepted', item['finding']['claim'])
            self.assertTrue(item['redacted'])

    def test_attribution_inside_semantic_evidence_refuses_instead_of_rewriting(self):
        m, r = fixture()
        add(r)
        r['runs'][0]['findings'][0]['evidence'] = 'According to the skeptic, parse returns ok'
        with self.assertRaisesRegex(ValueError, 'attribution'):
            scorer.build_queue(m, r)

    def test_physical_arm_root_removed_from_evidence_only_known_prefix(self):
        m, r = fixture()
        add(r)
        r['runs'][0]['findings'][0]['evidence'] = 'assert /private/G/hunter/module.js:17 returns a single item'
        with self.assertRaises(ValueError):
            scorer.build_queue(m, r)
        r['runs'][0]['findings'][0]['evidence'] = 'assert parse returns ok'
        for run in r['runs']:
            for f in run['findings']:
                f['claim'] = 'assert /private/G/hunter/module.js:17 returns a single item'
        m['defects'][0]['description'] = 'assert /private/G/hunter/module.js:17 returns a single item'
        for item in scorer.build_queue(m, r)['items']:
            self.assertEqual('assert module.js:17 returns a single item', item['finding']['claim'])
            self.assertEqual('assert parse returns ok', item['finding']['evidence'])
            if item['kind'] == 'semantic':
                self.assertEqual('assert module.js:17 returns a single item', item['behavior']['description'])
            self.assertTrue(item['redacted'])

    def test_hidden_identifiers_in_semantic_values_refuse_instead_of_rewriting(self):
        for identifier in ('claim-0', 'module-0GKG', 'module-0-defect-0'):
            for field in ('function', 'contractId', 'precondition', 'input', 'expected', 'actual', 'evidence'):
                with self.subTest(identifier=identifier, field=field):
                    m, r = fixture()
                    add(r)
                    r['runs'][0]['findings'][0][field] = 'literal ' + identifier
                    with self.assertRaises(ValueError):
                        scorer.build_queue(m, r)
            for field in ('function', 'contractId', 'precondition', 'input', 'expected', 'actual'):
                with self.subTest(identifier=identifier, behaviorField=field):
                    m, r = fixture()
                    add(r)
                    m['defects'][0][field] = 'literal ' + identifier
                    with self.assertRaises(ValueError):
                        scorer.build_queue(m, r)
        m, r = fixture()
        add(r)
        r['runs'][0]['findings'][0]['input'] = {'claim': ['literal claim-0']}
        with self.assertRaises(ValueError):
            scorer.build_queue(m, r)

    def test_known_physical_roots_in_semantic_values_and_keys_refuse(self):
        collision = '/private/G/hunter/module.js'
        for field in ('function', 'contractId', 'precondition', 'input', 'expected', 'actual', 'evidence'):
            with self.subTest(field=field):
                m, r = fixture()
                add(r)
                r['runs'][0]['findings'][0][field] = collision
                with self.assertRaises(ValueError):
                    scorer.build_queue(m, r)
        for field in ('function', 'contractId', 'precondition', 'input', 'expected', 'actual'):
            with self.subTest(behaviorField=field):
                m, r = fixture()
                add(r)
                m['defects'][0][field] = collision
                with self.assertRaises(ValueError):
                    scorer.build_queue(m, r)
        for payload in ({'claim': [collision]}, {collision: 'literal'}):
            with self.subTest(payload=payload):
                m, r = fixture()
                add(r)
                r['runs'][0]['findings'][0]['input'] = payload
                with self.assertRaises(ValueError):
                    scorer.build_queue(m, r)


    def test_nested_claim_key_does_not_make_semantic_input_narrative(self):
        m, r = fixture()
        add(r)
        r['runs'][0]['findings'][0]['input'] = {'claim': 'According to the hunter'}
        with self.assertRaisesRegex(ValueError, 'attribution'):
            scorer.build_queue(m, r)

    def test_public_base_path_refuses_measured_arm_directory(self):
        m, r = fixture()
        add(r)
        r['runs'][0]['basePath'] = '/private/G/hunter'
        with self.assertRaisesRegex(ValueError, 'public pinned base'):
            scorer.build_queue(m, r)

    def test_semantic_key_identity_collision_refuses_instead_of_collapsing(self):
        m, r = fixture()
        add(r)
        r['runs'][0]['findings'][0]['input'] = {'claim-0': 1, 'module-0-defect-0': 2}
        with self.assertRaisesRegex(ValueError, 'semantic key'):
            scorer.build_queue(m, r)


    def test_g_work_failure_vetoes_win_after_four_metric_conditions_pass(self):
        m, r = fixture(tasks=8)
        add(r)
        failed = next(run for run in r['runs'] if run['arm'] == 'G')
        failed['findings'] = []
        for failure in (True, 'worker timeout', 1, ['missing output'], {'stage': 'worker'}):
            with self.subTest(workFailure=failure):
                failed['workFailure'] = failure
                s = scorer.score(m, r, verdicts(m, r))
                self.assertEqual(32, s['runs'])
                self.assertTrue(all(s['conditions'][key] for key in ('gain', 'signTest', 'precision', 'cost')))
                self.assertEqual('15/16', s['catchRate']['G'])
                self.assertEqual('1/256', s['signTest']['pValue'])
                self.assertEqual('LOSE', s['outcome'])
                self.assertFalse(s['conditions']['operationalCompleteness'])

    def test_missing_and_falsey_work_failure_preserve_legacy_win(self):
        m, r = fixture(tasks=8)
        add(r)
        baseline = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('WIN', baseline['outcome'])
        self.assertTrue(baseline['conditions']['operationalCompleteness'])
        for failure in (False, None, '', 0, [], {}):
            with self.subTest(workFailure=failure):
                for run in r['runs']:
                    run['workFailure'] = failure
                s = scorer.score(m, r, verdicts(m, r))
                self.assertEqual(baseline, s)

    def test_k_work_failure_does_not_veto_g_win(self):
        m, r = fixture(tasks=8)
        add(r)
        for run in r['runs']:
            if run['arm'] == 'K':
                run['workFailure'] = 'control worker failed'
        s = scorer.score(m, r, verdicts(m, r))
        self.assertEqual('WIN', s['outcome'])
        self.assertTrue(s['conditions']['operationalCompleteness'])

    def test_cli_full_study_g_work_failure_veto(self):
        m, r = fixture(tasks=8)
        add(r)
        failed = next(run for run in r['runs'] if run['arm'] == 'G')
        failed.update(workFailure='worker timeout', findings=[])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name, value in (('m', m), ('r', r), ('v', verdicts(m, r))):
                (p / (name + '.json')).write_text(json.dumps(value))
            output = p / 'score.json'
            proc = subprocess.run([sys.executable, str(SCRIPT), 'score', '--manifest', str(p / 'm.json'),
                '--results', str(p / 'r.json'), '--verdicts', str(p / 'v.json'), '--output', str(output)], capture_output=True)
            self.assertEqual(0, proc.returncode, proc.stderr)
            s = json.loads(output.read_text())
            self.assertTrue(all(s['conditions'][key] for key in ('gain', 'signTest', 'precision', 'cost')))
            self.assertEqual('LOSE', s['outcome'])
            self.assertFalse(s['conditions']['operationalCompleteness'])

    def test_inputs_are_not_mutated(self):
        m, r = fixture()
        add(r)
        before = copy.deepcopy((m, r))
        scorer.score(m, r, verdicts(m, r))
        self.assertEqual(before, (m, r))

    def test_cli_full_eight_task_study_and_refusal(self):
        m, r = fixture(tasks=8)
        add(r)
        with tempfile.TemporaryDirectory() as tmp:
            paths = {name: Path(tmp) / (name + '.json') for name in ('manifest', 'results', 'verdicts', 'queue', 'score')}
            for name, obj in (('manifest', m), ('results', r), ('verdicts', verdicts(m, r))):
                paths[name].write_text(json.dumps(obj), encoding='utf-8')
            args = ['--manifest', str(paths['manifest']), '--results', str(paths['results'])]
            p = subprocess.run([sys.executable, str(SCRIPT), 'queue', *args, '--output', str(paths['queue'])], capture_output=True)
            self.assertEqual(0, p.returncode, p.stderr)
            self.assertEqual(32, len(json.loads(paths['queue'].read_text())['items']))
            p = subprocess.run([sys.executable, str(SCRIPT), 'score', *args, '--verdicts', str(paths['verdicts']), '--output', str(paths['score'])], capture_output=True)
            self.assertEqual(0, p.returncode, p.stderr)
            self.assertEqual('WIN', json.loads(paths['score'].read_text())['outcome'])
            small_manifest, small_results = fixture()
            paths['manifest'].write_text(json.dumps(small_manifest))
            paths['results'].write_text(json.dumps(small_results))
            paths['queue'].unlink()
            p = subprocess.run([sys.executable, str(SCRIPT), 'queue', *args, '--output', str(paths['queue'])], capture_output=True)
            self.assertNotEqual(0, p.returncode)
            self.assertFalse(paths['queue'].exists())
            paths['results'].write_text('{"version":2,"runs":NaN}')
            p = subprocess.run([sys.executable, str(SCRIPT), 'queue', *args, '--output', str(paths['queue'])], capture_output=True)
            self.assertNotEqual(0, p.returncode)




def _mutate_source(source, marker, replacement):
    """Refuse ambiguous/non-applied mutations; never call those coverage evidence."""
    if source.count(marker) != 1:
        raise ValueError('mutation marker must occur exactly once')
    if marker == replacement:
        raise ValueError('mutation must change source')
    return source.replace(marker, replacement)


def run_mutations():
    """Each mutation must make its selected regression fail; sources stay untouched."""
    global scorer, SCRIPT
    import io
    import types
    original_source = SCRIPT.read_text(encoding='utf-8-sig')
    cases = [
        ('relative location identity', "return '/'.join(parts)\n    roles =", "return parts[-1]\n    roles =", 'test_relative_file_paths_keep_distinct_directory_identity'),
        ('all real questions', 'for defect in [None] + by_task[run[\'task\']]:', 'for defect in by_task[run[\'task\']]:', 'test_queue_requires_real_and_every_same_task_candidate'),
        ('same task only', "[None] + by_task[run['task']]", '[None] + defects', 'test_queue_does_not_match_different_tasks'),
        ('blind roles', 'return walk(value), changed', 'return value, False', 'test_queue_blinds_roles_metadata_and_identifiers'),
        ('salt binding', '_canonical([salt, binding, kind,', "_canonical(['ignored', binding, kind,", 'test_queue_is_deterministic_salted_and_content_bound'),
        ('no automatic credit', "if record['kind'] == 'semantic' and verdicts[opaque]:", "if record['kind'] == 'semantic':", 'test_file_line_class_never_auto_credit'),
        ('real contradiction', "if not real[(record['run'], record['finding'])]:", 'if False:', 'test_real_false_cannot_semantically_match'),
        ('unknown judgments', 'confirmed = real[(rid, fid)]', 'confirmed = True', 'test_unknown_and_unverifiable_need_judgment'),
        ('augmenting paths', 'seed not in owner or augment(owner[seed], seen)', 'seed not in owner', 'test_maximum_matching_not_greedy'),
        ('one seed per claim', 'return owner\n\n\ndef score', "return {s: f for f in edges for s in edges[f]}\n\n\ndef score", 'test_single_finding_never_credits_multiple_defects'),
        ('duplicate accounting', "claims[arm]['duplicate' if edges[rid].get(fid) else 'extra'] += 1", "claims[arm]['extra'] += 1", 'test_duplicate_claims_count_in_precision_and_duplicates'),
        ('extra accounting', "claims[arm]['duplicate' if edges[rid].get(fid) else 'extra'] += 1", "claims[arm]['duplicate'] += 1", 'test_unmatched_real_claims_are_extra'),
        ('unique sign unit', '2 ** n)', '2 ** (n * len(pairs)))', 'test_sign_test_uses_unique_defects_and_exact_fractions'),
        ('pair averaging', 'len(defects) * len(pairs))', 'len(defects))', 'test_pair_average_preserves_fractional_catches'),
        ('sign ties', "'ties': len(defects) - n,", "'ties': 0,", 'test_tied_defects_excluded_from_sign_test'),
        ('clean costs', "for task, pair, arm in duration if arm == 'G')", "for task, pair, arm in duration if arm == 'G' and task in seeded_tasks)", 'test_median_cost_uses_all_pairs_including_clean_tasks'),
        ('clean false positives', "clean[arm]['confirmedReal' if confirmed else 'falsePositives'] += 1", "clean[arm]['confirmedReal'] += 1", 'test_clean_false_positives_are_judged_and_reported'),
        ('precision gate', "precision['G'] >= precision['K'] - Fraction(1, 10)", 'True', 'test_precision_and_cost_gate_win'),
        ('bool only', 'type(value) is not bool', 'not isinstance(value, (bool, int))', 'test_verdicts_are_complete_exact_and_boolean_only'),
        ('duration guard', 'type(duration) is not int or duration <= 0', 'False', 'test_invalid_study_shapes_are_refused'),
        ('input purity', "pairs = {r['pair'] for r in runs}", "results['mutated'] = True\n    pairs = {r['pair'] for r in runs}", 'test_inputs_are_not_mutated'),
        ('CLI study size', "len(tasks) != 8 or pairs != {'GK', 'KG'}", 'False', 'test_cli_full_eight_task_study_and_refusal'),
        ('inclusive thresholds', 'median <= 3', 'median < 3', 'test_exact_precision_and_cost_thresholds_are_inclusive'),
        ('significance gate', 'p <= Fraction(1, 10)', 'p <= Fraction(1, 8)', 'test_three_unique_wins_fail_significance'),
        ('conditional routing', "routing[arm][run['route']] += 1", "routing[arm]['graph' if arm == 'G' else 'single'] += 1", 'test_conditional_single_route_allowed_and_counted'),
        ('duplicate JSON refusal', 'if key in result:', 'if False:', 'test_cli_rejects_duplicate_verdict_keys_and_writes_nothing'),
        ('G work failure veto', "not any(run.get('workFailure') for run in runs\n                                                     if run['arm'] == 'G')", 'True', 'test_g_work_failure_vetoes_win_after_four_metric_conditions_pass'),
        ('legacy missing failure', "run.get('workFailure')", "run.get('workFailure', True)", 'test_missing_and_falsey_work_failure_preserve_legacy_win'),
        ('K failure not a veto', "not any(run.get('workFailure') for run in runs\n                                                     if run['arm'] == 'G')", "not any(run.get('workFailure') for run in runs)", 'test_k_work_failure_does_not_veto_g_win'),
        ('CLI operational veto', 'all(conditions.values())', "all(value for key, value in conditions.items() if key != 'operationalCompleteness')", 'test_cli_full_study_g_work_failure_veto'),

        ('valid helper contract', 'and must not erase a demonstrated helper-contract failure.', 'and should erase a demonstrated helper-contract failure.', 'test_real_question_preserves_helper_contract_failures'),
        ('per run public base', "base_path = run.get('basePath', results.get('basePath'))", "base_path = results.get('basePath')", 'test_run_public_base_path_overrides_global_base'),
        ('semantic payload preserved', 'if narrative:\n                out = ORIGIN_PHRASES', 'if True:\n                out = re.sub(r"\\b(?:k|G|single|control|graph)\\b", "[blinded]", out)\n                out = ORIGIN_PHRASES', 'test_semantic_values_preserve_legitimate_role_like_words'),
        ('explicit attribution', "out = ORIGIN_PHRASES.sub('[blinded]', out)", 'out = out', 'test_explicit_english_and_russian_narrative_attribution_is_blinded'),
        ('semantic attribution refusal', 'elif ORIGIN_PHRASES.search(out) or ARM_PHRASES.search(out):', 'elif False:', 'test_attribution_inside_semantic_evidence_refuses_instead_of_rewriting'),
        ('semantic hidden identifier refusal', "if not narrative and any(re.search(r'(?<!\\w)' + re.escape(identifier) + r'(?!\\w)', out) for identifier in hidden):", 'if False:', 'test_hidden_identifiers_in_semantic_values_refuse_instead_of_rewriting'),
        ('semantic physical prefix refusal', 'if not narrative and any(root in out for root in physical_roots):', 'if False:', 'test_physical_arm_root_removed_from_evidence_only_known_prefix'),
        ('nested semantics preserved', "(depth == 1 and key in ('claim', 'description'))", "key in ('claim', 'description')", 'test_nested_claim_key_does_not_make_semantic_input_narrative'),
        ('public base clone refusal', "if parts & {run['id'], 'G', 'K', 'GK', 'KG', 'hunter', 'skeptic'}:\n                    raise ValueError('basePath", "if False:\n                    raise ValueError('basePath", 'test_public_base_path_refuses_measured_arm_directory'),
        ('semantic key refusal', "if any(re.search(r'(?<!\\w)' + re.escape(identifier) + r'(?!\\w)', key) for identifier in hidden):", 'if False:', 'test_semantic_key_identity_collision_refuses_instead_of_collapsing'),

    ]
    original_scorer, original_script = scorer, SCRIPT
    rejected = 0
    for label, marker, replacement, test in cases:
        source = _mutate_source(original_source, marker, replacement)
        namespace = {'__name__': 'semantic_score_mutant'}
        exec(compile(source, '<semantic-score-mutant>', 'exec'), namespace)
        scorer = types.SimpleNamespace(**namespace)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                SCRIPT = Path(tmp) / 'mutant.py'
                SCRIPT.write_text(source, encoding='utf-8')
                result = unittest.TextTestRunner(stream=io.StringIO()).run(SemanticsTests(test))
                if result.wasSuccessful():
                    raise AssertionError('surviving mutation: ' + label)
                rejected += 1
                print('MUTATION REJECTED ' + label)
        finally:
            scorer, SCRIPT = original_scorer, original_script
    print('MUTATIONS: ' + str(rejected) + '/' + str(len(cases)) + ' rejected')

if __name__ == '__main__':
    if '--mutations' in sys.argv:
        run_mutations()
    else:
        unittest.main(verbosity=2)
