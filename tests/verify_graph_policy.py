#!/usr/bin/env python3
"""Owner-bound graph routing policy regressions; all files are disposable synthetic inputs."""
import copy
import datetime
import errno
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/graph/scripts/itd_graph_policy.py'
if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location('itd_graph_policy', SCRIPT)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
else:
    api = None


def utc_after(days):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).isoformat()


class GraphPolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api, 'graph routing policy implementation is absent')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        for relative in ('src/parser.py', 'src/gateway.py', 'docs/context.txt', 'tests/example.txt'):
            path = self.project / relative
            path.parent.mkdir(exist_ok=True)
            path.write_text('synthetic source for ' + relative, encoding='utf-8')
        self.policy = {'version': 1, 'enabled': True, 'project': str(self.project),
            'template': 'contract-boundary-check', 'templateSha256': api.fingerprint(),
            'allowedModules': ['src/*.py'], 'sensitivePaths': ['src/*.py'],
            'boundaries': [{'id': 'parser', 'paths': ['src/parser.py']},
                           {'id': 'gateway', 'paths': ['src/gateway.py']}],
            'maxRuns': 2, 'maxAgentNodes': 3, 'maxSeconds': 90, 'expiresAt': utc_after(2)}
        self.authorization = self.authorize(self.policy)
        self.request = {'version': 1, 'unitId': 'review-limits', 'module': 'src/parser.py',
            'task': 'Audit boundary interactions', 'functions': ['parse'],
            'contracts': [{'id': 'reject-empty', 'requirement': 'Empty input raises ValueError'}],
            'changedFiles': ['src/parser.py', 'src/gateway.py']}

    def authorize(self, policy):
        return {'version': 1, 'policySha256': api.policy_digest(policy),
                'by': 'project-owner', 'at': utc_after(-1)}

    def decide(self, **kwargs):
        return api.decide(str(self.project), kwargs.get('request', self.request),
                          kwargs.get('policy', self.policy),
                          kwargs.get('authorization', self.authorization), kwargs.get('used', 0))

    def reject(self, **kwargs):
        with self.assertRaises(ValueError):
            self.decide(**kwargs)

    def test_owner_bound_sensitive_cross_boundary_change_routes_to_graph(self):
        self.assertEqual('graph', self.decide()['route'])

    def test_absent_and_disabled_policy_stay_single(self):
        self.assertEqual('single', self.decide(policy=None, authorization=None)['route'])
        self.assertEqual('single', self.decide(policy=dict(self.policy, enabled=False), authorization=None)['route'])

    def test_authorization_is_required_and_bound_to_canonical_policy_content(self):
        self.assertEqual('single', self.decide(authorization=None)['route'])
        for authorization in (dict(self.authorization, policySha256='0' * 64),
                              dict(self.authorization, by=''), dict(self.authorization, at='yesterday')):
            with self.subTest(authorization=authorization):
                self.reject(authorization=authorization)
        changed = dict(self.policy, maxSeconds=91)
        self.reject(policy=changed)

    def test_policy_digest_is_canonical_sha256(self):
        canonical = json.dumps(self.policy, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), api.policy_digest(self.policy))
        self.assertEqual(api.policy_digest(self.policy), api.policy_digest(dict(reversed(list(self.policy.items())))))
        self.assertRegex(api.fingerprint(), r'^[0-9a-f]{64}$')

    def test_unallowed_module_uses_single_even_for_cross_boundary_change(self):
        self.request['module'] = 'docs/context.txt'
        self.assertEqual('single', self.decide()['route'])

    def test_one_boundary_and_nonsensitive_change_do_not_trigger_graph(self):
        for paths in (['src/parser.py'], ['docs/context.txt', 'tests/example.txt']):
            request = dict(self.request, changedFiles=paths)
            with self.subTest(paths=paths):
                self.assertEqual('single', self.decide(request=request)['route'])

    def test_two_files_in_same_boundary_do_not_count_as_two_boundaries(self):
        policy = copy.deepcopy(self.policy)
        policy['boundaries'] = [{'id': 'core', 'paths': ['src/*.py']}]
        self.assertEqual('single', self.decide(policy=policy, authorization=self.authorize(policy))['route'])

    def test_overlapping_path_matches_two_declared_distinct_boundaries(self):
        policy = copy.deepcopy(self.policy)
        policy['boundaries'][1]['paths'] = ['src/parser.py']
        request = dict(self.request, changedFiles=['src/parser.py'])
        self.assertEqual('graph', self.decide(policy=policy, authorization=self.authorize(policy), request=request)['route'])

    def test_budget_limit_is_exact_and_does_not_mutate_inputs(self):
        before = copy.deepcopy((self.policy, self.authorization, self.request))
        self.assertEqual('graph', self.decide(used=1)['route'])
        result = self.decide(used=2)
        self.assertEqual('single', result['route'])
        self.assertEqual('budget-exhausted', result['reason'])
        self.assertEqual(before, (self.policy, self.authorization, self.request))

    def test_policy_template_and_project_binding_cannot_be_changed(self):
        for updates in ({'templateSha256': '0' * 64}, {'template': 'module-neighbour-check'},
                        {'project': str(self.project.parent)}, {'project': 'relative-project'}):
            bad = dict(self.policy, **updates)
            with self.subTest(updates=updates):
                self.reject(policy=bad, authorization=self.authorize(bad))

    def test_expired_enabled_policy_refuses(self):
        bad = dict(self.policy, expiresAt=utc_after(-1))
        self.reject(policy=bad, authorization=self.authorize(bad))

    def test_malformed_limits_and_timestamps_refuse(self):
        for updates in ({'maxRuns': 0}, {'maxRuns': True}, {'maxRuns': 1.5},
                        {'maxAgentNodes': 4}, {'maxAgentNodes': True}, {'maxSeconds': 0},
                        {'maxSeconds': '90'}, {'expiresAt': 'tomorrow'},
                        {'expiresAt': '2030-01-01T00:00:00'}):
            bad = dict(self.policy, **updates)
            with self.subTest(updates=updates):
                self.reject(policy=bad, authorization=self.authorize(bad))

    def test_unknown_policy_fields_and_duplicate_boundary_ids_refuse(self):
        bad = dict(self.policy, bypass=True)
        self.reject(policy=bad, authorization=self.authorize(bad))
        bad = copy.deepcopy(self.policy)
        bad['boundaries'][1]['id'] = bad['boundaries'][0]['id']
        self.reject(policy=bad, authorization=self.authorize(bad))

    def test_unsafe_missing_or_absolute_request_paths_refuse(self):
        for path in ('../outside.py', 'src/../parser.py', '/etc/passwd', 'src\\parser.py', 'src/missing.py'):
            for field in ('module', 'changedFiles'):
                bad = copy.deepcopy(self.request)
                bad[field] = path if field == 'module' else [path]
                with self.subTest(path=path, field=field):
                    self.reject(request=bad)

    def test_symlink_paths_cannot_cross_project_containment(self):
        outside = Path(self.temp.name) / 'outside.py'
        outside.write_text('outside project', encoding='utf-8')
        try:
            (self.project / 'src/link.py').symlink_to(outside)
        except NotImplementedError as exc:
            self.skipTest('Symlink creation unsupported on this host: ' + str(exc))
        except OSError as exc:
            if exc.errno not in (errno.EPERM, errno.EACCES, errno.ENOTSUP, errno.ENOSYS) and getattr(exc, 'winerror', None) != 1314:
                raise
            self.skipTest('Symlink creation unsupported on this host: ' + str(exc))
        self.reject(request=dict(self.request, module='src/link.py'))
        self.reject(request=dict(self.request, changedFiles=['src/link.py']))

    def test_malformed_request_identity_and_inventory_refuse(self):
        for updates in ({'unitId': '../review'}, {'task': ''}, {'functions': []}, {'contracts': []},
                        {'version': 2}, {'functions': ['parse', 'parse']}):
            with self.subTest(updates=updates):
                self.reject(request=dict(self.request, **updates))

    def unresolved(self):
        return {'findingId': 'contracts-empty', 'reason': 'Caller evidence conflicts with function contract',
                'counterexample': 'parse empty text with direct function call',
                'evidence': [{'path': path, 'sha256': hashlib.sha256((self.project / path).read_bytes()).hexdigest()}
                             for path in ('docs/context.txt', 'tests/example.txt')]}

    def test_unresolved_with_two_content_bound_sources_can_trigger_graph(self):
        request = dict(self.request, changedFiles=['docs/context.txt'], unresolved=self.unresolved())
        self.assertEqual('graph', self.decide(request=request)['route'])

    def test_unresolved_evidence_needs_two_distinct_sources_and_correct_hashes(self):
        unresolved = self.unresolved()
        variants = []
        for evidence in (unresolved['evidence'][:1], [unresolved['evidence'][0]] * 2,
                         [dict(unresolved['evidence'][0], sha256='0' * 64), unresolved['evidence'][1]]):
            variants.append(dict(unresolved, evidence=evidence))
        variants += [dict(unresolved, reason=''), dict(unresolved, counterexample='')]
        for candidate in variants:
            with self.subTest(candidate=candidate):
                self.reject(request=dict(self.request, changedFiles=['docs/context.txt'], unresolved=candidate))

    def test_unresolved_evidence_hash_is_rechecked_after_source_change(self):
        request = dict(self.request, changedFiles=['docs/context.txt'], unresolved=self.unresolved())
        (self.project / 'docs/context.txt').write_text('changed after evidence capture', encoding='utf-8')
        self.reject(request=request)

    def seed_prepare_project(self, ignore_authorization=False):
        metadata = self.project / '.itd'
        metadata.mkdir()
        memory = self.project / '.itd-memory'
        memory.mkdir()
        for path, data in ((metadata / 'GRAPH_POLICY.json', self.policy),
                           (metadata / 'GRAPH_AUTHORIZATION.json', self.authorization),
                           (memory / 'graph-request.json', self.request)):
            path.write_text(json.dumps(data), encoding='utf-8')
        if ignore_authorization:
            (self.project / '.gitignore').write_text('.itd/GRAPH_AUTHORIZATION.json\n')
        env = dict(os.environ, GIT_AUTHOR_NAME='Graph Test', GIT_AUTHOR_EMAIL='graph@example.invalid',
                   GIT_COMMITTER_NAME='Graph Test', GIT_COMMITTER_EMAIL='graph@example.invalid')
        for args in (['init', '-q'], ['add', '.'], ['commit', '-q', '-m', 'synthetic inputs']):
            subprocess.run(['git', '-C', str(self.project), *args], env=env,
                           capture_output=True, check=True)

    def prepare(self, session='test-session'):
        return api.prepare(str(self.project), '.itd-memory/graph-request.json', session)

    def test_prepare_is_idempotent_and_binds_exact_owner_policy_request(self):
        self.seed_prepare_project()
        first = self.prepare()
        second = self.prepare()
        self.assertEqual('graph', first['route'])
        self.assertFalse(first['reused'])
        self.assertTrue(second['reused'])
        self.assertEqual(first['runDir'], second['runDir'])
        run_dir = Path(first['runDir'])
        graph = json.loads((run_dir / 'graph.json').read_text())
        approval = json.loads((run_dir / 'approval.json').read_text())
        self.assertEqual('project-owner', approval['by'])
        self.assertEqual(api.policy_digest(self.policy), approval['policy']['policySha256'])
        self.assertEqual(api.policy_digest(self.request), approval['policy']['requestSha256'])
        api.validate_bound_approval(run_dir, graph, approval)
        ledger = json.loads((self.project / '.itd-memory/graph-policy-ledger.json').read_text())
        self.assertEqual(1, len(ledger['entries']))
        self.assertFalse((self.project / '.itd-memory/graph-policy.lock').exists())

    def test_expired_policy_refuses_existing_and_recorded_run_reuse(self):
        for recorded in (False, True):
            if recorded:
                run_dir = self.recorded_reuse()
            else:
                run_dir, _ = self.prepared_reuse()
            ledger = self.project / '.itd-memory/graph-policy-ledger.json'
            before = ledger.read_bytes()
            class FutureClock(datetime.datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.datetime.now(tz) + datetime.timedelta(days=3)
            with self.subTest(recorded=recorded), mock.patch.object(api, 'datetime', FutureClock):
                with self.assertRaisesRegex(ValueError, 'expired graph policy'):
                    self.prepare()
            self.assertEqual(before, ledger.read_bytes())
            shutil.rmtree(self.project / '.itd-memory')
            shutil.rmtree(self.project / '.itd')
            shutil.rmtree(self.project / '.git')

    def test_prepare_budget_is_owner_bound_across_sessions_and_reuse_is_free(self):
        self.policy['maxRuns'] = 1
        self.authorization = self.authorize(self.policy)
        self.seed_prepare_project()
        original = self.prepare()
        self.assertTrue(self.prepare()['reused'])
        self.request['task'] = 'Audit a second independently requested change'
        (self.project / '.itd-memory/graph-request.json').write_text(json.dumps(self.request))
        self.assertEqual('budget-exhausted', self.prepare()['reason'])
        next_session = self.prepare('another-session')
        self.assertEqual('single', next_session['route'])
        self.assertEqual('budget-exhausted', next_session['reason'])
        ledger = json.loads((self.project / '.itd-memory/graph-policy-ledger.json').read_text())
        self.assertEqual(1, len(ledger['entries']))
        self.assertEqual(original['runDir'], str(self.project / ledger['entries'][0]['runDir']))

    def test_explicit_authorization_renewal_gets_new_run_identity(self):
        self.policy['maxRuns'] = 1
        self.authorization = self.authorize(self.policy)
        self.seed_prepare_project(ignore_authorization=True)
        first_tree = api.module('itd_graph').project_tree_state(self.project)
        first = self.prepare()
        renewed = dict(self.authorization, at=utc_after(-0.5))
        (self.project / '.itd/GRAPH_AUTHORIZATION.json').write_text(json.dumps(renewed))
        self.assertEqual(first_tree, api.module('itd_graph').project_tree_state(self.project))
        second = self.prepare()
        self.assertEqual('graph', second['route'])
        self.assertFalse(second['reused'])
        self.assertNotEqual(first['runDir'], second['runDir'])
        self.assertTrue(self.prepare()['reused'])

    def test_legacy_usage_ledger_refuses_instead_of_resetting_budget(self):
        _, ledger_path = self.prepared_reuse()
        ledger = json.loads(ledger_path.read_text())
        ledger['version'] = 1
        ledger_path.write_text(json.dumps(ledger))
        with self.assertRaises(ValueError):
            self.prepare('another-session')

    def test_foreign_budget_hashes_refuse_instead_of_restoring_allowance(self):
        self.policy['maxRuns'] = 1
        self.authorization = self.authorize(self.policy)
        _, ledger_path = self.prepared_reuse()
        ledger = json.loads(ledger_path.read_text())
        for field in ('policySha256', 'authorizationSha256'):
            bad = copy.deepcopy(ledger)
            bad['entries'][0][field] = '0' * 64
            ledger_path.write_text(json.dumps(bad))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepare('another-session-' + field)

    def test_prepare_refuses_untracked_source_and_never_creates_run(self):
        self.seed_prepare_project()
        (self.project / 'src/new.py').write_text('untracked code')
        self.request['changedFiles'].append('src/new.py')
        (self.project / '.itd-memory/graph-request.json').write_text(json.dumps(self.request))
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.project / '.itd-memory/graph-runs').exists())

    def test_prepare_owner_binding_detects_metadata_and_graph_tampering(self):
        self.seed_prepare_project()
        prepared = self.prepare()
        run_dir = Path(prepared['runDir'])
        graph = json.loads((run_dir / 'graph.json').read_text())
        approval = json.loads((run_dir / 'approval.json').read_text())
        for changed in ('task', 'owner'):
            bad_graph, bad_approval = copy.deepcopy(graph), copy.deepcopy(approval)
            if changed == 'task':
                bad_graph['task'] = 'Unapproved task'
            else:
                bad_approval['by'] = 'another-owner'
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                api.validate_bound_approval(run_dir, bad_graph, bad_approval)
        self.request['task'] = 'Changed after approval'
        (self.project / '.itd-memory/graph-request.json').write_text(json.dumps(self.request))
        with self.assertRaises(ValueError):
            api.validate_bound_approval(run_dir, graph, approval)

    def test_execution_deadline_and_boot_identity_are_enforced(self):
        self.seed_prepare_project()
        prepared = self.prepare()
        approval = json.loads((Path(prepared['runDir']) / 'approval.json').read_text())
        api.check_deadline(approval)
        for updates in ({'startedNs': 0}, {'bootId': 'foreign-boot'}, {'startedNs': True}):
            bad = copy.deepcopy(approval)
            bad['policy'].update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                api.check_deadline(bad)

    def test_cli_authorize_requires_exact_digest_and_records_owner(self):
        self.seed_prepare_project()
        auth_path = self.project / '.itd/GRAPH_AUTHORIZATION.json'
        auth_path.unlink()
        def cli(digest):
            return subprocess.run([sys.executable, str(SCRIPT), 'authorize', '--project',
                                   str(self.project), '--digest', digest, '--by', 'explicit-owner'],
                                  text=True, capture_output=True)
        self.assertNotEqual(0, cli('0' * 64).returncode)
        self.assertFalse(auth_path.exists())
        good = cli(api.policy_digest(self.policy))
        self.assertEqual(0, good.returncode, good.stderr)
        saved = json.loads(auth_path.read_text())
        self.assertEqual('explicit-owner', saved['by'])
        self.assertEqual(api.policy_digest(self.policy), saved['policySha256'])

    def run_hook(self):
        return subprocess.run([sys.executable, str(SCRIPT), 'hook'],
            input=json.dumps({'cwd': str(self.project), 'session_id': 'hook-session'}),
            text=True, capture_output=True)

    def test_hook_prepares_authorized_run_and_emits_executable_context(self):
        self.seed_prepare_project()
        (self.project / '.itd-memory/STATE.json').write_text(json.dumps(
            {'currentUnit': {'id': self.request['unitId'], 'status': 'in_progress'}}))
        result = self.run_hook()
        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)['hookSpecificOutput']
        self.assertEqual('UserPromptSubmit', context['hookEventName'])
        ledger = json.loads((self.project / '.itd-memory/graph-policy-ledger.json').read_text())
        self.assertEqual(1, len(ledger['entries']))
        run_dir = self.project / ledger['entries'][0]['runDir']
        self.assertIn(str(run_dir), context['additionalContext'])
        self.assertIn('emit-serial', context['additionalContext'])
        self.assertTrue((run_dir / 'approval.json').is_file())
        repeated = self.run_hook()
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        ledger = json.loads((self.project / '.itd-memory/graph-policy-ledger.json').read_text())
        self.assertEqual(1, len(ledger['entries']))

    def test_hook_stale_verified_or_foreign_unit_is_quiet_without_run(self):
        self.seed_prepare_project()
        for unit in ({'id': self.request['unitId'], 'status': 'verified'},
                     {'id': 'another-unit', 'status': 'in_progress'}):
            (self.project / '.itd-memory/STATE.json').write_text(json.dumps({'currentUnit': unit}))
            result = self.run_hook()
            with self.subTest(unit=unit):
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('', result.stdout)
                self.assertFalse((self.project / '.itd-memory/graph-runs').exists())
                self.assertFalse((self.project / '.itd-memory/graph-policy-ledger.json').exists())

    def prepared_reuse(self):
        self.seed_prepare_project()
        result = self.prepare()
        return Path(result['runDir']), self.project / '.itd-memory/graph-policy-ledger.json'

    def test_reuse_refuses_unsafe_or_foreign_ledger_run_directory(self):
        run_dir, ledger_path = self.prepared_reuse()
        ledger = json.loads(ledger_path.read_text())
        foreign = Path(self.temp.name) / 'foreign/.itd-memory/graph-runs/foreign-run'
        same_project = self.project / '.itd-memory/graph-runs/foreign-run'
        for target in (foreign, same_project):
            shutil.copytree(run_dir, target)
            approval_path = target / 'approval.json'
            approval = json.loads(approval_path.read_text())
            del approval['policy']  # Otherwise valid manual approval must not bypass owner-policy reuse.
            approval_path.write_text(json.dumps(approval))
        for relative in (str(foreign), '../foreign/.itd-memory/graph-runs/foreign-run',
                         '.itd-memory/graph-runs/foreign-run'):
            bad = copy.deepcopy(ledger)
            bad['entries'][0]['runDir'] = relative
            ledger_path.write_text(json.dumps(bad))
            with self.subTest(runDir=relative), self.assertRaises(ValueError):
                self.prepare()

    def test_reuse_refuses_ledger_digest_that_does_not_bind_saved_graph(self):
        _, ledger_path = self.prepared_reuse()
        ledger = json.loads(ledger_path.read_text())
        ledger['entries'][0]['graphDigest'] = '0' * 64
        ledger_path.write_text(json.dumps(ledger))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_reuse_refuses_manual_valid_approval_without_policy_provenance(self):
        run_dir, _ = self.prepared_reuse()
        approval_path = run_dir / 'approval.json'
        approval = json.loads(approval_path.read_text())
        del approval['policy']
        approval_path.write_text(json.dumps(approval))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_reuse_refuses_approval_bound_to_another_host_session(self):
        run_dir, _ = self.prepared_reuse()
        approval_path = run_dir / 'approval.json'
        approval = json.loads(approval_path.read_text())
        approval['policy']['session'] = 'foreign-host-session'
        approval_path.write_text(json.dumps(approval))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_reuse_refuses_approval_bound_to_another_project_snapshot(self):
        run_dir, _ = self.prepared_reuse()
        approval_path = run_dir / 'approval.json'
        approval = json.loads(approval_path.read_text())
        approval['projectTree']['head'] = '0' * 40
        approval_path.write_text(json.dumps(approval))
        with self.assertRaises(ValueError):
            self.prepare()

    def recorded_reuse(self):
        run_dir, _ = self.prepared_reuse()
        graph = json.loads((run_dir / 'graph.json').read_text())
        coverage = [{'function': 'parse', 'contractIds': ['reject-empty'], 'status': 'checked',
                     'evidence': 'Synthetic complete function inspection'}]
        outputs = {'contracts': {'findings': [], 'coverage': coverage},
                   'integration': {'findings': [], 'coverage': coverage},
                   'checker': {'assessments': []}}
        result_path = self.project / '.itd-memory/record-result.json'
        result_path.write_text(json.dumps({'graphDigest': api.policy_digest(graph), 'nodes': outputs}))
        recorded = subprocess.run([sys.executable, str(SCRIPT.with_name('itd_graph.py')), 'record',
            str(run_dir), '--result', str(result_path), '--runtime', 'serial'], capture_output=True, text=True)
        self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
        self.assertEqual('recorded', self.prepare()['route'])
        return run_dir

    def test_reuse_refuses_empty_or_tampered_receipt_instead_of_recorded(self):
        run_dir = self.recorded_reuse()
        receipt_path = run_dir / 'receipt.json'
        original = json.loads(receipt_path.read_text())
        for receipt in ({}, dict(original, graphDigest='0' * 64), dict(original, nodes={})):
            receipt_path.write_text(json.dumps(receipt))
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                self.prepare()

    def test_reuse_refuses_tampered_or_missing_recorded_node(self):
        run_dir = self.recorded_reuse()
        node_path = run_dir / 'nodes/contracts.md'
        node_path.write_text('tampered node output')
        with self.assertRaises(ValueError):
            self.prepare()
        node_path.unlink()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_reuse_refuses_tampered_or_missing_derived_synthesis(self):
        run_dir = self.recorded_reuse()
        synthesis_path = run_dir / 'synthesis.json'
        synthesis_path.write_text('{}')
        with self.assertRaises(ValueError):
            self.prepare()
        synthesis_path.unlink()
        with self.assertRaises(ValueError):
            self.prepare()


if __name__ == '__main__':
    unittest.main(verbosity=2)
