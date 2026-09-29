"""Synthetic-only producer-evidence contract tests. No Pi3X model is run.

The positive backend-shaped receipt below is deliberately fabricated to test the
validator, not inference evidence. Consistent malicious declarations cannot be
authenticated by hashes. The test report always retains this limitation.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'workflow'))
from r2s.generation_skills import bindings, execute, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = {'skills_root': str(ROOT/'.agents/skills')}
    helper = load(cfg, 'reference', 'reference.py')
    checks = []

    def save(path, data):
        path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')

    def check(name, function, rejected=False):
        try:
            result = function()
        except (ValueError, OSError) as error:
            if not rejected:
                raise
            checks.append({'name': name, 'status': 'passed', 'rejection': str(error)})
            return
        if rejected:
            raise AssertionError('Accepted invalid receipt: ' + name)
        checks.append({'name': name, 'status': 'passed'})
        return result

    frame = out/'synthetic.png'
    Image.new('RGB', (4, 4), (80, 90, 100)).save(frame)
    manifest_path = out/'input.json'
    manifest = helper.freeze({'preprocessing': {'resize': 'none', 'output_size_wh': [4, 4]},
                             'frames': [{'id': 'synthetic', 'path': str(frame),
                                         'pts_seconds': 0, 'role': 'fit'}]}, out)
    save(manifest_path, manifest)
    npz = out/'synthetic_predictions.npz'
    points = np.ones((1, 1, 4, 4, 3), dtype=np.float32)
    np.savez(npz, points=points, local_points=points,
             conf=np.zeros((1, 1, 4, 4, 1), dtype=np.float32),
             camera_poses=np.eye(4, dtype=np.float32)[None, None])
    provenance = {k: manifest[k] for k in ('code_revision', 'weight_revision', 'weight_sha256', 'preprocessing')}
    provenance.update(kind='synthetic_contract', input_sha256=helper.sha(manifest_path),
                      npz_sha256=helper.sha(npz), frame_ids=['synthetic'])
    consume = lambda p, **kw: helper.consume(manifest_path, npz, p, .5, provenance_base=out, **kw)
    result = check('synthetic_nonformal_stays_not_run', lambda: consume(provenance))
    assert result['inference'] == 'not_run' and result['backend_run_binding'] is None
    check('synthetic_formal_rejected', lambda: consume(provenance, formal=True), True)
    relabelled = dict(provenance, kind='backend_output', run_receipt='nonexistent.json')
    check('original_relabel_and_nonexistent_receipt_bypass', lambda: consume(relabelled, formal=True), True)

    producer = out/'producer'; producer.mkdir()
    log = producer/'run.log'
    log.write_text('SYNTHETIC CONTRACT FIXTURE ONLY. No model forward was executed.\n')
    receipt_path = producer/'run.json'
    backend = dict(provenance, kind='backend_output', run_receipt='producer/run.json')
    receipt = {k: backend[k] for k in ('input_sha256', 'npz_sha256', 'code_revision',
                                      'weight_revision', 'weight_sha256', 'preprocessing', 'frame_ids')}
    receipt.update(schema='pi3x-backend-run/1', kind='backend_output', synthetic=False,
                   status='completed', returncode=0, errors=[], forward_run=True,
                   forward_passes=1, checkpoint_loaded=True, checkpoint_sha256_verified=True,
                   checkpoint_missing_keys=[], checkpoint_unexpected_keys=[],
                   provenance_payload_sha256=helper.provenance_payload_sha256(backend),
                   run_log={'path': 'run.log', 'sha256': helper.sha(log)})

    def install(row, prov=None):
        save(receipt_path, row)
        return dict(backend if prov is None else prov, run_receipt_sha256=helper.sha(receipt_path))

    valid = install(receipt)
    result = check('consistent_backend_shaped_fixture_checks_only', lambda: consume(valid, formal=True))
    assert result['backend_run_binding']['path'] == str(receipt_path)
    assert result['inference'] == 'externally_reported_not_independently_verified'
    assert result['geometry_accuracy'] == 'unverified'
    for name, update in [
        ('wrong_schema', {'schema': 'unknown'}),
        ('synthetic_kind', {'kind': 'synthetic_contract'}),
        ('synthetic_flag', {'synthetic': True}),
        ('failed_status', {'status': 'failed'}),
        ('nonzero_returncode', {'returncode': 1}),
        ('false_returncode_not_integer', {'returncode': False}),
        ('reported_errors', {'errors': ['fixture error']}),
        ('forward_not_run', {'forward_run': False}),
        ('zero_forward_passes', {'forward_passes': 0}),
        ('boolean_forward_count', {'forward_passes': True}),
        ('checkpoint_not_loaded', {'checkpoint_loaded': False}),
        ('checkpoint_not_verified', {'checkpoint_sha256_verified': False}),
        ('missing_checkpoint_keys', {'checkpoint_missing_keys': ['layer']}),
        ('unexpected_checkpoint_keys', {'checkpoint_unexpected_keys': ['layer']}),
        ('input_binding', {'input_sha256': '0'*64}),
        ('npz_binding', {'npz_sha256': '0'*64}),
        ('code_binding', {'code_revision': '0'*40}),
        ('weight_revision_binding', {'weight_revision': '0'*40}),
        ('weight_bytes_binding', {'weight_sha256': '0'*64}),
        ('frame_order_binding', {'frame_ids': ['other']}),
        ('preprocessing_binding', {'preprocessing': {'resize': 'changed'}}),
        ('provenance_binding', {'provenance_payload_sha256': '0'*64}),
        ('missing_log', {'run_log': {'path': 'absent.log', 'sha256': '0'*64}}),
        ('log_hash', {'run_log': {'path': 'run.log', 'sha256': '0'*64}}),
    ]:
        bad = copy.deepcopy(receipt); bad.update(update)
        p = install(bad)
        check(name, lambda p=p: consume(p, formal=True), True)
    bad = copy.deepcopy(receipt); del bad['forward_run']
    check('missing_forward_field', lambda: consume(install(bad), formal=True), True)
    p = install(receipt); p['run_receipt_sha256'] = '0'*64
    check('receipt_hash', lambda: consume(p, formal=True), True)
    p = install(receipt); p['synthetic'] = True
    check('synthetic_provenance_flag', lambda: consume(p, formal=True), True)

    prov_path = out/'provenance.json'; valid = install(receipt); save(prov_path, valid)
    cfg['reference'] = {'mode': 'consume', 'manifest': str(manifest_path),
                        'npz': str(npz), 'provenance': str(prov_path)}
    value = {'stage': 'scene_reference', 'generation_skills': cfg, 'formal_test': True,
             'accepted_source_records': [{'path': str(frame), 'sha256': helper.sha(frame)}]}
    native = out/'native'; native.mkdir()
    result = check('native_backend_shaped_contract', lambda: execute(value, native))
    assert result['status'] == 'complete'
    config = {'workflow_profile': 'quality_v2', 'generation_skills': cfg}
    before = bindings(config, 'scene_reference')
    assert str(receipt_path) in before['files'] and str(log) in before['files']
    log.write_text(log.read_text() + 'retained-log drift\n')
    after = bindings(config, 'scene_reference')
    check('log_drift_invalidates_cache', lambda: assert_different(before, after))
    blocked = out/'blocked_log'; blocked.mkdir()
    response = execute(value, blocked)
    assert response['status'] == 'needs_input'
    assert json.loads((blocked/'reference_status.json').read_text())['mode'] == 'blocked'
    checks.append({'name': 'native_drift_fail_closed', 'status': 'passed'})
    receipt['run_log']['sha256'] = helper.sha(log)
    save(prov_path, install(receipt)); before = bindings(config, 'scene_reference')
    save(receipt_path, dict(receipt, forward_run=False))
    check('receipt_drift_invalidates_cache', lambda: assert_different(before, bindings(config, 'scene_reference')))
    save(prov_path, relabelled)
    blocked = out/'blocked_original_bypass'; blocked.mkdir()
    response = execute(value, blocked)
    assert response['status'] == 'needs_input'
    report = json.loads((blocked/'reference_status.json').read_text())
    assert report['mode'] == 'blocked' and 'cameras_opencv_c2w' not in report
    checks.append({'name': 'native_original_bypass_fail_closed', 'status': 'passed'})
    save(out/'test_results.json', {'status': 'passed', 'count': len(checks), 'checks': checks,
        'data_origin': 'synthetic_contract', 'actual_model_forward': False,
        'scope': 'Contract validation only; backend-shaped positive fixture is fabricated, not inference evidence',
        'limitation': 'Consistent self-reported evidence is not independently authenticated'})
    print(json.dumps({'status': 'passed', 'count': len(checks), 'actual_model_forward': False}))


def assert_different(a, b):
    assert a != b


if __name__ == '__main__':
    main()
