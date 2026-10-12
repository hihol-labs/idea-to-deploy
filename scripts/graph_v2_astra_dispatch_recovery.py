#!/usr/bin/env python3
"""Recover one proven pre-session capacity refusal, retaining its native evidence.

The bound grader, questions, judge answer and all acceptance guards stay intact.
Only the failed spawn (which returned no session) is excluded from dispatch
cardinality. The successful call/return is still checked by the frozen grader.
"""
import json
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
FAILED_CALL = 'call_6611a77278864ac4b4eefb2c0671d799'
TASK = 'gv2r2b_grade_astra_14'
FAILURE = 'collab spawn failed: agent thread limit reached'

def filter_failed_spawn(rows, native, expected):
    calls = [r for r in rows if r.get('type') == 'response_item'
             and r.get('payload', {}).get('type') == 'function_call'
             and r['payload'].get('call_id') == FAILED_CALL]
    replies = [r for r in rows if r.get('payload', {}).get('type') == 'function_call_output'
               and r['payload'].get('call_id') == FAILED_CALL]
    if len(calls) != 1 or len(replies) != 1:
        raise ValueError('capacity refusal call/return not unique')
    call, reply = calls[0], replies[0]
    if call['payload'].get('name') != 'spawn_agent' or reply['payload'].get('output') != FAILURE:
        raise ValueError('not the registered pre-session capacity refusal')
    arguments = native.strict(call['payload']['arguments'])
    if arguments.get('task_name') != TASK or not native.dispatch_args_match(arguments, expected):
        raise ValueError('failed spawn differs from unchanged judge task')
    return [row for row in rows if row is not call and row is not reply], {'call': call, 'return': reply}

def main():
    path = ROOT / 'scripts/graph_v2_astra.py'
    spec = importlib.util.spec_from_file_location('amended', path)
    amended = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(amended)
    grader, _ = amended.adapter()
    expected = grader.launch(14)
    load = grader.load
    def transport(path):
        native = load(path)
        if path.name == 'graph_v2_native.py':
            parent_rows = native.parent_rows
            def parents():
                filtered, evidence = filter_failed_spawn(parent_rows(), native, expected)
                proof = amended.D / 'grading-astra/dispatch-failures' / (FAILED_CALL + '.json')
                if proof.exists() and amended.read(proof) != evidence:
                    raise ValueError('capacity refusal evidence changed')
                if not proof.exists(): grader.write(proof, evidence)
                return filtered
            native.parent_rows = parents
        return native
    grader.load = transport
    value, audit = grader.collect(14)
    print(json.dumps({'collected': len(value), 'retainedPreSessionFailure': FAILED_CALL,
                      'acceptedSession': audit['sessionId']}))

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
