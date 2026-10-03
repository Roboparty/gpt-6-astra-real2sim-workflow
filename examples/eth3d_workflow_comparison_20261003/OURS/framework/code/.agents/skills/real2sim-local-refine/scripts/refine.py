"""Frozen-region source difference diagnosis and isolated RoomKit part edits."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnose(protocol, base):
    import numpy as np
    from PIL import Image
    if protocol.get('schema') != 'real2sim-roi/1' or not protocol.get('views'):
        raise ValueError('Frozen nonempty real2sim-roi/1 protocol required')
    rows, seen = [], set()
    for view in protocol['views']:
        if view['id'] in seen or view['role'] not in ('fit', 'heldout'):
            raise ValueError('Unique view ids and explicit roles required')
        seen.add(view['id'])
        if not view.get('regions') or not re.fullmatch('[0-9a-f]{64}', view['source_camera_sha256']) or not (view['source_camera_sha256'] == view['candidate_camera_sha256'] == view['baseline_camera_sha256']):
            raise ValueError('Region denominator or fixed camera binding missing')
        images = []
        for key in ('source', 'baseline', 'candidate'):
            entry = view[key]
            path = base/entry['path']
            if sha(path) != entry['sha256']:
                raise ValueError('Image hash mismatch: ' + key)
            with Image.open(path) as im:
                if im.mode != 'RGB':
                    raise ValueError('Explicit RGB conversion must precede freezing')
                images.append(np.asarray(im, dtype=np.float64)/255)
        src, old, new = images
        if src.shape != old.shape or src.shape != new.shape:
            raise ValueError('Resolution mismatch; no auto resize permitted')
        regions = set()
        for r in view['regions']:
            if r['id'] in regions or not r.get('part_ids'):
                raise ValueError('Unique regions and part mapping required')
            regions.add(r['id'])
            x0, y0, x1, y1 = r['xyxy']
            if any(type(x) is not int for x in r['xyxy']) or not (0 <= x0 < x1 <= src.shape[1] and 0 <= y0 < y1 <= src.shape[0]):
                raise ValueError('Region outside source image')
            crop = (slice(y0, y1), slice(x0, x1))
            before = float(np.abs(src[crop]-old[crop]).mean())
            after = float(np.abs(src[crop]-new[crop]).mean())
            rows.append({'view': view['id'], 'role': view['role'], 'region': r['id'],
                         'part_ids': r['part_ids'], 'xyxy': r['xyxy'],
                         'baseline_srgb_mae': before, 'candidate_srgb_mae': after,
                         'delta': after-before, 'worsened': after > before})
    return {'schema': 'real2sim-roi-report/1', 'regions': rows,
            'edit_priority_fit_only': sorted([r for r in rows if r['role'] == 'fit'], key=lambda r: -r['candidate_srgb_mae']),
            'acceptance': 'not_determined', 'geometry_accuracy': 'unverified',
            'note': 'sRGB image diagnostic; does not separate material, lighting or shape causes'}


def edit(scene, change):
    if scene.get('schema') != 'roomkit/1' or change.get('schema') != 'real2sim-part-change/1':
        raise ValueError('Expected RoomKit scene and explicit part-change contract')
    allowed = {'geometry': {'size', 'position', 'rotation', 'fold_amplitude'},
               'material': {'color', 'roughness'}}
    if change.get('mode') not in allowed or not change.get('reason') or not change.get('source_region'):
        raise ValueError('One geometry/material intervention and source-region reason required')
    if not change.get('set') or not set(change['set']) <= allowed[change['mode']]:
        raise ValueError('Mixed or unsupported intervention; lighting uses its own frozen scene adapter')
    candidate = copy.deepcopy(scene)
    parts = [p for p in candidate['parts'] if p['id'] == change['part_id']]
    if len(parts) != 1:
        raise ValueError('Exactly one stable part id required')
    parts[0].update(change['set'])
    parts[0]['prior_status'] = 'assumed'
    parts[0]['prior_source'] = change['reason']
    # Reuse RoomKit validation, not a second geometry implementation.
    import importlib.util
    helper = Path(__file__).resolve().parents[2]/'blender-roomkit/scripts/roomkit.py'
    module_spec = importlib.util.spec_from_file_location('roomkit', helper)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.validate(candidate)
    return candidate


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('diagnose'); d.add_argument('protocol', type=Path); d.add_argument('output', type=Path)
    e = sub.add_parser('edit'); e.add_argument('scene', type=Path); e.add_argument('change', type=Path); e.add_argument('output', type=Path)
    a = p.parse_args()
    if a.command == 'diagnose':
        result = diagnose(json.loads(a.protocol.read_text(encoding='utf-8')), a.protocol.parent)
        result['protocol_sha256'] = sha(a.protocol)
    else:
        change = json.loads(a.change.read_text(encoding='utf-8'))
        if change['scene_sha256'] != sha(a.scene):
            raise ValueError('Base scene drift')
        result = edit(json.loads(a.scene.read_text(encoding='utf-8')), change)
    with a.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, allow_nan=False)
