"""Freeze input frames or consume Pi3X outputs. Never installs or runs a model."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CODE_REV = '9fa3ddb3f8d53041f8b2738df404f62223bbaa7b'
WEIGHT_REV = 'bb1deea4d7423de5b30691739cb451a3f57dc1d5'
WEIGHT_SHA = '69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def freeze(config, base):
    from PIL import Image
    if not config.get('preprocessing') or not config.get('frames'):
        raise ValueError('Explicit preprocessing and ordered frames required')
    frames, seen = [], set()
    for item in config['frames']:
        if item['id'] in seen or item['role'] not in ('fit', 'heldout'):
            raise ValueError('Unique ids and fit/heldout roles required')
        seen.add(item['id'])
        path = (base/item['path']).resolve()
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            size = list(im.size)
        if not isinstance(item.get('pts_seconds'), (float, int)) or not math.isfinite(item['pts_seconds']) or item['pts_seconds'] < 0:
            raise ValueError('Finite nonnegative exact source PTS required')
        frames.append(dict(item, path=str(path), sha256=sha(path), image_size=size))
    if len({f['sha256'] for f in frames}) != len(frames):
        raise ValueError('Duplicate frame bytes are not independent observations')
    if not any(f['role'] == 'fit' for f in frames):
        raise ValueError('At least one fit frame required')
    return {'schema': 'pi3x-reference-input/1', 'code_revision': CODE_REV,
            'weight_revision': WEIGHT_REV, 'weight_sha256': WEIGHT_SHA,
            'preprocessing': config['preprocessing'], 'frames': frames,
            'scale': 'approximate_unvalidated', 'unobserved': 'unknown',
            'environment': 'not_verified_by_freeze', 'inference': 'not_run',
            'geometry_accuracy': 'unverified'}


def provenance_payload_sha256(provenance):
    """Bind producer declarations without a circular hash of their receipt pointer."""
    payload = {k: v for k, v in provenance.items() if k not in ('run_receipt', 'run_receipt_sha256')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def run_receipt_files(provenance, base):
    """Paths for cache invalidation; validation happens separately in consume."""
    path = provenance.get('run_receipt')
    if not isinstance(path, str) or not path.strip():
        return []
    receipt = (Path(base)/path).resolve()
    paths = [receipt]
    if receipt.is_file():
        try:
            data = json.loads(receipt.read_text(encoding='utf-8'))
            log = data.get('run_log', {}).get('path')
            if isinstance(log, str) and log.strip():
                paths.append((receipt.parent/log).resolve())
        except (ValueError, AttributeError, TypeError):
            pass  # The receipt bytes are still bound; consume rejects malformed data.
    return paths


def validate_backend_run(provenance, base):
    """Check retained evidence consistency, not authenticity of producer claims.

    Required receipt schema: pi3x-backend-run/1; kind=backend_output,
    synthetic=false, status=completed, returncode=0, forward_run=true,
    forward_passes>0, checkpoint_loaded=true, checkpoint_sha256_verified=true,
    checkpoint_missing_keys=[], checkpoint_unexpected_keys=[], errors=[].
    Repeat input_sha256, npz_sha256, code_revision, weight_revision,
    weight_sha256, frame_ids and preprocessing from provenance; bind the remaining
    provenance payload hash and a retained run_log {path, sha256}. Paths resolve
    from the provenance file and receipt file respectively, never from CWD.
    These fields must come from a separately run backend; this adapter runs none.
    """
    paths = run_receipt_files(provenance, base)
    if not paths or not paths[0].is_file():
        raise ValueError('Backend output needs an existing retained run receipt')
    receipt_path = paths[0]
    receipt_sha = sha(receipt_path)
    if provenance.get('run_receipt_sha256') != receipt_sha:
        raise ValueError('Backend run receipt hash mismatch')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if not isinstance(receipt, dict) or receipt.get('schema') != 'pi3x-backend-run/1':
        raise ValueError('Wrong backend run receipt schema')
    if (receipt.get('kind') != 'backend_output' or receipt.get('synthetic') is not False
            or provenance.get('synthetic', False) is not False):
        raise ValueError('Synthetic or unspecified backend execution is not eligible')
    if (receipt.get('status') != 'completed' or type(receipt.get('returncode')) is not int
            or receipt['returncode'] != 0 or receipt.get('errors') != []):
        raise ValueError('Backend execution did not complete successfully')
    if (receipt.get('forward_run') is not True or type(receipt.get('forward_passes')) is not int
            or receipt['forward_passes'] < 1):
        raise ValueError('Backend receipt does not report an actual forward pass')
    if (receipt.get('checkpoint_loaded') is not True
            or receipt.get('checkpoint_sha256_verified') is not True
            or receipt.get('checkpoint_missing_keys') != []
            or receipt.get('checkpoint_unexpected_keys') != []):
        raise ValueError('Backend checkpoint loading is incomplete or incompatible')
    for key in ('input_sha256', 'npz_sha256', 'code_revision', 'weight_revision',
                'weight_sha256', 'frame_ids', 'preprocessing'):
        if key not in receipt or receipt[key] != provenance[key]:
            raise ValueError('Backend receipt binding mismatch: ' + key)
    if receipt.get('provenance_payload_sha256') != provenance_payload_sha256(provenance):
        raise ValueError('Backend receipt provenance payload mismatch')
    log = receipt.get('run_log')
    if not isinstance(log, dict) or not isinstance(log.get('path'), str) or not log['path'].strip():
        raise ValueError('Backend receipt needs a retained execution log')
    log_path = (receipt_path.parent/log['path']).resolve()
    if not log_path.is_file() or log.get('sha256') != sha(log_path):
        raise ValueError('Backend execution log missing or hash mismatch')
    return {'path': str(receipt_path), 'sha256': receipt_sha,
            'run_log': {'path': str(log_path), 'sha256': log['sha256']},
            'validation': 'consistent_retained_producer_declarations',
            'authenticity': 'not_independently_attested'}


def consume(manifest_path, npz_path, provenance, threshold, *, provenance_base=None, formal=False):
    import numpy as np
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'pi3x-reference-input/1':
        raise ValueError('Wrong input manifest schema')
    if (manifest.get('code_revision'), manifest.get('weight_revision'), manifest.get('weight_sha256')) != (CODE_REV, WEIGHT_REV, WEIGHT_SHA):
        raise ValueError('Input revision differs from pinned adapter')
    if not 0 <= threshold <= 1 or not math.isfinite(threshold):
        raise ValueError('Confidence threshold must be in [0,1]')
    for f in manifest['frames']:
        if sha(f['path']) != f['sha256']:
            raise ValueError('Source frame hash drift')
    if provenance['input_sha256'] != sha(manifest_path) or provenance['npz_sha256'] != sha(npz_path):
        raise ValueError('Input/output provenance hash mismatch')
    for field in ('code_revision', 'weight_revision', 'weight_sha256'):
        if provenance[field] != manifest[field]:
            raise ValueError('Backend revision mismatch: ' + field)
    fit = [f['id'] for f in manifest['frames'] if f['role'] == 'fit']
    if provenance['frame_ids'] != fit or provenance['preprocessing'] != manifest['preprocessing']:
        raise ValueError('Frame order, heldout leakage or preprocessing mismatch')
    if provenance.get('kind') not in ('synthetic_contract', 'backend_output'):
        raise ValueError('Explicit output origin required')
    if formal and provenance['kind'] != 'backend_output':
        raise ValueError('Synthetic reference cannot enter a formal generation case')
    run_binding = None
    if provenance['kind'] == 'backend_output':
        if not isinstance(provenance.get('run_receipt'), str) or not provenance['run_receipt'].strip():
            raise ValueError('Backend output needs a retained run receipt path')
        if provenance_base is None and not Path(provenance.get('run_receipt', '')).is_absolute():
            raise ValueError('Relative run receipt requires the provenance file directory')
        run_binding = validate_backend_run(provenance, provenance_base or manifest_path.parent)
    with np.load(npz_path, allow_pickle=False) as arrays:
        values = {k: arrays[k] for k in ('points', 'local_points', 'conf', 'camera_poses')}
    points, local, conf, poses = [values[k] for k in ('points', 'local_points', 'conf', 'camera_poses')]
    if points.ndim != 5 or points.shape[:2] != (1, len(fit)) or points.shape[-1] != 3 or min(points.shape[2:4]) < 1:
        raise ValueError('Expected points [1,N,H,W,3]')
    if local.shape != points.shape or conf.shape != points.shape[:-1]+(1,) or poses.shape != (1, len(fit), 4, 4):
        raise ValueError('Pi3X output shapes differ from pinned model API')
    size = manifest['preprocessing'].get('output_size_wh')
    if size is not None and list(points.shape[2:4]) != [size[1], size[0]]:
        raise ValueError('Output raster differs from frozen preprocessing')
    if any(not np.issubdtype(v.dtype, np.floating) or not np.isfinite(v).all() for v in values.values()):
        raise ValueError('Nonfinite or nonfloating output')
    if not np.allclose(poses[..., 3, :], [0, 0, 0, 1], atol=1e-5):
        raise ValueError('Invalid homogeneous pose')
    rotation = poses[..., :3, :3]
    if not np.allclose(rotation.swapaxes(-1, -2) @ rotation, np.eye(3), atol=1e-3) or not np.allclose(np.linalg.det(rotation), 1, atol=1e-3):
        raise ValueError('Pose rotation is not SO(3)')
    predicted = np.einsum('bnij,bnhwj->bnhwi', rotation, local) + poses[..., :3, 3][:, :, None, None, :]
    if not np.allclose(predicted, points, atol=1e-3, rtol=1e-4):
        raise ValueError('Global points inconsistent with camera-to-world convention')
    prob = 1/(1+np.exp(-np.clip(conf.astype('float64'), -700, 700)))
    return {'schema': 'pi3x-reference-receipt/1', 'origin': provenance['kind'],
            'input_sha256': sha(manifest_path), 'npz_sha256': sha(npz_path),
            'array_shape': list(points.shape), 'cameras_opencv_c2w': poses[0].tolist(),
            'confidence_encoding': 'sigmoid_of_raw_logits', 'threshold': threshold,
            'retained_fraction_by_frame': (prob[0, ..., 0] >= threshold).mean(axis=(1, 2)).tolist(),
            'intrinsics': None, 'intrinsics_note': 'Not an output of this adapter; do not invent K',
            'scale': 'approximate_unvalidated', 'unobserved': 'unknown',
            'environment': 'not_verified_by_consumer',
            'inference': 'not_run' if provenance['kind'] == 'synthetic_contract' else 'externally_reported_not_independently_verified',
            'backend_run_binding': run_binding,
            'geometry_accuracy': 'unverified'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze'); f.add_argument('config', type=Path); f.add_argument('output', type=Path)
    c = sub.add_parser('consume'); c.add_argument('manifest', type=Path); c.add_argument('npz', type=Path)
    c.add_argument('provenance', type=Path); c.add_argument('output', type=Path)
    c.add_argument('--threshold', type=float, default=.5)
    c.add_argument('--formal', action='store_true', help='Reject synthetic data; require a bound backend execution receipt')
    a = p.parse_args()
    result = freeze(json.loads(a.config.read_text(encoding='utf-8')), a.config.parent) if a.command == 'freeze' else consume(a.manifest, a.npz, json.loads(a.provenance.read_text(encoding='utf-8')), a.threshold, provenance_base=a.provenance.parent, formal=a.formal)
    with a.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, allow_nan=False)
