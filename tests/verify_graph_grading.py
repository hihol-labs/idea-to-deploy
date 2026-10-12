#!/usr/bin/env python3
"""Independent blind-grading transport regressions; synthetic queue/native evidence only."""
import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADE = ROOT / 'scripts/graph_v2_grade.py'
NATIVE = ROOT / 'scripts/graph_v2_native.py'
RESULT = ROOT / 'tests/verify_graph_study_result.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GradingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-blind-grading-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.g = load(GRADE, 'synthetic_grading')
        self.g.GRADER_PREFIX = 'gv2_grade'
        self.native = load(NATIVE, 'synthetic_grading_native')
        self.result = load(RESULT, 'synthetic_result_verifier')
        self.g.ROOT = self.home
        self.g.D = self.home / '.itd-memory/graph-v2-study'
        self.base_inventories = {}
        self.g.write(self.g.D / 'freeze.json', {'projectRoot': str(self.home), 'baseInventories': self.base_inventories})
        self.parents, self.paths = [], {}
        self.n = types.SimpleNamespace(
            OLD=self.native.OLD, NativeSnapshot=self.native.NativeSnapshot, strict=self.native.strict,
            config=lambda: {'parentThreadId': 'synthetic-parent'},
            terminal_status=self.native.terminal_status, final_from=self.native.final_from,
            dispatch_args_match=self.native.dispatch_args_match, parent_rows=lambda: self.parents,
            native_rows=lambda actor: (self.paths[actor], self.native.NativeSnapshot(self.paths[actor].read_bytes())))
        self.g.load = lambda path: self.n if path.name == 'graph_v2_native.py' else types.SimpleNamespace(replay=lambda: {'synthetic': True})
        self.items = self.queue_items(2, 2)
        self.g.write(self.g.D / 'queue.json', {'items': self.items})
        self.g.write(self.g.D / 'collection-verification.json', {'synthetic': True})
        self.g.initialize()

    def queue_items(self, real, semantic):
        for i in range(max(real, semantic)):
            relative = '.itd-memory/graph-v2-study/public/bases/S' + str(i)
            base = self.home / relative
            base.mkdir(parents=True, exist_ok=True)
            files = {'src.py': 'def calculate(value):\n    return value + ' + str(i) + '\n',
                     'CONTRACT.md': 'calculate preserves its stated integer contract.\n'}
            inventory = {}
            for name, text in files.items():
                (base / name).write_text(text, encoding='utf-8')
                inventory[name] = hashlib.sha256(text.encode()).hexdigest()
            self.base_inventories[base.relative_to(self.g.D).as_posix()] = inventory
        self.g.write(self.g.D / 'freeze.json', {'projectRoot': str(self.home), 'baseInventories': self.base_inventories})
        return [{'id': kind + '-opaque-' + str(i).zfill(4), 'kind': kind,
                 'question': 'Synthetic independent question ' + str(i),
                 'context': {'basePath': str(self.home / '.itd-memory/graph-v2-study/public/bases' / ('S' + str(i))),
                             'task': 'Check the stated calculate contract.'}}
                for kind, count in (('real', real), ('semantic', semantic)) for i in range(count)]

    def answers(self, index=0):
        return {item['id']: False for item in self.g.read(self.g.D / 'grading/batches' / (str(index) + '.json'))['items']}

    def dispatch(self, index=0, value=None, final_text=None, session=None):
        expected = self.g.launch(index)
        actor = '/root/' + expected['task_name']
        call_id = 'synthetic-grader-call-' + expected['task_name']
        self.parents.extend([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                'call_id': call_id, 'arguments': json.dumps(expected)}},
            {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': call_id,
                'output': json.dumps({'task_name': actor})}}])
        rows = [
            {'type': 'session_meta', 'payload': {'id': session or 'synthetic-session-' + expected['task_name'],
                'source': {'subagent': {'thread_spawn': {'parent_thread_id': 'synthetic-parent', 'agent_path': actor}}}}},
            {'type': 'turn_context', 'payload': {'model': 'gpt-6.1-sol', 'effort': 'high'}},
            {'type': 'event_msg', 'payload': {'type': 'task_started'}},
            self.accepted_read(self.g.transport_path(self.g.D / 'grading/batches' / (str(index) + '.json')))[0],
            {'type': 'response_item', 'timestamp': '2026-10-11T00:00:00+00:00',
                'payload': {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
                            'content': [{'type': 'output_text', 'text': final_text if final_text is not None else
                                         json.dumps(self.answers(index) if value is None else value)}]}},
            {'type': 'event_msg', 'payload': {'type': 'task_complete'}}]
        path = self.home / (expected['task_name'] + '.jsonl')
        path.write_bytes(b''.join((json.dumps(row) + '\n').encode() for row in rows))
        self.paths[actor] = path
        return actor, path

    def audit_rows(self, command):
        return [{'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
                'input': 'text(await tools.exec_command({cmd:' + json.dumps(command) + '}));'}}]

    def accepted_read(self, path):
        return [{'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
                'input': self.g.read_code(path)}}]

    def test_grader_namespace_separates_new_study_actor_identity(self):
        before = self.g.launch(0)['task_name']
        self.g.GRADER_PREFIX = 'gv2r2_grade'
        after = self.g.launch(0)['task_name']
        self.assertNotEqual(before, after)
        self.assertEqual('gv2r2_grade_0', after)

    def test_partition_keeps_exact_questions_and_kind_specific_batch_limits(self):
        items = self.queue_items(141, 161)
        self.g.write(self.g.D / 'queue.json', {'items': items})
        batches = self.g.batches()
        for batch in batches:
            self.assertEqual(3, batch['version'])
            self.assertTrue(batch['items'])
            self.assertLessEqual(len(batch['items']), 70 if batch['kind'] == 'real' else 80)
            self.assertEqual({batch['kind']}, {item['kind'] for item in batch['items']})
            self.assertLessEqual(len(json.dumps(batch, ensure_ascii=False, indent=2).encode('utf-8')) + 1, 18000)
        self.assertEqual(batches, self.g.batches())
        self.assertEqual(items, [item for batch in batches for item in batch['items']])

    def test_capsule_limit_counts_utf8_bytes_instead_of_characters(self):
        items = copy.deepcopy(self.queue_items(0, 2))
        for item in items:
            item['question'] = 'Ж' * 5000
        self.g.write(self.g.D / 'queue.json', {'items': items})
        combined = {'version': 3, 'kind': 'semantic', 'items': items, 'sources': []}
        text = json.dumps(combined, ensure_ascii=False, indent=2) + '\n'
        self.assertLess(len(text), 18000)
        self.assertGreater(len(text.encode('utf-8')), 18000)
        batches = self.g.batches()
        self.assertEqual([1, 1], [len(batch['items']) for batch in batches])
        self.assertEqual(items, [item for batch in batches for item in batch['items']])
        for batch in batches:
            self.assertLessEqual(len((json.dumps(batch, ensure_ascii=False, indent=2) + '\n').encode('utf-8')), 18000)

    def test_freeze_refuses_queue_collection_partition_and_attempt_ledger_edits(self):
        for relative in ('queue.json', 'collection-verification.json', 'grading/attempts.json', 'grading/batches/0.json'):
            path = self.g.D / relative
            before = path.read_bytes()
            data = self.g.read(path)
            data['unapproved-edit'] = True
            self.g.write(path, data)
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.g.frozen()
            path.write_bytes(before)
        with self.assertRaises(ValueError):
            self.g.initialize()

    def test_exact_native_boolean_map_is_accepted_and_bound_to_snapshot(self):
        self.dispatch()
        value, audit = self.g.collect(0)
        self.assertEqual(self.answers(), value)
        raw = (self.g.D / 'grading/native' / (audit['nativeSha256'] + '.jsonl')).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), audit['nativeSha256'])
        self.result.native_proof(audit, raw, self.n, 'synthetic-parent', audit['agent'])

    def test_collect_replay_refuses_stored_audit_identity_and_binding_tamper(self):
        self.dispatch()
        value, audit = self.g.collect(0)
        path = self.g.D / 'grading/audits/0.json'
        variants = []
        for field, replacement in (('sessionId', 'foreign-session'), ('agent', '/root/foreign-agent'),
                                   ('models', ['foreign-model']), ('efforts', ['low'])):
            bad = copy.deepcopy(audit)
            bad[field] = replacement
            variants.append((field, bad))
        for side, field, replacement in (('call', 'name', 'foreign-tool'),
                                         ('return', 'call_id', 'foreign-call')):
            bad = copy.deepcopy(audit)
            bad['binding'][side]['payload'][field] = replacement
            variants.append((side + '.' + field, bad))
        for label, bad in variants:
            with self.subTest(field=label):
                self.g.write(path, bad)
                with self.assertRaises(ValueError):
                    self.g.collect(0, False)
                self.assertEqual(bad, self.g.read(path))
                self.g.write(path, audit)
        self.assertEqual((value, audit), self.g.collect(0, False))

    def test_collect_refuses_native_parent_and_agent_lineage_mismatch(self):
        _, path = self.dispatch()
        original = path.read_bytes()
        for field, replacement in (('parent_thread_id', 'foreign-parent'),
                                   ('agent_path', '/root/foreign-agent')):
            with self.subTest(field=field):
                rows = [json.loads(line) for line in original.splitlines()]
                rows[0]['payload']['source']['subagent']['thread_spawn'][field] = replacement
                path.write_bytes(b''.join((json.dumps(row) + '\n').encode() for row in rows))
                with self.assertRaises(ValueError):
                    self.g.collect(0)
                self.assertFalse((self.g.D / 'grading/audits/0.json').exists())
                self.assertFalse((self.g.D / 'grading/answers/0.json').exists())
        path.write_bytes(original)
        self.g.collect(0)

    def test_aborted_native_turn_with_valid_final_is_refused_live_and_replay(self):
        _, path = self.dispatch()
        original = path.read_bytes()
        for terminal in ('interrupted', 'cancelled'):
            with self.subTest(terminal=terminal):
                rows = [json.loads(line) for line in original.splitlines()]
                rows[-1]['payload'].update(type='turn_aborted', reason=terminal)
                raw = b''.join((json.dumps(row) + '\n').encode() for row in rows)
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.g.collect(0)
                self.assertFalse((self.g.D / 'grading/audits/0.json').exists())
        path.write_bytes(original)
        _, audit = self.g.collect(0)
        rows = [json.loads(line) for line in original.splitlines()]
        rows[-1]['payload'].update(type='turn_aborted', reason='interrupted')
        raw = b''.join((json.dumps(row) + '\n').encode() for row in rows)
        digest = hashlib.sha256(raw).hexdigest()
        (self.g.D / 'grading/native' / (digest + '.jsonl')).write_bytes(raw)
        audit['nativeSha256'] = digest
        self.g.write(self.g.D / 'grading/audits/0.json', audit)
        with self.assertRaises(ValueError):
            self.g.collect(0, False)

    def test_retry_refuses_aborted_native_turn_even_with_invalid_answer(self):
        _, path = self.dispatch(value={})
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        rows[-1]['payload'].update(type='turn_aborted', reason='interrupted')
        path.write_bytes(b''.join((json.dumps(row) + '\n').encode() for row in rows))
        with self.assertRaises(ValueError):
            self.g.retry(0)
        self.assertEqual({}, self.g.read(self.g.D / 'grading/attempts.json'))

    def test_unapproved_grader_io_persists_violation_and_permanently_invalidates_study(self):
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        _, path = self.dispatch()
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        rows.insert(-2, self.audit_rows('cat /unapproved/private-source.py')[0])
        raw = b''.join((json.dumps(row) + '\n').encode() for row in rows)
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            self.g.collect(0)
        violation = self.g.D / 'grading/violations' / ('0-' + digest + '.json')
        self.assertTrue(violation.exists(), 'offending native proof must survive refusal')
        evidence = self.g.read(violation)
        self.assertEqual(digest, evidence['nativeSha256'])
        self.assertEqual(raw, (self.g.D / 'grading/native' / (digest + '.jsonl')).read_bytes())
        self.assertEqual('INVALID', self.g.read(self.g.D / 'STATE.json')['phase'])
        with self.assertRaises(ValueError):
            self.g.frozen()
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        with self.assertRaises(ValueError):
            self.g.frozen()
        with self.assertRaises(ValueError):
            self.g.retry(0)

    def test_direct_retry_with_aborted_unapproved_io_persists_violation(self):
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        _, path = self.dispatch()
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        rows[-1]['payload'].update(type='turn_aborted', reason='cancelled')
        rows.insert(-2, self.audit_rows('cat /unapproved/private-source.py')[0])
        raw = b''.join((json.dumps(row) + '\n').encode() for row in rows)
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            self.g.retry(0)
        violation = self.g.D / 'grading/violations' / ('0-' + digest + '.json')
        self.assertTrue(violation.exists(), 'offending native proof must survive refusal')
        evidence = self.g.read(violation)
        self.assertEqual(digest, evidence['nativeSha256'])
        self.assertEqual(raw, (self.g.D / 'grading/native' / (digest + '.jsonl')).read_bytes())
        self.assertEqual('INVALID', self.g.read(self.g.D / 'STATE.json')['phase'])
        with self.assertRaises(ValueError):
            self.g.frozen()
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        with self.assertRaises(ValueError):
            self.g.frozen()
        with self.assertRaises(ValueError):
            self.g.launch(0)

    def test_observed_illegal_io_invalidates_before_settlement_collect_and_retry(self):
        for method in ('collect', 'retry'):
            for shape in ('after-complete', 'pending', 'truncated', 'foreign-model'):
                with self.subTest(method=method, shape=shape):
                    # Each violation permanently invalidates its own synthetic study.
                    case = GradingTests('runTest')
                    case.setUp()
                    try:
                        case.g.write(case.g.D / 'STATE.json', {'phase': 'COLLECTED'})
                        _, path = case.dispatch(value={})
                        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
                        illegal = case.audit_rows('cat /unapproved/private-source.py')[0]
                        if shape == 'after-complete':
                            rows.append(illegal)
                        else:
                            rows.insert(-2, illegal)
                            if shape in ('pending', 'truncated'):
                                rows = rows[:-1]
                            if shape == 'foreign-model':
                                rows[1]['payload']['model'] = 'foreign-model'
                        raw = b''.join((json.dumps(row) + '\n').encode() for row in rows)
                        if shape == 'truncated':
                            raw += b'{"incomplete":'
                        path.write_bytes(raw)
                        with self.assertRaises(ValueError):
                            getattr(case.g, method)(0)
                        digest = hashlib.sha256(raw).hexdigest()
                        marker = case.g.D / 'grading/violations' / ('0-' + digest + '.json')
                        self.assertTrue(marker.exists(), 'observed illegal IO must survive unsettled lifecycle')
                        self.assertEqual(raw, (case.g.D / 'grading/native' / (digest + '.jsonl')).read_bytes())
                        self.assertEqual('INVALID', case.g.read(case.g.D / 'STATE.json')['phase'])
                        case.g.write(case.g.D / 'STATE.json', {'phase': 'COLLECTED'})
                        with self.assertRaises(ValueError):
                            case.g.frozen()
                    finally:
                        case.doCleanups()

    def test_missing_capsule_read_without_observed_io_does_not_invalidate(self):
        for method in ('collect', 'retry'):
            for complete in (False, True):
                with self.subTest(method=method, complete=complete):
                    case = GradingTests('runTest')
                    case.setUp()
                    try:
                        case.g.write(case.g.D / 'STATE.json', {'phase': 'COLLECTED'})
                        _, path = case.dispatch(value={})
                        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
                        rows = [row for row in rows if row.get('payload', {}).get('type') != 'custom_tool_call']
                        if not complete:
                            rows = rows[:-1]
                        path.write_bytes(b''.join((json.dumps(row) + '\n').encode() for row in rows))
                        with self.assertRaises(ValueError):
                            getattr(case.g, method)(0)
                        self.assertFalse(list((case.g.D / 'grading/violations').glob('*.json')))
                        self.assertEqual('COLLECTED', case.g.read(case.g.D / 'STATE.json')['phase'])
                        case.g.frozen()
                    finally:
                        case.doCleanups()

    def test_accepted_live_native_growth_retains_observed_unapproved_io(self):
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        _, path = self.dispatch()
        _, accepted = self.g.collect(0)
        original = path.read_bytes()
        illegal = self.audit_rows('cat /unapproved/post-acceptance-source.py')[0]
        raw = original + (json.dumps(illegal) + '\n').encode()
        path.write_bytes(raw)
        with self.assertRaises(ValueError):
            self.g.collect(0, True)
        digest = hashlib.sha256(raw).hexdigest()
        marker = self.g.D / 'grading/violations' / ('0-' + digest + '.json')
        self.assertTrue(marker.exists(), 'live growth must preserve observed IO before hash refusal')
        self.assertEqual(raw, (self.g.D / 'grading/native' / (digest + '.jsonl')).read_bytes())
        self.assertEqual(original, (self.g.D / 'grading/native' / (accepted['nativeSha256'] + '.jsonl')).read_bytes())
        self.assertEqual('INVALID', self.g.read(self.g.D / 'STATE.json')['phase'])
        self.g.write(self.g.D / 'STATE.json', {'phase': 'COLLECTED'})
        with self.assertRaises(ValueError):
            self.g.frozen()

    def test_ingestion_refuses_missing_extra_truncated_ids_and_non_boolean_values(self):
        good = self.answers()
        key = next(iter(good))
        candidates = [{}, dict(good, foreign=True), {key[:8]: False}, list(good)]
        candidates.extend(dict(good, **{key: value}) for value in (0, 1, 'false', None, []))
        for value in candidates:
            self.parents.clear()
            self.dispatch(value=value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'exact boolean'):
                self.g.collect(0)
            self.assertFalse((self.g.D / 'grading/audits/0.json').exists())
            self.assertFalse((self.g.D / 'grading/answers/0.json').exists())

    def test_native_duplicate_answer_keys_are_rejected_before_storage(self):
        key = next(iter(self.answers()))
        entries = [json.dumps(identifier) + ':false' for identifier in self.answers()]
        entries.append(json.dumps(key) + ':true')
        self.dispatch(final_text='{' + ','.join(entries) + '}')
        with self.assertRaises(ValueError):
            self.g.collect(0)
        self.assertFalse((self.g.D / 'grading/audits/0.json').exists())

    def test_stored_native_snapshot_bytes_are_immutable_even_for_equivalent_json(self):
        self.dispatch()
        _, audit = self.g.collect(0)
        snapshot = self.g.D / 'grading/native' / (audit['nativeSha256'] + '.jsonl')
        snapshot.write_bytes(b' ' + snapshot.read_bytes())
        with self.assertRaises(ValueError):
            self.g.collect(0, False)

    def test_accepted_answer_edit_or_live_native_growth_is_refused(self):
        _, native_path = self.dispatch()
        value, _ = self.g.collect(0)
        self.g.write(self.g.D / 'grading/answers/0.json', {key: not answer for key, answer in value.items()})
        with self.assertRaises(ValueError):
            self.g.collect(0, False)
        self.g.write(self.g.D / 'grading/answers/0.json', value)
        with native_path.open('ab') as stream:
            stream.write(b' ')
        with self.assertRaises(ValueError):
            self.g.collect(0)

    def test_combine_requires_unique_native_sessions_and_question_ids(self):
        original = self.g.collect
        answers = [self.answers(0), self.answers(1)]
        self.g.collect = lambda i, live=True: (answers[i], {'sessionId': 'reused-session'})
        with self.assertRaises(ValueError):
            self.g.combine()
        answers[1] = dict(answers[0])
        self.g.collect = lambda i, live=True: (answers[i], {'sessionId': 'session-' + str(i)})
        with self.assertRaises(ValueError):
            self.g.combine()
        self.g.collect = original

    def test_combine_reconstructs_exact_verdicts_and_refuses_operator_edit(self):
        for index in (0, 1):
            self.dispatch(index)
            self.g.collect(index)
        result = self.g.combine()
        self.assertEqual(4, result['questions'])
        self.assertEqual(2, result['nativeSessions'])
        self.assertEqual(result, self.g.combine(False))
        self.g.write(self.g.D / 'verdicts.json', {})
        with self.assertRaises(ValueError):
            self.g.combine(False)

    def test_invalid_settled_answer_retries_once_with_immutable_failure_proof(self):
        actor, path = self.dispatch(value={})
        with self.assertRaises(ValueError):
            self.g.collect(0)
        retry = self.g.retry(0)
        self.assertTrue(retry['task_name'].endswith('_r1'))
        self.g.frozen()
        proof = self.g.read(self.g.D / 'grading/rejected/0.json')
        snapshot = self.g.D / 'grading/native' / (proof['nativeSha256'] + '.jsonl')
        self.assertEqual(path.read_bytes(), snapshot.read_bytes())
        self.dispatch(value=self.answers(), session='fresh-retry-session')
        self.g.collect(0)
        self.assertEqual(path.read_bytes(), snapshot.read_bytes())
        with self.assertRaises(ValueError):
            self.g.retry(0)
        self.dispatch(1)
        self.g.collect(1)
        self.assertEqual(4, self.g.combine()['questions'])

    def test_valid_or_already_accepted_judge_cannot_be_retried(self):
        self.dispatch()
        before = (self.g.D / 'grading/freeze.json').read_bytes()
        with self.assertRaises(ValueError):
            self.g.retry(0)
        self.assertEqual(before, (self.g.D / 'grading/freeze.json').read_bytes())
        self.g.collect(0)
        with self.assertRaises(ValueError):
            self.g.retry(0)

    def test_retry_proof_tamper_and_reused_native_session_refuse(self):
        self.dispatch(value={}, session='rejected-native-session')
        self.g.retry(0)
        proof = self.g.read(self.g.D / 'grading/rejected/0.json')
        snapshot = self.g.D / 'grading/native' / (proof['nativeSha256'] + '.jsonl')
        raw = snapshot.read_bytes()
        snapshot.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            self.g.frozen()
        snapshot.write_bytes(raw)
        self.dispatch(value=self.answers(), session='rejected-native-session')
        with self.assertRaises(ValueError):
            self.g.collect(0)

    def test_attempt_ledger_allows_one_retry_and_refuses_other_types_or_counts(self):
        self.assertEqual('gv2_grade_0', self.g.launch(0)['task_name'])
        self.g.write(self.g.D / 'grading/attempts.json', {'0': 1})
        with self.assertRaises(ValueError):
            self.g.launch(0)
        for attempt in (-1, 2, '1', True):
            self.g.write(self.g.D / 'grading/attempts.json', {'0': attempt})
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                self.g.launch(0)

    def test_native_proof_refuses_hash_lineage_and_call_return_mismatches(self):
        self.dispatch()
        _, audit = self.g.collect(0)
        raw = (self.g.D / 'grading/native' / (audit['nativeSha256'] + '.jsonl')).read_bytes()
        self.result.native_proof(audit, raw, self.n, 'synthetic-parent', audit['agent'])
        variants = []
        for key, value in (('nativeSha256', '0' * 64), ('sessionId', 'foreign')):
            bad = copy.deepcopy(audit)
            bad[key] = value
            variants.append((bad, raw, 'synthetic-parent', audit['agent']))
        for key, value in (('call_id', 'foreign-call'), ('type', 'message')):
            bad = copy.deepcopy(audit)
            bad['binding']['return']['payload'][key] = value
            variants.append((bad, raw, 'synthetic-parent', audit['agent']))
        variants.extend([(audit, b' ' + raw, 'synthetic-parent', audit['agent']),
                         (audit, raw, 'foreign-parent', audit['agent']),
                         (audit, raw, 'synthetic-parent', '/root/foreign-agent')])
        for args in variants:
            with self.subTest(args=args[2:]), self.assertRaises(ValueError):
                self.result.native_proof(args[0], args[1], self.n, args[2], args[3])

    def test_capsules_consume_study_relative_base_inventory_coordinates(self):
        freeze = self.g.read(self.g.D / 'freeze.json')
        bases = {Path(item['context']['basePath']) for item in self.items}
        self.assertEqual({base.relative_to(self.g.D).as_posix() for base in bases},
                         set(freeze['baseInventories']))
        self.assertTrue(all(key.startswith('public/bases/') for key in freeze['baseInventories']))
        self.assertTrue(all(not key.startswith('.itd-memory/') for key in freeze['baseInventories']))
        capsule = self.g.batches()[0]
        self.assertEqual({item['context']['basePath'] for item in capsule['items']},
                         {source['basePath'] for source in capsule['sources']})

    def test_capsules_include_hash_bound_sources_only_for_realness(self):
        batches = self.g.batches()
        real, semantic = batches[0], batches[1]
        self.assertTrue(real['sources'])
        self.assertEqual([], semantic['sources'])
        for source in real['sources']:
            self.assertIn(source['basePath'], {item['context']['basePath'] for item in real['items']})
            for file in source['files']:
                self.assertEqual(hashlib.sha256(file['text'].encode('utf-8')).hexdigest(), file['sha256'])
                self.assertEqual((Path(source['basePath']) / file['path']).read_text(encoding='utf-8'), file['text'])
        self.assertEqual(4, sum(len(source['files']) for source in real['sources']))

    def test_tampered_public_base_refuses_capsule_generation(self):
        base = Path(self.items[0]['context']['basePath'])
        (base / 'src.py').write_text('tampered public code')
        with self.assertRaises(ValueError):
            self.g.batches()

    def test_undeclared_public_base_cannot_enter_capsule(self):
        queue = copy.deepcopy(self.items)
        queue[0]['context']['basePath'] = str(self.home / 'unapproved-base')
        self.g.write(self.g.D / 'queue.json', {'items': queue})
        with self.assertRaises(ValueError):
            self.g.batches()

    def test_exactly_one_assigned_capsule_read_is_required(self):
        for index in (0, 1):
            path = self.g.D / 'grading/batches' / (str(index) + '.json')
            batch = self.g.read(path)
            read = self.accepted_read(path)
            self.assertEqual([], self.g.audit(self.n, read, batch, path))
            self.assertTrue(self.g.audit(self.n, [], batch, path))
            self.assertTrue(self.g.audit(self.n, read + read, batch, path))
            self.assertTrue(self.g.audit(self.n, read + [{'type': 'response_item', 'payload':
                {'type': 'function_call', 'name': 'wait', 'arguments': '{}'}}], batch, path))
            self.assertTrue(self.g.audit(self.n, self.audit_rows('cat ' + str(path)), batch, path))

    def test_relative_dynamic_foreign_and_second_io_are_rejected(self):
        path = self.g.D / 'grading/batches/0.json'
        batch = self.g.read(path)
        for command in ('cat grading/batches/0.json', 'cat "$ASSIGNED"',
                        'python3 -c "print(open(\'src.py\').read())"',
                        'cat ' + batch['items'][0]['context']['basePath'] + '/src.py',
                        'cat ' + str(path.with_name('1.json'))):
            extra = self.audit_rows(command)
            with self.subTest(command=command):
                self.assertTrue(self.g.audit(self.n, extra, batch, path))
                self.assertTrue(self.g.audit(self.n, self.accepted_read(path) + extra, batch, path))

    def test_launch_pins_exact_read_capsule_hash_and_no_further_tools(self):
        path = self.g.D / 'grading/batches/0.json'
        message = self.g.launch(0)['message']
        self.assertIn(self.g.read_code(path), message)
        self.assertIn(self.g.sha(path), message)
        self.assertIn('exactly once', message.lower())
        self.assertIn('zero', message.lower())

    def test_copied_transport_keeps_original_assigned_path_and_hashes_local_batch(self):
        original_root = self.home
        copied_root = self.home.parent / (self.home.name + '-copy')
        moved_root = self.home.parent / (self.home.name + '-hidden')
        self.addCleanup(lambda: shutil.rmtree(copied_root, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(moved_root, ignore_errors=True))
        before = [p.read_bytes() for p in sorted((self.g.D / 'grading/batches').glob('*.json'))]
        shutil.copytree(original_root, copied_root)
        original_root.rename(moved_root)
        self.home = copied_root
        self.g.ROOT = copied_root
        self.g.D = copied_root / '.itd-memory/graph-v2-study'
        self.assertEqual([self.g.read(p) for p in sorted((self.g.D / 'grading/batches').glob('*.json'))], self.g.batches())
        self.g.frozen()
        self.assertEqual(before, [p.read_bytes() for p in sorted((self.g.D / 'grading/batches').glob('*.json'))])
        for index in (0, 1):
            local = self.g.D / 'grading/batches' / (str(index) + '.json')
            assigned = original_root / '.itd-memory/graph-v2-study/grading/batches' / (str(index) + '.json')
            self.assertFalse(assigned.exists())
            self.assertEqual(assigned, self.g.transport_path(local))
            message = self.g.launch(index)['message']
            self.assertIn(self.g.read_code(assigned), message)
            self.assertIn(self.g.sha(local), message)
            self.assertNotIn(str(local), message)
            self.dispatch(index)
            answers, evidence = self.g.collect(index)
            self.assertEqual(self.answers(index), answers)
            self.assertEqual(self.g.sha(local), evidence['batchSha256'])
            batch = self.g.read(local)
            self.assertTrue(self.g.audit(self.n, self.accepted_read(local), batch, assigned))
        self.assertEqual(4, self.g.combine()['questions'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
