"""Qualify exported components, semantic seating and roundtrip using Aetheris CLI."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def near(a, b, tolerance=1e-8):
    return len(a) == len(b) and all(abs(x - y) <= tolerance for x, y in zip(a, b))


def glb_triangles(path):
    """Read actual exported triangle positions and node matrices, in model mm."""
    data = path.read_bytes()
    require(struct.unpack_from('<4sII', data) == (b'glTF', 2, len(data)), 'Invalid GLB container')
    chunks, offset = {}, 12
    while offset < len(data):
        length, kind = struct.unpack_from('<II', data, offset)
        chunks[kind] = data[offset + 8:offset + 8 + length]
        offset += 8 + length
    doc, binary = json.loads(chunks[0x4E4F534A]), chunks[0x004E4942]

    def accessor(index):
        a = doc['accessors'][index]
        v = doc['bufferViews'][a['bufferView']]
        count = {'VEC3': 3, 'SCALAR': 1}[a['type']]
        fmt = '<' + {5126: 'f', 5125: 'I', 5123: 'H', 5121: 'B'}[a['componentType']] * count
        start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = v.get('byteStride', struct.calcsize(fmt))
        return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(a['count'])]

    identity = [float(i % 5 == 0) for i in range(16)]
    components = {}

    def visit(index, parent):
        node = doc['nodes'][index]
        require(not any(k in node for k in ('rotation', 'translation', 'scale')), 'Expected exporter matrix transforms')
        local = node.get('matrix', identity)
        world = [sum(parent[k * 4 + row] * local[col * 4 + k] for k in range(4))
                 for col in range(4) for row in range(4)]
        if 'mesh' in node:
            triangles = []
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                require(primitive.get('mode', 4) == 4, 'Expected triangle mesh')
                points = []
                for p in accessor(primitive['attributes']['POSITION']):
                    v = [sum(world[k * 4 + r] * (*p, 1)[k] for k in range(4)) for r in range(3)]
                    points.append((v[0] * 1000, -v[2] * 1000, v[1] * 1000))
                indices = [i[0] for i in accessor(primitive['indices'])]
                triangles.extend(tuple(points[i] for i in indices[n:n + 3]) for n in range(0, len(indices), 3))
            components[node['name'].split('.')[-1]] = triangles
        for child in node.get('children', []):
            visit(child, world)

    for root in doc['scenes'][doc.get('scene', 0)]['nodes']:
        visit(root, identity)
    require(set(components) == {'Bracket', 'Fastener'}, 'GLB lost named components')
    return components


def qualify(directory, cli, reconstructor):
    output = directory / 'assembly'
    evidence = output / 'evidence'
    evidence.mkdir()
    dims = json.loads((directory / 'qualification.json').read_text())['dimensions']

    def run(name, *args):
        p = subprocess.run(['dotnet', str(cli), *map(str, args), '--json'], capture_output=True, text=True, encoding='utf-8')
        (evidence / (name + '.json')).write_text(p.stdout, encoding='utf-8')
        require(p.returncode == 0, f'{name}: {p.stdout[:1800]} {p.stderr[:800]}')
        return json.loads(p.stdout)

    def inspect(source, name, x):
        doc = run(name, 'asm', 'inspect', source)
        g = doc['geometryArtifact']
        require(doc['success'] and len(g['definitions']) == 2, 'Assembly did not retain two definitions')
        residuals = g['mateResiduals']
        require(len(residuals) == 1 and residuals[0]['passed'] and
                residuals[0]['positionResidualMm'] < 1e-8 and residuals[0]['angularResidualRadians'] < 1e-8,
                'Named seating mate failed')
        instances = doc['assemblyIr']['instances']
        fastener = next(i for i in instances if i['path']['segments'][-1] == 'Fastener')
        require(near(fastener['resolvedTransform']['matrix'][12:15], [x, dims['HoleY'], -4]), 'Semantic seat placement changed')
        return doc

    for part in ('fastener', 'bracket'):
        validation = run(part + '-validation', 'validate', output / (part + '.firmament'))['firmamentV2Validation']
        require(validation['status'] == 'valid' and validation['validationLevel'] == 'Built', part + ' not built during validation')
        run(part + '-build', 'build', output / (part + '.firmament'), '--out', output / (part.title() + '.step'))
    mass = run('fastener-verification', 'verify', output / 'Fastener.step', '--evidence-dir', evidence / 'verification')['brepMassProperties']
    radius, head, length, chamfer = (dims['ShaftDiameter'] - .3) / 2, dims['EntryDiameter'] / 2, dims['Thickness'] + 4, .5
    head_height = head - radius
    # Independent analytic volume: shaft + head frustum - removed terminal ring.
    expected = math.pi * radius ** 2 * (length - head_height) + math.pi * head_height / 3 * (radius ** 2 + radius * head + head ** 2)
    expected -= math.pi * chamfer * (radius ** 2 - (radius ** 2 + radius * (radius - chamfer) + (radius - chamfer) ** 2) / 3)
    require(mass['status'] == 'NumericalWithBound' and mass['isEnclosed'] and mass['isOrientationConsistent'] and
            mass['errorBound'] is not None and abs(mass['absoluteVolume'] - expected) <= mass['errorBound'],
            'Chamfered fastener independent mass check failed')
    families = sorted(f['surfaceKind'] for f in mass['faceContributions'])
    require(families == ['Cone', 'Cone', 'Cylinder', 'Plane', 'Plane'], 'Fastener analytic surface families changed')
    subprocess.run([sys.executable, str(reconstructor), '--pdf', str(directory / 'Bracket.pdf'),
                    '--reference-step', str(output / 'Bracket.step'), '--out-dir', str(evidence / 'drawing-reconstruction'), '--cli', str(cli)], check=True)
    source = output / 'mounted-bracket.firmasm'
    original = inspect(source, 'inspection', dims['HoleX'])
    run('step-export', 'asm', 'export-ap242', source, '--out', output / 'MountedBracket.step')
    run('glb-export', 'asm', 'export-glb', source, output / 'MountedBracket.glb')
    analysis = run('analysis', 'analyze', 'assembly', output / 'MountedBracket.step')
    require(analysis['importStatus'] == 'Qualified' and analysis['definitionCount'] == analysis['occurrenceCount'] == analysis['bodyCount'] == 2,
            'AP242 product structure failed')
    require(analysis['semanticPmi']['success'] and not analysis['semanticPmi']['items'],
            'Assembly unexpectedly inherited part-owned PMI')
    require(near(analysis['assemblyBoundingBox']['minimum'], [0, 0, -4]) and
            near(analysis['assemblyBoundingBox']['maximum'], [dims['Width'], dims['Height'], dims['Thickness']]), 'Assembly STEP bounds changed')
    components = glb_triangles(output / 'MountedBracket.glb')
    for name, low, high in [('Bracket', [0, 0, 0], [dims['Width'], dims['Height'], dims['Thickness']]),
                            ('Fastener', [dims['HoleX'] - head, dims['HoleY'] - head, -4],
                             [dims['HoleX'] + head, dims['HoleY'] + head, dims['Thickness']])]:
        points = [p for t in components[name] for p in t]
        require(near([min(p[a] for p in points) for a in range(3)], low, 1e-4) and
                near([max(p[a] for p in points) for a in range(3)], high, 1e-4), name + ' GLB placement/bounds changed')
    tip = [p for t in components['Fastener'] for p in t if abs(p[2] + 4) < 1e-4]
    require(tip and all(abs(math.hypot(p[0] - dims['HoleX'], p[1] - dims['HoleY']) - (radius - chamfer)) < 1e-4 for p in tip),
            'GLB terminal chamfer radius missing')
    shoulder = [p for t in components['Fastener'] for p in t if abs(p[2] - (-4 + chamfer)) < 1e-4]
    require(shoulder and all(abs(math.hypot(p[0] - dims['HoleX'], p[1] - dims['HoleY']) - radius) < 1e-4 for p in shoulder),
            'GLB chamfer shoulder height/radius missing')
    imported = run('import', 'asm', 'import-step', output / 'MountedBracket.step', '--out', evidence / 'roundtrip')
    run('roundtrip-export', 'asm', 'export-ap242', imported['firmasmPath'], '--out', evidence / 'roundtrip.step')
    replay = run('roundtrip-analysis', 'analyze', 'assembly', evidence / 'roundtrip.step')
    require(replay['importStatus'] == 'Qualified' and replay['definitionCount'] == replay['occurrenceCount'] == replay['bodyCount'] == 2,
            'Roundtrip lost product structure')
    require(replay['assemblyBoundingBox'] == analysis['assemblyBoundingBox'], 'Roundtrip changed bounds')
    require(all(near(a, b) for a, b in zip(sorted(o['worldTransform'] for o in analysis['occurrences']),
                                         sorted(o['worldTransform'] for o in replay['occurrences']))), 'Roundtrip changed transforms')
    replay_inspection = run('roundtrip-inspection', 'asm', 'inspect', imported['firmasmPath'])
    metrics = lambda doc: sorted(json.dumps(d['metrics'], sort_keys=True) for d in doc['geometryArtifact']['definitions'])
    require(metrics(original) == metrics(replay_inspection), 'Roundtrip changed component topology/local bounds')
    # A moved hole must carry the mate, while both shape definitions remain unchanged except the bracket.
    relocated = evidence / 'relocated'
    relocated.mkdir()
    for p in output.glob('*.firma*'):
        shutil.copy2(p, relocated / p.name)
    parameters = relocated / 'parameters.firmament'
    old = f'holeX: {dims["HoleX"]:g}mm'
    text = parameters.read_text()
    require(text.count(old) == 1, 'Relocation guard could not identify the authored parameter')
    parameters.write_text(text.replace(old, f'holeX: {dims["HoleX"] - 1:g}mm'), encoding='utf-8')
    moved = inspect(relocated / source.name, 'relocated-inspection', dims['HoleX'] - 1)
    fastener_hash = lambda d: next(x['stepSha256'] for x in d['geometryArtifact']['definitions'] if x['definitionIdentity'].startswith('Fastener<'))
    require(fastener_hash(original) == fastener_hash(moved), 'Hole relocation changed the fastener definition')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    receipt = {'status': 'passed', 'components': 2, 'mate': 'InstallFastener', 'seatResidualMm': 0,
               'diametralClearanceMm': .3, 'tipChamferMm': chamfer, 'tipChamferDegrees': 45,
               'analyticFastenerVolumeMm3': expected, 'evaluatedFastenerVolumeMm3': mass['absoluteVolume'],
               'numericalVolumeErrorBoundMm3': mass['errorBound'], 'numericalVolumeMethod': mass['evaluationMethod'],
               'drawingReconstructsAssemblyBracket': True, 'stepRoundtripQualified': True,
               'glbWorldBoundsQualified': True, 'holeRelocationFollowsMate': True, 'hashes': hashes,
               'assemblyPmiItems': 0,
               'limits': ['Threadless blank; no drive recess, retention or strength qualification.',
                          'Nominal seating only; angular/location stacks and process capability unqualified.',
                          'Part PMI stays part-owned; assembly PMI must be explicitly authored.']}
    (output / 'qualification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('directory', 'cli', 'reconstructor'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    qualify(args.directory.resolve(), args.cli.resolve(), args.reconstructor.resolve())
