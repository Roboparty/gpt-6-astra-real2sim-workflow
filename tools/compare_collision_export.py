"""Paired exporter experiment on a retained scene; never writes source artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    source = args.source_export.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Output exists; retain previous experiment and choose a new path')
    output.mkdir(parents=True)
    inputs = [source / 'scene.json', source / 'geometry_audit.json']
    inputs += sorted((source / 'meshes').glob('*'))
    original_hashes = {str(p.relative_to(source)): sha(p) for p in inputs if p.is_file()}
    runs = []
    for name, code in [('baseline', args.baseline_code), ('candidate', args.candidate_code)]:
        directory = output / name
        directory.mkdir()
        for path in inputs:
            if not path.is_file():
                continue
            target = directory / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        if args.openings:
            # A separate matched-input experiment, applied identically to both arms.
            scene = json.loads((directory / 'scene.json').read_text())
            scene['room']['openings'] = json.loads(args.openings.read_text())
            (directory / 'scene.json').write_text(json.dumps(scene, indent=2))
        script = code.resolve() / 'workflow' / 'r2s' / 'simulation.py'
        command = [sys.executable, str(script), str(directory / 'scene.json'), str(directory)]
        start = time.monotonic()
        env = dict(os.environ, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
        with (directory / 'stdout.log').open('w') as stdout, (directory / 'stderr.log').open('w') as stderr:
            try:
                proc = subprocess.run(command, stdout=stdout, stderr=stderr, env=env,
                                      timeout=args.timeout, check=False)
                code_value = proc.returncode
                status = 'passed' if code_value == 0 else 'failed'
            except subprocess.TimeoutExpired:
                code_value, status = None, 'timeout'
        audit_path = directory / 'simulation_audit.json'
        audit = json.loads(audit_path.read_text()) if audit_path.exists() else None
        record = dict(arm=name, status=status, returncode=code_value,
                      wall_seconds=time.monotonic() - start, command=command,
                      script_sha256=sha(script), scene_sha256=sha(directory / 'scene.json'),
                      implementation={p.name: sha(p) for p in sorted(script.parent.glob('*.py'))},
                      audit=audit, stderr_tail=(directory / 'stderr.log').read_text()[-3000:])
        runs.append(record)
        (directory / 'run.json').write_text(json.dumps(record, indent=2))
    after = {str(p.relative_to(source)): sha(p) for p in inputs if p.is_file()}
    report = dict(schema='real2sim.collision-comparison/1',
                  protocol='PROTOCOL_20260929', source_export=str(source),
                  input_hashes=original_hashes, source_unchanged=after == original_hashes,
                  added_openings_sha256=sha(args.openings) if args.openings else None,
                  same_scene_input=runs[0]['scene_sha256'] == runs[1]['scene_sha256'],
                  denominator=len(runs), runs=runs,
                  scope='One retained development scene; no visual acceptance or SOTA claim')
    (output / 'comparison.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ['source_unchanged', 'same_scene_input', 'denominator']}))
    print(json.dumps([{k: r[k] for k in ['arm', 'status', 'wall_seconds']} for r in runs]))
    if not report['source_unchanged'] or not report['same_scene_input']:
        raise RuntimeError('Experiment integrity failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source-export', 'baseline-code', 'candidate-code', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--openings', type=Path)
    parser.add_argument('--timeout', type=int, default=1800)
    run(parser.parse_args())
