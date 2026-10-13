#!/usr/bin/env python3
"""Behavioral regressions for the contract-first three-agent graph (synthetic inputs only)."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/graph/scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    path = SCRIPTS / (name + '.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = load('itd_graph_v2')
legacy = load('itd_graph')
CONTRACTS = [
    {'id': 'reject-empty', 'requirement': 'parse rejects empty text'},
    {'id': 'preserve-limit', 'requirement': 'apply preserves the explicit limit'},
]
FUNCTIONS = ['parse', 'apply']
TASK = 'Audit empty input and the limit propagation path.'


def finding(identifier='contracts-empty', **updates):
    value = {'findingId': identifier, 'file': 'src/limits.py', 'line': 17,
             'function': 'parse', 'contractId': 'reject-empty',
             'precondition': 'text is empty', 'input': 'empty text',
             'expected': 'ValueError', 'actual': 'empty object',
             'claim': 'Empty text passes parse', 'evidence': 'return {} at line 17',
             'class': 'boundary', 'severity': 'high', 'origin': 'pre-existing'}
    value.update(updates)
    return value


def coverage():
    return [{'function': name, 'contractIds': [contract['id'] for contract in CONTRACTS],
             'status': 'checked', 'evidence': 'Read implementation and caller'}
            for i, name in enumerate(FUNCTIONS)]


def assessment(identifier='contracts-empty', contract='violated', reachability='reachable'):
    return {'findingId': identifier, 'contract': contract, 'reachability': reachability,
            'reason': 'The function returns before validating input',
            'evidence': 'src/limits.py:17 and caller line 41'}


def outputs():
    return {'contracts': {'findings': [finding()], 'coverage': coverage()},
            'integration': {'findings': [], 'coverage': coverage()},
            'checker': {'assessments': [assessment()]}}


class GraphV2Tests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api, 'contract-first implementation is absent')
        self.graph = api.build_graph('review-limits', '/synthetic/project',
                                     'src/limits.py', TASK, CONTRACTS, FUNCTIONS)
        self.outputs = outputs()

    def reject(self, value):
        with self.assertRaises(ValueError):
            api.validate_outputs(self.graph, value)

    def test_graph_has_exact_three_agents_and_legacy_validator_accepts_it(self):
        self.assertEqual({'contracts', 'integration', 'checker', 'human'},
                         {node['id'] for node in self.graph['nodes']})
        self.assertEqual(3, sum(node['kind'] == 'agent' for node in self.graph['nodes']))
        self.assertEqual([], legacy.validate_graph(self.graph))

    def test_every_agent_prompt_keeps_task_contracts_and_function_inventory(self):
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        for node in self.graph['nodes']:
            if node['kind'] == 'agent':
                with self.subTest(node=node['id']):
                    self.assertIn(TASK, node['prompt'])
                    self.assertIn(canonical(CONTRACTS), node['prompt'])
                    self.assertIn(canonical(FUNCTIONS), node['prompt'])

    def test_valid_complete_hunter_outputs_are_accepted(self):
        api.validate_outputs(self.graph, self.outputs)

    def test_each_hunter_must_cover_every_function(self):
        for node in ('contracts', 'integration'):
            bad = copy.deepcopy(self.outputs)
            bad[node]['coverage'].pop()
            with self.subTest(node=node):
                self.reject(bad)

    def test_duplicate_and_unknown_coverage_functions_are_rejected(self):
        for entry in (coverage()[0], dict(coverage()[0], function='foreign')):
            bad = copy.deepcopy(self.outputs)
            bad['contracts']['coverage'].append(entry)
            with self.subTest(entry=entry):
                self.reject(bad)

    def test_not_applicable_still_requires_nonempty_evidence_and_known_contracts(self):
        self.outputs['integration']['coverage'][0]['status'] = 'not-applicable'
        api.validate_outputs(self.graph, self.outputs)
        for updates in ({'evidence': ''}, {'contractIds': ['foreign']}, {'status': 'skipped'}):
            bad = copy.deepcopy(self.outputs)
            bad['integration']['coverage'][0].update(updates)
            with self.subTest(updates=updates):
                self.reject(bad)

    def test_every_function_accounts_for_each_contract_exactly_once(self):
        for node in ('contracts', 'integration'):
            for status in ('checked', 'not-applicable'):
                for function_index in range(len(FUNCTIONS)):
                    for contract_ids in ([], ['reject-empty'], ['preserve-limit'],
                                         ['reject-empty', 'preserve-limit', 'reject-empty']):
                        bad = copy.deepcopy(self.outputs)
                        bad[node]['coverage'][function_index].update(
                            status=status, contractIds=contract_ids)
                        with self.subTest(node=node, status=status,
                                          function=FUNCTIONS[function_index], contractIds=contract_ids):
                            self.reject(bad)

    def test_finding_ids_are_namespaced_by_hunter(self):
        for identifier in ('empty', 'integration-empty'):
            bad = copy.deepcopy(self.outputs)
            bad['contracts']['findings'][0]['findingId'] = identifier
            bad['checker']['assessments'][0]['findingId'] = identifier
            with self.subTest(identifier=identifier):
                self.reject(bad)

    def test_duplicate_finding_ids_are_rejected(self):
        self.outputs['contracts']['findings'].append(finding())
        self.reject(self.outputs)

    def test_findings_must_reference_declared_function_and_contract(self):
        for updates in ({'function': 'foreign'}, {'contractId': 'foreign'}):
            bad = copy.deepcopy(self.outputs)
            bad['contracts']['findings'][0].update(updates)
            with self.subTest(updates=updates):
                self.reject(bad)

    def test_finding_schema_requires_all_contract_evidence_fields(self):
        for key in finding():
            bad = copy.deepcopy(self.outputs)
            del bad['contracts']['findings'][0][key]
            with self.subTest(key=key):
                self.reject(bad)

    def test_finding_locations_and_enum_values_are_validated(self):
        for updates in ({'line': True}, {'line': 0}, {'file': '../outside.py'},
                        {'severity': 'critical'}, {'origin': 'invented'}):
            bad = copy.deepcopy(self.outputs)
            bad['contracts']['findings'][0].update(updates)
            with self.subTest(updates=updates):
                self.reject(bad)

    def test_checker_cannot_omit_repeat_or_invent_a_decision(self):
        for assessments in ([], [assessment(), assessment()],
                            [assessment('contracts-foreign')]):
            bad = copy.deepcopy(self.outputs)
            bad['checker']['assessments'] = assessments
            with self.subTest(assessments=assessments):
                self.reject(bad)

    def test_checker_requires_independent_contract_and_reachability_axes(self):
        for updates in ({'contract': 'refuted'}, {'reachability': 'confirmed'}, {'reason': ''}, {'evidence': ''}):
            bad = copy.deepcopy(self.outputs)
            bad['checker']['assessments'][0].update(updates)
            with self.subTest(updates=updates):
                self.reject(bad)

    def test_contract_violation_is_retained_even_when_current_caller_blocks_it(self):
        self.outputs['checker']['assessments'][0]['reachability'] = 'blocked'
        result = api.synthesize(self.graph, self.outputs)
        self.assertEqual(1, len(result['findings']))
        self.assertEqual('confirmed', result['findings'][0]['status'])
        self.assertEqual('blocked', result['findings'][0]['reachability'])
        self.assertEqual(['contracts-empty'], result['findings'][0]['sourceIds'])
        self.assertEqual([], result['dropped'])

    def test_unknown_contract_is_retained_as_unverifiable(self):
        self.outputs['checker']['assessments'][0]['contract'] = 'unknown'
        result = api.synthesize(self.graph, self.outputs)
        self.assertEqual(['unverifiable'], [item['status'] for item in result['findings']])

    def test_satisfied_contract_is_dropped(self):
        self.outputs['checker']['assessments'][0]['contract'] = 'satisfied'
        result = api.synthesize(self.graph, self.outputs)
        self.assertEqual([], result['findings'])
        self.assertEqual(1, len(result['dropped']))
        self.assertIn('contracts-empty', json.dumps(result['dropped']))

    def test_same_location_independent_claims_are_not_merged(self):
        self.outputs['integration']['findings'] = [finding('integration-limit', function='apply',
            contractId='preserve-limit', claim='Caller silently drops the explicit limit')]
        self.outputs['checker']['assessments'].append(assessment('integration-limit'))
        result = api.synthesize(self.graph, self.outputs)
        self.assertEqual(2, len(result['findings']))
        self.assertEqual({'contracts-empty', 'integration-limit'},
                         {source for item in result['findings'] for source in item['sourceIds']})

    def test_synthesis_validates_before_processing_untrusted_outputs(self):
        self.outputs['checker']['assessments'] = []
        with self.assertRaises(ValueError):
            api.synthesize(self.graph, self.outputs)

    def test_build_rejects_ambiguous_contract_or_function_inventory(self):
        for contracts, functions in (([], FUNCTIONS), (CONTRACTS, []),
                                     (CONTRACTS + [CONTRACTS[0]], FUNCTIONS),
                                     (CONTRACTS, FUNCTIONS + ['parse'])):
            with self.subTest(contracts=contracts, functions=functions), self.assertRaises(ValueError):
                api.build_graph('review-limits', '/synthetic/project', 'src/limits.py',
                                TASK, contracts, functions)


if __name__ == '__main__':
    unittest.main(verbosity=2)
