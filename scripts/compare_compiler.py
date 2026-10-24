"""Gate a compiler upgrade on the unchanged historical design's artifacts."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(before, after, output):
    load = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    old, new = load(before / 'run.json'), load(after / 'run.json')
    if old['demoRevision'] != new['demoRevision']:
        raise ValueError('Compiler control must use exactly the same historical design commit')
    checks = {}
    for case in ('nominal', 'variant'):
        for filename in ('Bracket.step', 'Bracket.glb', 'Bracket.pdf', 'Bracket.svg'):
            key = f'{case}/{filename}'
            checks[key] = hashlib.sha256((before / key).read_bytes()).hexdigest() == hashlib.sha256((after / key).read_bytes()).hexdigest()
    receipt = {'schema': 'code-native-compiler-control/1', 'designRevision': old['demoRevision'],
               'originalCompiler': old['aetherisRevision'], 'proposedCompiler': new['aetherisRevision'],
               'byteIdenticalArtifacts': checks, 'passed': all(checks.values())}
    output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    if not receipt['passed']:
        raise ValueError('Compiler upgrade changed historical artifacts; investigate before accepting')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    compare(a.before, a.after, a.output)
