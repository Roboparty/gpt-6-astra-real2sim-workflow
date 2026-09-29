"""Validate frozen original/baked exports at preregistered virtual viewpoints.

Runs the existing controlled-rig Blender renderer; no export, optimization or
real-image scoring. Complete cell denominators and failures are retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def verify_inputs(cfg, repo):
    for name, expected in cfg['implementation_sha256'].items():
        if sha(repo/name) != expected:
            raise ValueError('Changed implementation: '+name)
    for arm in cfg['arms']:
        for key in ('source_model', 'source_scene'):
            if sha(arm[key]) != arm[key+'_sha256']:
                raise ValueError('Changed source: '+arm[key])
        for rel, expected in arm['export_files_sha256'].items():
            if sha(Path(arm['export_dir'])/rel) != expected:
                raise ValueError('Changed export dependency: '+rel)


def score(cfg, output, report):
    import numpy as np
    from PIL import Image

    def rgb(row):
        path = output/row['arm']/row['view']/row['format']/'render.png'
        if sha(path) != row['render_sha256']:
            raise ValueError('Changed rendered image: '+str(path))
        with Image.open(path) as image:
            value = np.asarray(image.convert('RGB'), dtype=float)/255.
        if value.shape != (cfg['render']['height'], cfg['render']['width'], 3):
            raise ValueError('Unexpected render shape')
        return value

    by_id = {(r['arm'], r['view'], r['format']): r for r in report['cells']}
    rows = []
    for view in cfg['views']:
        for fmt in cfg['formats']:
            row = {'view': view['id'], 'format': fmt, 'status': 'unavailable'}
            rows.append(row)
            needed = [(arm, view['id'], form) for arm in ('original', 'baked')
                      for form in ('native', fmt)]
            if any(by_id[k]['status'] not in {'rendered', 'rendered_geometry_failed'} for k in needed):
                continue
            o, b = rgb(by_id['original', view['id'], fmt]), rgb(by_id['baked', view['id'], fmt])
            on, bn = rgb(by_id['original', view['id'], 'native']), rgb(by_id['baked', view['id'], 'native'])
            row.update(status='scored', original_format_to_original_native_mae=float(abs(o-on).mean()),
                       baked_format_to_baked_native_mae=float(abs(b-bn).mean()),
                       baked_format_to_original_native_mae=float(abs(b-on).mean()),
                       baked_native_to_original_native_mae=float(abs(bn-on).mean()))
    return {'expected_comparisons': len(cfg['views'])*len(cfg['formats']), 'rows': rows,
            'scope': 'Full-image normalized RGB MAE; correlated virtual views of one scene, no real-photo or 3D accuracy, no automatic acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('protocol', 'output', 'blender'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.protocol.read_text(encoding='utf-8-sig'))
    if [a['id'] for a in cfg['arms']] != ['original', 'baked'] or cfg['formats'] != ['native', 'glb', 'usdc']:
        raise ValueError('Requires the complete fixed original/baked three-format comparison')
    if len(cfg['views']) != 3 or len({v['id'] for v in cfg['views']}) != 3:
        raise ValueError('Requires three distinct registered views')
    repo = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(schema='real2sim.portability-view-validation/1', status='started',
                  protocol_sha256=sha(args.protocol), script_sha256=sha(__file__),
                  expected_cells=18, cells=[dict(arm=a['id'], view=v['id'], format=f, status='not_run')
                    for a in cfg['arms'] for v in cfg['views'] for f in cfg['formats']],
                  executions=[], gpu_hours=0, paid_api_requests=0)
    write(args.output/'receipt.json', report)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', R2S_CPU='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    try:
        verify_inputs(cfg, repo)
        for arm in cfg['arms']:
            for view in cfg['views']:
                before = time.monotonic()
                execution = dict(arm=arm['id'], view=view['id'], status='failed')
                report['executions'].append(execution)
                group_dir = args.output/arm['id']/view['id']
                group_dir.parent.mkdir(exist_ok=True)
                child = {k: arm[k] for k in ('source_model', 'source_model_sha256', 'source_scene', 'source_scene_sha256')}
                child.update(render=cfg['render'], render_failed_geometry_as_diagnostic=True,
                             diagnostic_camera_translation_world_m=view['translation_world_m'],
                             parent_protocol_sha256=report['protocol_sha256'], arm=arm['id'], view=view['id'])
                child_path = group_dir.with_suffix('.protocol.json')
                write(child_path, child)
                execution['protocol_sha256'] = sha(child_path)
                try:
                    remaining = cfg['budget']['cpu_wall_seconds']-(time.monotonic()-started)
                    if remaining <= 0:
                        raise TimeoutError('Shared view-validation budget exhausted')
                    free = shutil.disk_usage(args.output).free
                    execution['free_disk_bytes'] = free
                    if free < cfg['budget']['minimum_free_disk_bytes']:
                        raise RuntimeError('Free disk below registered reserve')
                    argv = [str(args.blender), '-b', '-t', '2', '--python-exit-code', '12', '-P',
                            str(repo/'tools/render_interchange_appearance.py'), '--', '--protocol', str(child_path),
                            '--export-dir', arm['export_dir'], '--output', str(group_dir)]
                    with group_dir.with_suffix('.log').open('w') as log:
                        result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=remaining)
                    execution.update(returncode=result.returncode, status='completed' if result.returncode == 0 else 'failed')
                except Exception as error:
                    execution['error'] = repr(error)
                receipt_path = group_dir/'receipt.json'
                if receipt_path.exists():
                    detail = json.loads(receipt_path.read_text())
                    if detail['protocol_sha256'] != execution['protocol_sha256']:
                        raise ValueError('Child protocol binding mismatch')
                    execution['receipt_sha256'] = sha(receipt_path)
                    execution['source_bytes_unchanged'] = detail.get('sources_unchanged')
                    for cell in report['cells']:
                        if (cell['arm'], cell['view']) != (arm['id'], view['id']):
                            continue
                        row = next((r for r in detail['groups'] if r['group'] == cell['format']), None)
                        if row:
                            cell.update({k: row[k] for k in ('status', 'error', 'geometry_status', 'geometry_sha256', 'render_sha256', 'rig_preserved', 'diagnostic_camera') if k in row})
                            cell['rig_sha256'] = hashlib.sha256(json.dumps(row.get('rig_before'), sort_keys=True).encode()).hexdigest()
                            if row.get('rig_before') != row.get('rig_after'):
                                cell.update(status='failed', error='Rig drift in rendered cell')
                execution['wall_seconds'] = time.monotonic()-before
                report['wall_seconds'] = time.monotonic()-started
                write(args.output/'receipt.json', report)
                print(json.dumps(execution), flush=True)
        # Every format and both arms must use the same rig within each view.
        for view in cfg['views']:
            rigs = {r.get('rig_sha256') for r in report['cells'] if r['view'] == view['id']}
            if len(rigs) != 1 or None in rigs:
                raise ValueError('Cross-arm or cross-format rig mismatch: '+view['id'])
        report['cross_arm_rigs_equal'] = True
        verify_inputs(cfg, repo)
        report['sources_and_export_dependencies_unchanged'] = True
        if sha(args.protocol) != report['protocol_sha256']:
            raise ValueError('Parent protocol changed')
        comparisons = score(cfg, args.output, report)
        comparisons['receipt_protocol_sha256'] = report['protocol_sha256']
        write(args.output/'comparison.json', comparisons)
        report['comparison_sha256'] = sha(args.output/'comparison.json')
        report['status'] = 'completed_diagnostic' if all(r['status'] in {'rendered', 'rendered_geometry_failed'} for r in report['cells']) else 'incomplete'
    except Exception as error:
        report.update(status='failed', error=repr(error))
    finally:
        report['wall_seconds'] = time.monotonic()-started
        write(args.output/'receipt.json', report)
    if report['status'] != 'completed_diagnostic':
        raise RuntimeError('View validation incomplete; all cells retained')


if __name__ == '__main__':
    main()
