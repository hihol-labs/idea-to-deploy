#!/usr/bin/env python3
"""Owner-authorized judge-only amendment; original collection/source freeze stays intact.

Reuse the hash-pinned grader via a narrow AST adaptation: judge identity and output
namespace only. No question, rubric, scoring or measured-agent code is modified.
"""
import ast
import hashlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / '.itd-memory/graph-v2-study-r2'
AMENDMENT = ROOT / 'docs/measurements/graph-v2/ASTRA_AMENDMENT.json'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def load(path):
    module = types.ModuleType('amended_dependency')
    module.__file__ = str(path)
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), module.__dict__)
    return module

class JudgeOnly(ast.NodeTransformer):
    def __init__(self):
        self.models = 0

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            if node.value == 'gpt-6.1-sol':
                self.models += 1
                return ast.copy_location(ast.Constant('gpt-6-astra'), node)
            if node.value.startswith('grading/'):
                return ast.copy_location(ast.Constant('grading-astra/' + node.value[8:]), node)
            if node.value == 'verdicts.json':
                return ast.copy_location(ast.Constant('verdicts-astra.json'), node)
        return node

def adapter():
    amendment = read(AMENDMENT)
    if amendment['graderModel'] != 'gpt-6-astra' or amendment['reasoningEffort'] != 'high':
        raise ValueError('unapproved judge identity')
    for filename, field in [('collection-verification.json', 'collectionSha256'),
                            ('queue.json', 'queueSha256'),
                            ('grading/freeze.json', 'originalGradingFreezeSha256')]:
        if digest(D / filename) != amendment[field]:
            raise ValueError('amendment input changed: ' + filename)
    study = load(ROOT / 'scripts/graph_v2_study.py')
    study.replay()
    freeze = read(D / 'freeze.json')
    for original, expected in freeze['files'].items():
        relative = Path(original).relative_to(freeze['projectRoot'])
        if digest(ROOT / relative) != expected or digest(D / 'source-snapshot' / relative) != expected:
            raise ValueError('original frozen source/input changed')
    source = ROOT / 'scripts/graph_v2_grade.py'
    transform = JudgeOnly()
    tree = transform.visit(ast.parse(source.read_text(encoding='utf-8')))
    if transform.models != 2:
        raise ValueError('unexpected original grader model guards')
    module = types.ModuleType('astra_grader')
    module.__file__ = str(Path(__file__))
    exec(compile(ast.fix_missing_locations(tree), str(source), 'exec'), module.__dict__)
    module.GRADER_PREFIX += '_astra'
    original_launch = module._launch
    def launch(index, attempt):
        return dict(original_launch(index, attempt), model='gpt-6-astra', reasoning_effort='high')
    module._launch = launch
    original_frozen = module.frozen
    def frozen():
        value = original_frozen()
        if value.get('amendmentSha256') != digest(AMENDMENT):
            raise ValueError('judge amendment changed')
        return value
    module.frozen = frozen
    return module, study

def initialize():
    grader, study = adapter()
    if (D / 'grading-astra').exists():
        raise ValueError('amended grading already initialized')
    native = load(ROOT / 'scripts/graph_v2_native.py')
    for row in native.parent_rows():
        payload = row.get('payload', {})
        if payload.get('name') == 'spawn_agent':
            args = native.strict(payload['arguments'])
            if args.get('task_name', '').startswith(grader.CONTEXT['grader'] + '_'):
                raise ValueError('judge already dispatched before amendment initialization')
    for folder in ('native', 'answers', 'audits', 'rejected', 'violations'):
        if any((D / 'grading' / folder).glob('*')):
            raise ValueError('original grading already has evidence')
    original = read(D / 'grading/freeze.json')
    for index, batch in enumerate(grader.batches()):
        if batch != read(D / 'grading/batches' / (str(index) + '.json')):
            raise ValueError('original questions changed')
        grader.write(D / 'grading-astra/batches' / (str(index) + '.json'), batch)
        if digest(D / 'grading-astra/batches' / (str(index) + '.json')) != digest(D / 'grading/batches' / (str(index) + '.json')):
            raise ValueError('capsule bytes changed')
    grader.write(D / 'grading-astra/attempts.json', {})
    original.update(scriptSha256=digest(__file__), amendmentSha256=digest(AMENDMENT),
                    attemptsSha256=digest(D / 'grading-astra/attempts.json'))
    grader.write(D / 'grading-astra/freeze.json', original)
    return {'status': 'ASTRA_GRADING_FROZEN', 'batches': original['batches'], 'questions': len(read(D / 'queue.json')['items'])}

def main():
    command = sys.argv[1]
    if command == 'initialize':
        return initialize()
    grader, study = adapter()
    if command == 'launch': return grader.launch(int(sys.argv[2]))
    if command == 'collect': return {'collected': len(grader.collect(int(sys.argv[2]))[0])}
    if command == 'retry': return grader.retry(int(sys.argv[2]))
    if command == 'combine': return grader.combine()
    if command == 'verify':
        grading = grader.combine(False)
        proof = load(ROOT / 'tests/verify_graph_study_result.py')
        native = load(ROOT / 'scripts/graph_v2_native.py')
        parent = read(study.PROTO)['parentThreadId']
        for index in range(grader.frozen()['batches']):
            audit = read(D / 'grading-astra/audits' / (str(index) + '.json'))
            raw = (D / 'grading-astra/native' / (audit['nativeSha256'] + '.jsonl')).read_bytes()
            proof.native_proof(audit, raw, native, parent, '/root/' + grader.launch(index)['task_name'])
        for key in read(D / 'grading-astra/attempts.json'):
            audit = grader.rejected_proof(int(key))
            raw = (D / 'grading-astra/native' / (audit['nativeSha256'] + '.jsonl')).read_bytes()
            proof.native_proof(audit, raw, native, parent, '/root/' + grader._launch(int(key), 0)['task_name'])
        scorer = load(ROOT / 'skills/graph/scripts/itd_graph_score.py')
        manifest, results = read(D / 'sealed/manifest.json'), read(D / 'results.json')
        if scorer.build_queue(manifest, results) != read(D / 'queue.json'):
            raise ValueError('blind queue changed')
        score = scorer.score(manifest, results, read(D / 'verdicts-astra.json'))
        score_path = D / 'score-astra.json'
        if score_path.exists() and read(score_path) != score:
            raise ValueError('registered amended score changed')
        if not score_path.exists(): grader.write(score_path, score)
        return {'status': 'AMENDED_STUDY_VERIFIED', 'collection': study.replay(), 'grading': grading,
                'measuredModel': 'gpt-6.1-sol', 'graderModel': 'gpt-6-astra', 'score': score}
    raise ValueError('unknown amendment command')

if __name__ == '__main__':
    try: print(json.dumps(main(), ensure_ascii=False))
    except Exception as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
