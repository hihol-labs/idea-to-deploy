#!/usr/bin/env python3
"""Study-adapter safety regressions using only synthetic projects and fake native rows."""
import copy
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/graph_v2_study.py'
NATIVE_SCRIPT = ROOT / 'scripts/graph_v2_native.py'
HOOK = ROOT / 'hooks/graph-route.sh'
DISPATCH = ROOT / 'hooks/codex-dispatch.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeSnapshot(list):
    def __init__(self, raw):
        data = json.loads(raw)
        super().__init__(data['rows'])
        self.complete = data['complete']
        self.final = data['final']
        self.terminal = data.get('terminal', 'task_complete')


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-graph-study-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.api = load(SCRIPT, 'synthetic_study_adapter')
        self.api.NAMESPACE = 'gv2b'
        self.api.ROOT = self.home
        self.api.STUDY = self.home / 'study'
        self.api.RUNS = self.home / 'clones'
        self.api.RUNS.mkdir()
        self.addCleanup(self.unlock_clones)
        self.gt = load(ROOT / 'skills/graph/scripts/itd_graph.py', 'synthetic_gt')
        self.v2 = load(ROOT / 'skills/graph/scripts/itd_graph_v2.py', 'synthetic_v2')
        self.policy = load(ROOT / 'skills/graph/scripts/itd_graph_policy.py', 'synthetic_policy')
        self.policy.boot_id = lambda: 'synthetic-boot'
        self.parents, self.logs = [], {}
        self.native = types.SimpleNamespace(
            NativeSnapshot=NativeSnapshot, strict=json.loads,
            parent_rows=lambda: self.parents,
            native_rows=lambda agent: (self.logs[agent], None),
            audit=lambda rows, clone, assigned=None: {'invalid': False, 'voiding': False, 'ctxCalls': False},
            terminal_status=lambda rows: {'type': rows.terminal} if rows.complete else None,
            dispatch_args_match=lambda actual, expected: actual == expected,
            final_from=self.final_from)
        self.cfg = {'model': 'synthetic-model', 'reasoningEffort': 'low'}
        self.api.libraries = lambda: (self.cfg, self.native, self.gt, self.v2, self.policy)
        self.base = self.api.STUDY / 'public/bases/T1'
        self.base.mkdir(parents=True)
        (self.base / 'src.py').write_text('def parse(text):\n    return text\n')
        (self.base / '.gitignore').write_text('ignored-overlay.txt\n')
        env = dict(os.environ, GIT_AUTHOR_NAME='Synthetic Study', GIT_AUTHOR_EMAIL='study@example.invalid',
                   GIT_COMMITTER_NAME='Synthetic Study', GIT_COMMITTER_EMAIL='study@example.invalid')
        for args in (['init', '-q'], ['add', '.'], ['commit', '-q', '-m', 'synthetic base']):
            subprocess.run(['git', '-C', str(self.base), *args], env=env, capture_output=True, check=True)
        head = subprocess.check_output(['git', '-C', str(self.base), 'rev-parse', 'HEAD'], text=True).strip()
        self.task_data = {'id': 'T1', 'basePath': str(self.base), 'baseHead': head, 'module': 'src.py',
            'task': 'Inspect synthetic empty-input behavior', 'functions': ['parse'],
            'contracts': [{'id': 'empty-input', 'requirement': 'Empty input is rejected'}],
            'changedFiles': ['src.py'], 'sensitive': False, 'boundaries': []}
        self.label = 'T1-GK-K'
        self.pin = self.home / 'frozen-input.txt'
        self.pin.write_text('synthetic frozen input')
        self.api.write(self.api.STUDY / 'freeze.json', {
            'projectRoot': str(self.home), 'files': {str(self.pin): self.api.sha(self.pin)},
            'baseInventories': {'public/bases/T1': self.api.base_inventory(self.base)}})
        self.state = {'phase': 'FROZEN', 'active': None, 'queue': [self.label],
                      'completed': [], 'voided': [], 'voidedNative': [], 'bootId': 'synthetic-boot'}
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        self.api.write(self.api.STUDY / 'results.json', {'version': 2, 'runs': []})
        self.api.write(self.api.STUDY / 'public/catalog.json', {'tasks': [self.task_data]})

    def test_frozen_public_judge_base_detects_source_and_ignored_overlay_changes(self):
        base = self.api.STUDY / 'public/bases/T1'
        base.mkdir(parents=True, exist_ok=True)
        source = base / 'src.py'
        source.write_text('def parse(text): return text\n')
        freeze = self.api.read(self.api.STUDY / 'freeze.json')
        freeze['baseInventories'] = {'public/bases/T1': self.api.base_inventory(base)}
        self.api.write(self.api.STUDY / 'freeze.json', freeze)
        self.api.frozen(False)
        original = source.read_bytes()
        source.write_text('def parse(text): return None\n')
        with self.assertRaisesRegex(ValueError, 'public judge base'):
            self.api.frozen(False)
        source.write_bytes(original)
        (base / 'ignored-overlay.txt').write_text('untrusted overlay')
        with self.assertRaisesRegex(ValueError, 'public judge base'):
            self.api.frozen(False)

    def test_study_namespace_separates_clones_and_native_actor_identity(self):
        previous_clone = self.api.layout(self.label)[0]
        previous_actor = self.api.actor_name(self.label, 'check')
        self.api.NAMESPACE = 'gv2r2'
        self.assertNotEqual(previous_clone, self.api.layout(self.label)[0])
        self.assertNotEqual(previous_actor, self.api.actor_name(self.label, 'check'))
        self.assertTrue(self.api.actor_name(self.label, 'check').startswith('gv2r2_'))

    def test_context_refuses_unsafe_namespace_directory_and_clone_root(self):
        ctx = load(ROOT / 'scripts/graph_v2_context.py', 'synthetic_context')
        protocol = self.home / 'docs/measurements/graph-v2/PROTOCOL.json'
        protocol.parent.mkdir(parents=True)
        valid = {'namespace': 'gv2r2', 'studyDirectory': '.itd-memory/graph-v2-study-r2', 'runsRoot': str(self.home / 'runs')}
        for field, value in (('namespace', '../escape'), ('studyDirectory', '../escape'), ('runsRoot', 'relative/runs')):
            protocol.write_text(json.dumps(dict(valid, **{field: value})))
            with self.subTest(field=field), self.assertRaises(ValueError):
                ctx.context(self.home)
        protocol.write_text(json.dumps(valid))
        actual = ctx.context(self.home)
        self.assertEqual(self.home / valid['studyDirectory'], actual['study'])
        self.assertEqual('gv2r2_grade', actual['grader'])

    def unlock_clones(self):
        for clone in self.api.RUNS.iterdir():
            if clone.is_dir():
                clone.chmod(0o700)

    @staticmethod
    def final_from(rows):
        if rows.final == 'MALFORMED':
            raise ValueError('synthetic malformed JSON final')
        return json.dumps(rows.final), rows.final, None

    def seed_attempt(self, route='single'):
        clone, out = self.api.layout(self.label)
        shutil.copytree(self.base, clone)
        out.mkdir(parents=True)
        run_dir = clone / '.itd-memory/graph-runs/synthetic-run'
        if route == 'graph':
            graph = self.v2.build_graph('synthetic-run', str(clone), 'src.py', self.task_data['task'],
                                        self.task_data['contracts'], self.task_data['functions'])
            self.api.write(run_dir / 'graph.json', graph)
        self.api.write(out / 'attempt.json', {'label': self.label, 'task': self.task_data,
            'arm': 'K' if route == 'single' else 'G', 'pair': 'GK', 'route': route,
            'decision': {'route': route}, 'runDir': str(run_dir), 'clone': str(clone),
            't0': 1, 'bootId': 'synthetic-boot'})
        self.api.write(out / 'snapshot.json', self.gt.project_tree_state(clone))
        self.api.write(out / 'source-inventory.json', self.api.source_inventory(clone))
        self.state.update(active=self.label, phase='RUNNING')
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        return clone, out

    def reset_attempt(self):
        clone, out = self.api.layout(self.label)
        if clone.exists():
            clone.chmod(0o700)
            shutil.rmtree(clone)
        if out.exists():
            shutil.rmtree(out)
        self.parents.clear()
        self.logs.clear()
        self.state.update(active=None, phase='FROZEN')
        self.api.write(self.api.STUDY / 'STATE.json', self.state)

    def clear_synthetic_invalidation(self):
        """Start an independent subcase; production has no reset operation."""
        for relative in ('invalidations', 'grading/violations'):
            shutil.rmtree(self.api.STUDY / relative, ignore_errors=True)

    def hunter_output(self):
        return {'findings': [], 'coverage': [{'function': 'parse', 'contractIds': ['empty-input'],
                'status': 'checked', 'evidence': 'Synthetic source read'}]}

    def dispatch(self, node='check', final=None, complete=True):
        launch = self.api.task(self.label, node)
        actor = '/root/' + launch['task_name']
        call_id = 'synthetic-call-' + node
        self.parents.extend([
            {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                'call_id': call_id, 'arguments': json.dumps(launch)}},
            {'type': 'response_item', 'payload': {'type': 'function_call_output',
                'call_id': call_id, 'output': json.dumps({'task_name': actor})}}])
        log = self.home / ('native-' + node + '.jsonl')
        log.write_text(json.dumps({'complete': complete, 'final': self.hunter_output() if final is None else final,
            'rows': [{'type': 'session_meta', 'payload': {'id': 'session-' + node}},
                     {'type': 'turn_context', 'payload': {'model': 'synthetic-model', 'effort': 'low'}},
                     {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
                      'input': self.api.CTX.read_code(self.api.layout(self.label)[0] / '.itd-memory/tasks' / (node + '.json'))}}]}))
        self.logs[actor] = log
        return actor

    def test_prepare_rejects_wrong_order_active_work_and_reused_directories(self):
        with self.assertRaises(ValueError):
            self.api.prepare('T1-GK-G')
        self.state['active'] = 'T2-KG-K'
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        with self.assertRaises(ValueError):
            self.api.prepare(self.label)
        self.state['active'] = None
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        clone, out = self.api.layout(self.label)
        for folder in (clone, out):
            folder.mkdir(parents=True)
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                self.api.prepare(self.label)
            folder.rmdir()

    def test_prepare_creates_one_fresh_attempt_and_literal_task(self):
        launches = self.api.prepare(self.label)
        clone, out = self.api.layout(self.label)
        self.assertEqual(1, len(launches))
        self.assertEqual(self.label, self.api.read(self.api.STUDY / 'STATE.json')['active'])
        self.assertEqual((out / 'tasks/check.json').read_bytes(),
                         (clone / '.itd-memory/tasks/check.json').read_bytes())
        self.assertIn(self.api.sha(out / 'tasks/check.json'), launches[0]['message'])
        protocol = self.api.read(self.api.PROTO)
        self.assertEqual(protocol['model'], launches[0]['model'])
        self.assertEqual(protocol['reasoningEffort'], launches[0]['reasoning_effort'])

    def test_freeze_edit_and_incomplete_verification_refuse(self):
        with self.assertRaises(ValueError):
            self.api.verify()
        self.pin.write_text('changed frozen input')
        with self.assertRaises(ValueError):
            self.api.frozen()

    def test_missing_or_changed_global_boot_permanently_invalidates_study(self):
        for boot in (None, 'foreign-boot'):
            self.clear_synthetic_invalidation()
            state = dict(self.state, bootId=boot)
            self.api.write(self.api.STUDY / 'STATE.json', state)
            with self.subTest(boot=boot), self.assertRaisesRegex(ValueError, 'permanently INVALID'):
                self.api.frozen()
            self.assertEqual('INVALID', self.api.read(self.api.STUDY / 'STATE.json')['phase'])

    def test_changed_voided_native_evidence_permanently_invalidates_study(self):
        evidence = self.home / 'synthetic-voided-native.jsonl'
        evidence.write_text('settled synthetic evidence')
        self.state['voidedNative'] = [{'agents': [{'nativePath': str(evidence),
                                                  'nativeSha256': self.api.sha(evidence)}]}]
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        evidence.write_text('edited settled synthetic evidence')
        with self.assertRaisesRegex(ValueError, 'permanently INVALID'):
            self.api.frozen()
        self.assertEqual('INVALID', self.api.read(self.api.STUDY / 'STATE.json')['phase'])

    def test_task_generation_is_byte_stable_and_collect_detects_assigned_task_edit(self):
        clone, out = self.seed_attempt()
        actor = self.dispatch()
        before = (out / 'tasks/check.json').read_bytes()
        self.api.task(self.label, 'check')
        self.assertEqual(before, (out / 'tasks/check.json').read_bytes())
        assigned = clone / '.itd-memory/tasks/check.json'
        assigned.write_text(assigned.read_text() + ' ')
        result = self.api.collect(self.label, 'check', actor)
        self.assertEqual('MODEL_FAILURE', result['status'])
        self.assertIn('metadata changed', self.api.read(out / 'audits/check.json')['workFailure'])

    def test_task_payload_is_pure_and_matches_the_written_task_recipe(self):
        clone, out = self.seed_attempt()
        payload = self.api.task_payload(self.label, 'check', self.api.read(out / 'attempt.json'))
        self.assertFalse((out / 'tasks').exists())
        self.assertFalse((clone / '.itd-memory/tasks').exists())
        self.api.task(self.label, 'check')
        self.assertEqual(payload, self.api.read(out / 'tasks/check.json'))

    def test_collection_seal_binds_durable_files_and_replay_uses_offline_verification(self):
        calls = []
        expected = {'status': 'FRESH_STUDY_COLLECTED', 'arms': 32, 'nativeSessions': 32,
                    'model': 'synthetic-model', 'workFailures': 0}
        def verifier(live=True):
            calls.append(live)
            return dict(expected)
        self.api.verify = verifier
        self.assertEqual(expected, self.api.seal())
        self.assertEqual(expected, self.api.replay())
        self.assertEqual([True, False], calls)
        for name in ('results.json', 'STATE.json', 'freeze.json'):
            path = self.api.STUDY / name
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.api.replay()
            path.write_bytes(original)
        expected['workFailures'] = 1
        with self.assertRaises(ValueError):
            self.api.replay()

    def test_single_control_cannot_claim_checked_coverage_without_all_contracts(self):
        self.seed_attempt('single')
        value = self.hunter_output()
        value['coverage'][0]['contractIds'] = []
        actor = self.dispatch(final=value)
        result = self.api.collect(self.label, 'check', actor)
        self.assertEqual('MODEL_FAILURE', result['status'])
        _, out = self.api.layout(self.label)
        self.assertIn('every contract', self.api.read(out / 'audits/check.json')['workFailure'])

    def test_bad_final_ids_and_schema_are_recorded_as_model_failure(self):
        bad_id = self.hunter_output()
        finding = {key: 'synthetic evidence' for key in self.v2.FINDING['required']}
        finding.update(findingId='foreign-1', file='src.py', line=1, function='parse',
                       contractId='empty-input', severity='high', origin='introduced')
        bad_id['findings'] = [finding]
        for value in ('MALFORMED', {'findings': [], 'coverage': []},
                      {'findings': 'invalid', 'coverage': []}, bad_id):
            self.reset_attempt()
            _, out = self.seed_attempt()
            actor = self.dispatch(final=value)
            self.assertEqual('MODEL_FAILURE', self.api.collect(self.label, 'check', actor)['status'])
            self.assertTrue((out / 'audits/check.json').is_file())
            self.assertFalse((out / 'nodes/check.json').exists())

    def test_collect_catches_tracked_and_ignored_source_overlays(self):
        for relative in ('ignored-overlay.txt', 'src.py'):
            self.reset_attempt()
            clone, out = self.seed_attempt()
            actor = self.dispatch()
            (clone / relative).write_text('undeclared source edit')
            self.assertEqual('MODEL_FAILURE', self.api.collect(self.label, 'check', actor)['status'])
            self.assertIn('snapshot/overlay', self.api.read(out / 'audits/check.json')['workFailure'])

    def test_collect_is_idempotent_and_keeps_first_elapsed_endpoint(self):
        _, out = self.seed_attempt()
        actor = self.dispatch()
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'check', actor)['status'])
        files = [out / 'attempt.json', out / 'audits/check.json', out / 'nodes/check.json']
        before = [path.read_bytes() for path in files]
        repeated = self.api.collect(self.label, 'check', actor)
        self.assertEqual('COLLECTED', repeated['status'])
        self.assertTrue(repeated['idempotent'])
        self.assertEqual(before, [path.read_bytes() for path in files])

    def test_null_token_usage_event_does_not_reject_valid_native_answer(self):
        self.seed_attempt()
        actor = self.dispatch()
        payload = json.loads(self.logs[actor].read_text())
        payload['rows'].append({'type': 'event_msg', 'payload': {
            'type': 'token_count', 'info': None}})
        self.logs[actor].write_text(json.dumps(payload))
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'check', actor)['status'])
        _, out = self.api.layout(self.label)
        self.assertIsNone(self.api.read(out / 'audits/check.json')['usage'])

    def test_collect_after_accepted_native_log_change_permanently_invalidates(self):
        self.seed_attempt()
        actor = self.dispatch()
        self.api.collect(self.label, 'check', actor)
        with self.logs[actor].open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'permanently INVALID'):
            self.api.collect(self.label, 'check', actor)
        self.assertEqual('INVALID', self.api.read(self.api.STUDY / 'STATE.json')['phase'])

    def test_native_growth_retains_snapshot_and_marker_after_state_rewrite(self):
        clone, out = self.seed_attempt()
        actor = self.dispatch()
        self.api.collect(self.label, 'check', actor)
        accepted = self.api.read(out / 'audits/check.json')['nativeSha256']
        payload = json.loads(self.logs[actor].read_text())
        payload['rows'].append({'type': 'response_item', 'payload': {
            'type': 'custom_tool_call', 'name': 'exec', 'input': 'dynamic foreign read'}})
        self.logs[actor].write_text(json.dumps(payload))
        offending = self.api.sha(self.logs[actor])
        with self.assertRaisesRegex(ValueError, 'permanently INVALID'):
            self.api.collect(self.label, 'check', actor)
        markers = list((self.api.STUDY / 'invalidations').glob('*.json'))
        self.assertEqual(1, len(markers))
        self.assertTrue((self.api.STUDY / 'native' / (accepted + '.jsonl')).is_file())
        self.assertTrue((self.api.STUDY / 'native' / (offending + '.jsonl')).is_file())
        self.api.write(self.api.STUDY / 'STATE.json', dict(self.state, phase='FROZEN'))
        with self.assertRaisesRegex(ValueError, 'retained isolation/integrity'):
            self.api.frozen()
        self.assertEqual('INVALID', self.api.read(self.api.STUDY / 'STATE.json')['phase'])

    def test_finish_detects_source_overlay_added_after_collection(self):
        clone, _ = self.seed_attempt()
        actor = self.dispatch()
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'check', actor)['status'])
        (clone / 'ignored-overlay.txt').write_text('changed after collection')
        try:
            result = self.api.finish(self.label)
        except ValueError:
            return  # Refusal is conservative; a clean success would misreport the arm.
        finally:
            clone.chmod(0o700)  # Finish seals the disposable clone, including on work failure.
        self.assertEqual('MODEL_FAILURE', result['status'])

    def expired_graph_attempt(self):
        self.label = 'T1-GK-G'
        self.state['queue'] = [self.label]
        self.api.write(self.api.STUDY / 'STATE.json', self.state)
        self.task_data.update(sensitive=True, boundaries=[
            {'id': 'parser', 'paths': ['src.py']}, {'id': 'caller', 'paths': ['src.py']}])
        self.api.write(self.api.STUDY / 'public/catalog.json', {'tasks': [self.task_data]})
        self.api.prepare(self.label)
        clone, out = self.api.layout(self.label)
        for node in ('contracts', 'integration'):
            actor = self.dispatch(node)
            self.assertEqual('COLLECTED', self.api.collect(self.label, node, actor)['status'])
        actor = self.dispatch('checker', final={'assessments': []})
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'checker', actor)['status'])
        meta = self.api.read(out / 'attempt.json')
        run_dir = Path(meta['runDir'])
        approval = self.api.read(run_dir / 'approval.json')
        approval['policy']['startedNs'] = 0
        self.api.write(run_dir / 'approval.json', approval)
        return clone, out, run_dir

    def test_explicit_study_deadline_precedes_record_as_defense_in_depth(self):
        clone, out, run_dir = self.expired_graph_attempt()
        def forbidden_record(args):
            self.fail('cmd_record called before rejecting expired execution budget')
        self.gt.cmd_record = forbidden_record
        result = self.api.finish(self.label)
        clone.chmod(0o700)
        self.assertEqual('MODEL_FAILURE', result['status'])
        self.assertFalse((run_dir / 'receipt.json').exists())
        self.assertFalse((out / 'graph-run').exists())
        self.assertTrue((out / 'receipt.json').is_file())
        record = self.api.read(self.api.STUDY / 'results.json')['runs'][0]
        self.assertIn('budget', record['workFailure'])
        self.assertEqual([], record['findings'])
        self.assertEqual(3, len(record['agents']))

    def test_real_graph_record_rejects_expired_policy_without_receipt(self):
        clone, out, run_dir = self.expired_graph_attempt()
        approval = self.api.read(run_dir / 'approval.json')
        approval['policy']['bootId'] = self.gt.v2_module('itd_graph_policy').boot_id()
        self.api.write(run_dir / 'approval.json', approval)
        graph = self.api.read(run_dir / 'graph.json')
        outputs = {node: self.api.read(out / 'nodes' / (node + '.json'))
                   for node in ('contracts', 'integration', 'checker')}
        result_path = run_dir / 'result.json'
        self.api.write(result_path, {'graphDigest': self.gt.graph_digest(graph), 'nodes': outputs})
        with self.assertRaisesRegex(self.gt.Refused, 'budget'):
            self.gt.cmd_record(types.SimpleNamespace(run_dir=str(run_dir),
                result=str(result_path), runtime='serial', at=None))
        self.assertFalse((run_dir / 'receipt.json').exists())
        self.assertFalse((run_dir / 'nodes').exists())

    def test_task_capsules_embed_only_tracked_source_with_content_hashes(self):
        clone, out = self.seed_attempt()
        (clone / 'ignored-overlay.txt').write_text('untrusted ignored content')
        (clone / 'untracked.txt').write_text('untrusted untracked content')
        self.api.write(clone / '.itd-memory/private.json', {'secret': 'metadata'})
        payload = self.api.task_payload(self.label, 'check', self.api.read(out / 'attempt.json'))
        sources = payload['sources']
        self.assertEqual({'.gitignore', 'src.py'}, {entry['path'] for entry in sources})
        for entry in sources:
            self.assertEqual((clone / entry['path']).read_text(), entry['text'])
            self.assertEqual(hashlib.sha256(entry['text'].encode()).hexdigest(), entry['sha256'])

    def test_graph_and_single_capsules_expose_identical_pinned_source(self):
        _, out = self.seed_attempt('single')
        single = self.api.task_payload(self.label, 'check', self.api.read(out / 'attempt.json'))
        self.reset_attempt()
        clone, out = self.seed_attempt('graph')
        graph = self.api.read(Path(self.api.read(out / 'attempt.json')['runDir']) / 'graph.json')
        contracts = self.api.task_payload(self.label, 'contracts', self.api.read(out / 'attempt.json'), graph)
        self.assertEqual(single['sources'], contracts['sources'])
        clone.chmod(0)
        repeated = self.api.task_payload(self.label, 'contracts', self.api.read(out / 'attempt.json'), graph)
        self.assertEqual(contracts, repeated)
        clone.chmod(0o700)

    def test_finish_and_void_settle_all_children_after_malformed_first_final(self):
        self.seed_attempt('graph')
        self.dispatch('contracts', final='MALFORMED')
        pending = self.dispatch('integration', complete=False)
        for action in (lambda: self.api.finish(self.label),
                       lambda: self.api.void('T1-GK', 'infrastructure: synthetic interruption')):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'not settled'):
                action()
            out = self.api.layout(self.label)[1]
            self.assertTrue((out / 'observations/integration.json').is_file())
            self.assertEqual(self.label, self.api.read(self.api.STUDY / 'STATE.json')['active'])
            self.assertEqual([], self.api.read(self.api.STUDY / 'results.json')['runs'])
        self.assertTrue(self.logs[pending].exists())

    def test_valid_final_before_abort_is_failed_not_scored(self):
        clone, out = self.seed_attempt()
        value = self.hunter_output()
        finding = {key: 'synthetic evidence' for key in self.v2.FINDING['required']}
        finding.update(findingId='check-1', file='src.py', line=1, function='parse',
                       contractId='empty-input', severity='high', origin='introduced')
        value['findings'] = [finding]
        actor = self.dispatch(final=value)
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'check', actor)['status'])
        self.reset_attempt()
        clone, out = self.seed_attempt()
        actor = self.dispatch(final=value)
        native = json.loads(self.logs[actor].read_text())
        native['terminal'] = 'turn_aborted'
        self.logs[actor].write_text(json.dumps(native))
        self.assertEqual('MODEL_FAILURE', self.api.collect(self.label, 'check', actor)['status'])
        self.assertFalse((out / 'nodes/check.json').exists())
        finished = self.api.finish(self.label)
        clone.chmod(0o700)
        self.assertEqual('MODEL_FAILURE', finished['status'])
        record = self.api.read(self.api.STUDY / 'results.json')['runs'][0]
        self.assertEqual([], record['findings'])
        self.assertTrue(record['workFailure'])
        self.assertFalse((Path(self.api.read(out / 'attempt.json')['runDir']) / 'receipt.json').exists())

    def test_aborted_graph_checker_never_produces_graph_receipt(self):
        clone, out = self.seed_attempt('graph')
        for node in ('contracts', 'integration'):
            actor = self.dispatch(node)
            self.assertEqual('COLLECTED', self.api.collect(self.label, node, actor)['status'])
        actor = self.dispatch('checker', final={'assessments': []})
        native = json.loads(self.logs[actor].read_text())
        native['terminal'] = 'turn_aborted'
        self.logs[actor].write_text(json.dumps(native))
        self.assertEqual('MODEL_FAILURE', self.api.collect(self.label, 'checker', actor)['status'])
        self.assertEqual('MODEL_FAILURE', self.api.finish(self.label)['status'])
        clone.chmod(0o700)
        run_dir = Path(self.api.read(out / 'attempt.json')['runDir'])
        self.assertFalse((run_dir / 'receipt.json').exists())
        self.assertFalse((out / 'graph-run').exists())
        self.assertEqual([], self.api.read(self.api.STUDY / 'results.json')['runs'][0]['findings'])

    def test_aborted_valid_final_remains_settled_for_typed_infrastructure_void(self):
        self.seed_attempt()
        actor = self.dispatch()
        native = json.loads(self.logs[actor].read_text())
        native['terminal'] = 'turn_aborted'
        self.logs[actor].write_text(json.dumps(native))
        result = self.api.void('T1-GK', 'infrastructure: synthetic cancellation')
        self.assertEqual('VOIDED', result['status'])
        self.assertEqual(['T1-GK-G-r1', 'T1-GK-K-r1'], result['next'])
        state = self.api.read(self.api.STUDY / 'STATE.json')
        self.assertEqual(1, len(state['voidedNative'][0]['agents']))
        self.assertEqual([], self.api.read(self.api.STUDY / 'results.json')['runs'])

    def test_completed_model_failure_cannot_be_voided_as_infrastructure(self):
        self.seed_attempt()
        self.dispatch(final='MALFORMED')
        with self.assertRaisesRegex(ValueError, 'cannot be discarded'):
            self.api.void('T1-GK', 'infrastructure: synthetic excuse')
        self.assertEqual([], self.api.read(self.api.STUDY / 'STATE.json')['voided'])

    def test_recorded_model_failure_cannot_be_removed_by_infrastructure_void(self):
        record = {'task': 'T1', 'pair': 'GK', 'workFailure': 'invalid checker model output'}
        self.api.write(self.api.STUDY / 'results.json', {'version': 2, 'runs': [record]})
        with self.assertRaisesRegex(ValueError, 'cannot be discarded'):
            self.api.void('T1-GK', 'infrastructure: synthetic excuse')
        self.assertEqual([record], self.api.read(self.api.STUDY / 'results.json')['runs'])
        self.assertEqual([], self.api.read(self.api.STUDY / 'STATE.json')['voided'])

    def test_attempt_model_failure_cannot_be_removed_by_infrastructure_void(self):
        _, out = self.seed_attempt()
        meta = self.api.read(out / 'attempt.json')
        meta['workFailure'] = 'semantic graph validation failed'
        self.api.write(out / 'attempt.json', meta)
        with self.assertRaisesRegex(ValueError, 'cannot be discarded'):
            self.api.void('T1-GK', 'infrastructure: synthetic excuse')
        self.assertEqual([], self.api.read(self.api.STUDY / 'STATE.json')['voided'])

    def test_void_validates_all_settled_graph_decisions_before_discarding(self):
        self.seed_attempt('graph')
        for node in ('contracts', 'integration'):
            actor = self.dispatch(node)
            self.assertEqual('COLLECTED', self.api.collect(self.label, node, actor)['status'])
        checker = self.dispatch('checker', final={'assessments': [{'findingId': 'contracts-foreign',
            'contract': 'satisfied', 'reachability': 'blocked', 'reason': 'synthetic refutation',
            'evidence': 'synthetic caller evidence'}]})
        self.assertEqual('COLLECTED', self.api.collect(self.label, 'checker', checker)['status'])
        with self.assertRaises(ValueError):
            self.api.void('T1-GK', 'infrastructure: synthetic excuse')
        self.assertEqual([], self.api.read(self.api.STUDY / 'STATE.json')['voided'])

    def test_finish_refuses_clock_regression_and_boot_change(self):
        _, out = self.seed_attempt()
        actor = self.dispatch()
        self.api.collect(self.label, 'check', actor)
        original = self.api.read(out / 'attempt.json')
        for update in ({'bootId': 'other-boot'}, {'t0': original['t1']}):
            self.clear_synthetic_invalidation()
            self.api.write(self.api.STUDY / 'STATE.json', self.state)
            self.api.write(out / 'attempt.json', dict(original, **update))
            with self.subTest(update=update), self.assertRaisesRegex(ValueError, 'clock/boot'):
                self.api.finish(self.label)
            self.assertEqual('INVALID', self.api.read(self.api.STUDY / 'STATE.json')['phase'])
        self.assertEqual([], self.api.read(self.api.STUDY / 'results.json')['runs'])

    def test_collect_refuses_native_bytes_that_grow_during_final_extraction(self):
        self.seed_attempt()
        actor = self.dispatch()
        original = self.native.final_from
        def changing_final(rows):
            result = original(rows)
            with self.logs[actor].open('a') as stream:
                stream.write(' ')
            return result
        self.native.final_from = changing_final
        with self.assertRaisesRegex(ValueError, 'native evidence changed'):
            self.api.collect(self.label, 'check', actor)

    def test_real_codex_hook_transport_is_quiet_without_policy(self):
        result = self.hook({})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('', result.stdout)

    def hook(self, payload):
        env = dict(os.environ, PLUGIN_ROOT=str(ROOT))
        return subprocess.run([sys.executable, str(DISPATCH), '--script', str(HOOK)],
            cwd=self.base, input=json.dumps(payload), env=env, text=True, capture_output=True)

    def test_real_codex_hook_transport_emits_authorized_native_context(self):
        (self.base / 'caller.py').write_text('from src import parse\n')
        subprocess.run(['git', '-C', str(self.base), 'add', 'caller.py'], check=True, capture_output=True)
        expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
        policy = {'version': 1, 'enabled': True, 'project': str(self.base),
            'template': 'contract-boundary-check', 'templateSha256': self.policy.fingerprint(),
            'allowedModules': ['src.py'], 'sensitivePaths': ['*.py'],
            'boundaries': [{'id': 'parser', 'paths': ['src.py']}, {'id': 'caller', 'paths': ['caller.py']}],
            'maxRuns': 1, 'maxAgentNodes': 3, 'maxSeconds': 90, 'expiresAt': expiry}
        authorization = {'version': 1, 'policySha256': self.policy.policy_digest(policy),
            'by': 'synthetic-owner', 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        request = {'version': 1, 'unitId': 'synthetic-review', 'module': 'src.py',
            'task': self.task_data['task'], 'functions': self.task_data['functions'],
            'contracts': self.task_data['contracts'], 'changedFiles': ['src.py', 'caller.py']}
        self.api.write(self.base / '.itd/GRAPH_POLICY.json', policy)
        self.api.write(self.base / '.itd/GRAPH_AUTHORIZATION.json', authorization)
        self.api.write(self.base / '.itd-memory/graph-request.json', request)
        result = self.hook({'cwd': str(self.base), 'session_id': 'synthetic-hook',
                            'hook_event_name': 'UserPromptSubmit'})
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual('UserPromptSubmit', output['hookEventName'])
        self.assertIn('emit-serial', output['additionalContext'])
        self.assertIn('Owner policy selected', output['additionalContext'])


class NativeAuditTests(unittest.TestCase):
    def setUp(self):
        self.native = load(NATIVE_SCRIPT, 'synthetic_native_auditor')
        self.clone = Path('/home/hihol/itd-graph-v2-runs/gv2-T1-GK-G')

    def audit_path(self, path):
        return self.audit_command('cat ' + path)

    def audit_command(self, text, assigned='check'):
        command = 'await tools.exec_command(' + json.dumps({'cmd': text,
                                                           'workdir': str(self.clone)}) + ')'
        rows = [{'type': 'response_item', 'payload': {'type': 'function_call',
                 'name': 'exec', 'arguments': command}}]
        return self.native.audit(rows, self.clone, assigned)

    def test_audit_requires_exactly_one_literal_task_capsule_read(self):
        ctx = load(ROOT / 'scripts/graph_v2_context.py', 'capsule_context')
        row = {'type': 'response_item', 'payload': {'type': 'custom_tool_call',
               'name': 'exec', 'input': ctx.read_code(self.clone / '.itd-memory/tasks/check.json')}}
        self.assertEqual([], self.native.audit([row], self.clone, 'check')['voiding'])
        for rows in ([], [row, row], [row, {'type': 'response_item', 'payload':
                     {'type': 'function_call', 'name': 'wait', 'arguments': '{}'}}]):
            with self.subTest(rows=rows):
                self.assertTrue(self.native.audit(rows, self.clone, 'check')['voiding'])
        for command in ('cat .itd-memory/tasks/check.json', 'cat "$TASK"',
                        'python3 -I -B -c "print(open(\'src.py\').read())"'):
            with self.subTest(command=command):
                self.assertTrue(self.audit_command(command)['voiding'])

    def test_unapproved_io_invalidates_unknown_exposure_but_missing_read_is_work_failure(self):
        self.assertFalse(self.native.audit([], self.clone, 'check')['invalid'])
        self.assertTrue(self.audit_command('python3 -I -B -c "print(open(chr(47)+chr(116)).read())"')['invalid'])

    def test_audit_flags_sealed_study_bases_siblings_and_original_sources(self):
        cases = [('/tmp/graph-v2-study/sealed/manifest.json', 'sealed'),
                 ('/tmp/graph-v2-study/public/catalog.json', 'study'),
                 ('/home/hihol/itd-graph-v2-runs/bases/T1/src.py', 'bases'),
                 ('/home/hihol/itd-graph-v2-runs/gv2-T2-GK-G/src.py', 'otherClone'),
                 ('/home/hihol/projects/itd-graph-v2/src.py', 'otherOutside')]
        for path, category in cases:
            with self.subTest(path=path):
                audit = self.audit_path(path)
                self.assertIn(category, audit['voiding'])
                self.assertTrue(audit['invalid'])

    def test_audit_resolves_unc_and_parent_relative_escape_paths(self):
        for path in (r'\\wsl.localhost\Ubuntu-24.04\home\hihol\itd-graph-v2-runs\bases\T1\src.py',
                     '../bases/T1/src.py'):
            with self.subTest(path=path):
                self.assertIn('bases', self.audit_path(path)['voiding'])

    def test_audit_allows_exact_assigned_capsule_read_but_rejects_other_metadata(self):
        ctx = load(ROOT / 'scripts/graph_v2_context.py', 'capsule_context')
        row = {'type': 'response_item', 'payload': {'type': 'custom_tool_call',
               'name': 'exec', 'input': ctx.read_code(self.clone / '.itd-memory/tasks/check.json')}}
        audit = self.native.audit([row], self.clone, 'check')
        self.assertFalse(audit['invalid'])
        self.assertEqual([], audit['voiding'])
        self.assertTrue(self.audit_path(str(self.clone / 'src.py'))['voiding'])
        self.assertIn('otherMetadata', self.audit_path(str(self.clone / '.itd-memory/graph-request.json'))['voiding'])
        self.assertIn('otherMetadata', self.audit_path(str(self.clone / '.itd-memory/tasks/checker.json'))['voiding'])

    def test_audit_flags_relative_sealed_and_manifest_reads(self):
        for path in ('sealed/secret.json', './sealed/secret.json', 'manifest.json'):
            with self.subTest(path=path):
                audit = self.audit_path(path)
                self.assertTrue(audit['invalid'])
                self.assertIn('sealed', audit['voiding'])

    def test_audit_blocks_network_package_test_claude_and_git_mutation_commands(self):
        for command in ('curl https://example.invalid', 'wget https://example.invalid', 'claude --version',
                        'npm install', 'pnpm test', 'yarn start', 'pip install example', 'pytest tests',
                        'python3 -m unittest', 'python3 tests/check.py', 'git add src.py', 'git commit -m example'):
            with self.subTest(command=command):
                self.assertIn('forbiddenCommand', self.audit_command(command)['voiding'])
        self.assertTrue(self.audit_command("python3 -I -B -c 'print(1)'")['voiding'])

    def test_audit_preserves_escaped_python_path_quote_boundaries(self):
        cases = [('.itd-memory/tasks/checker.json', None),
                 ('.itd-memory/tasks/contracts.json', 'otherMetadata'),
                 ('./sealed/manifest.json', 'sealed')]
        for path, category in cases:
            python = 'python3 -I -B -c \'import pathlib; print(pathlib.Path("' + path + '").read_text())\''
            code = 'await tools.exec_command(' + json.dumps({'cmd': python,
                                                             'workdir': str(self.clone)}) + ')'
            self.assertIn('\\"' + path + '\\"', code)
            for transport in (code, json.dumps(code)[1:-1]):
                rows = [{'type': 'response_item', 'payload': {'type': 'custom_tool_call',
                         'name': 'exec', 'input': transport}}]
                with self.subTest(path=path, transport=transport):
                    audit = self.native.audit(rows, self.clone, 'checker')
                    if category is None:
                        self.assertTrue(audit['voiding'])
                        self.assertTrue(audit['invalid'])
                    else:
                        self.assertIn(category, audit['voiding'])
                        self.assertTrue(audit['invalid'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
