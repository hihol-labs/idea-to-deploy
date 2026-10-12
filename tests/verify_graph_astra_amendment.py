#!/usr/bin/env python3
"""Synthetic regressions for the owner-authorized judge transport amendment."""
import ast
import copy
import hashlib
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(path):
    spec = importlib.util.spec_from_file_location('subject', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.amended = load(ROOT / 'scripts/graph_v2_astra.py')
        self.recovery = load(ROOT / 'scripts/graph_v2_astra_dispatch_recovery.py')

    def test_transformation_changes_only_registered_model_and_artifact_literals(self):
        source = (ROOT / 'scripts/graph_v2_grade.py').read_text()
        before = ast.parse(source)
        after = self.amended.JudgeOnly().visit(ast.parse(source))
        old_nodes, new_nodes = list(ast.walk(before)), list(ast.walk(after))
        self.assertEqual(len(old_nodes), len(new_nodes))
        model_changes = 0
        for old, new in zip(old_nodes, new_nodes):
            self.assertEqual(type(old), type(new))
            if isinstance(old, ast.Constant) and old.value != new.value:
                if old.value == 'gpt-6.1-sol':
                    self.assertEqual('gpt-6-astra', new.value)
                    model_changes += 1
                elif old.value == 'verdicts.json':
                    self.assertEqual('verdicts-astra.json', new.value)
                else:
                    self.assertTrue(old.value.startswith('grading/'))
                    self.assertEqual('grading-astra/' + old.value[8:], new.value)
                new.value = old.value
        self.assertEqual(2, model_changes)
        self.assertEqual(ast.dump(before), ast.dump(after))

    def test_actual_adapted_model_guard_accepts_only_astra_high(self):
        grader = types.ModuleType('synthetic_grader')
        grader.__file__ = str(ROOT / 'scripts/graph_v2_astra.py')
        source = (ROOT / 'scripts/graph_v2_grade.py').read_text()
        tree = ast.fix_missing_locations(self.amended.JudgeOnly().visit(ast.parse(source)))
        exec(compile(tree, str(ROOT / 'scripts/graph_v2_grade.py'), 'exec'), grader.__dict__)
        grader.ROOT = self.home
        grader.D = self.home / 'study'
        grader.D.mkdir()
        grader.write(grader.D / 'freeze.json', {'projectRoot': str(self.home)})
        native = load(ROOT / 'scripts/graph_v2_native.py')
        native.config = lambda: {'parentThreadId': 'parent'}
        path = grader.D / 'grading-astra/batches/0.json'
        actor = '/root/synthetic'
        def raw(model, effort):
            rows = [
                {'type': 'session_meta', 'payload': {'id': 'session', 'source': {'subagent': {
                    'thread_spawn': {'parent_thread_id': 'parent', 'agent_path': actor}}}}},
                {'type': 'turn_context', 'payload': {'model': model, 'effort': effort}},
                {'type': 'event_msg', 'payload': {'type': 'task_started'}},
                {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec', 'input': grader.read_code(path)}},
                {'type': 'response_item', 'timestamp': '2026-10-12T00:00:00Z', 'payload': {
                    'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
                    'content': [{'type': 'output_text', 'text': '{}'}]}},
                {'type': 'event_msg', 'payload': {'type': 'task_complete'}}]
            return ''.join(json.dumps(row) + '\n' for row in rows).encode()
        batch = {'kind': 'semantic', 'items': [{'id': 'question'}]}
        grader.rejected_rows(native, raw('gpt-6-astra', 'high'), batch, path, actor)
        for model, effort in [('gpt-6.1-sol', 'high'), ('gpt-5.6-terra', 'high'), ('gpt-6-astra', 'medium')]:
            with self.subTest(model=model, effort=effort), self.assertRaisesRegex(ValueError, 'model/effort mixed'):
                grader.rejected_rows(native, raw(model, effort), batch, path, actor)

    def test_unapproved_model_and_changed_sealed_inputs_are_refused(self):
        self.amended.D = self.home
        self.amended.AMENDMENT = self.home / 'amendment.json'
        fields = [('collection-verification.json', 'collectionSha256'), ('queue.json', 'queueSha256'),
                  ('grading/freeze.json', 'originalGradingFreezeSha256')]
        good = {'graderModel': 'gpt-6-astra', 'reasoningEffort': 'high'}
        for filename, field in fields:
            path = self.home / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'{}')
            good[field] = hashlib.sha256(b'{}').hexdigest()
        for field, value in [('graderModel', 'gpt-6.1-sol'), ('reasoningEffort', 'medium')] + [(f, '0' * 64) for _, f in fields]:
            self.amended.AMENDMENT.write_text(json.dumps(dict(good, **{field: value})))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'unapproved judge|amendment input changed'):
                self.amended.adapter()

    def test_dispatch_recovery_excludes_only_proven_pre_session_refusal(self):
        r = self.recovery
        args = {'task_name': r.TASK, 'fork_turns': 'none', 'model': 'gpt-6-astra', 'reasoning_effort': 'high', 'message': 'pinned'}
        native = types.SimpleNamespace(strict=json.loads, dispatch_args_match=lambda actual, expected: actual == expected)
        call = {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                'call_id': r.FAILED_CALL, 'arguments': json.dumps(args)}}
        reply = {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': r.FAILED_CALL, 'output': r.FAILURE}}
        success = {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent',
                   'call_id': 'successful-call', 'arguments': json.dumps(args)}}
        remaining, proof = r.filter_failed_spawn([call, reply, success], native, args)
        self.assertEqual([success], remaining)
        self.assertEqual({'call': call, 'return': reply}, proof)
        for output in [json.dumps({'task_name': '/root/' + r.TASK}), 'unknown failure']:
            bad = copy.deepcopy(reply)
            bad['payload']['output'] = output
            with self.assertRaises(ValueError): r.filter_failed_spawn([call, bad, success], native, args)
        for rows in [[reply, success], [call, reply, reply, success], [call, call, reply, success]]:
            with self.assertRaises(ValueError): r.filter_failed_spawn(rows, native, args)
        with self.assertRaises(ValueError): r.filter_failed_spawn([call, reply, success], native, dict(args, model='other'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
