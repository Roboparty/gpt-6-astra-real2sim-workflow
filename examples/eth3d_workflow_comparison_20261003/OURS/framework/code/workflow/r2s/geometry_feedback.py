"""Fixed-camera image diagnostics; these scores do not measure unseen 3-D truth."""
import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_erosion, distance_transform_edt

from .contracts import digest
from .camera import focal_xy,validate_camera


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _artifact(record, base):
    path = Path(base) / record['path']
    if file_sha256(path) != record['sha256']:
        raise ValueError('Artifact hash mismatch: ' + str(path))
    return path


def _image(record, base, size, binary=False):
    with Image.open(_artifact(record, base)) as im:
        if im.size != tuple(size):
            raise ValueError('Image size differs from frozen camera; resizing is forbidden')
        if not binary:
            return im.convert('RGB')
        if im.mode not in ('1', 'L'):
            raise ValueError('Binary masks must be 1-bit or grayscale PNGs')
        arr = np.array(im)
    values = set(np.unique(arr).tolist())
    if not (values <= {0, 1} or values <= {0, 255}):
        raise ValueError('Mask is not binary; soft masks must be reviewed before freezing')
    return arr != 0


def _unique(items, key='id'):
    indexed = {item[key]: item for item in items}
    if len(indexed) != len(items) or any(not isinstance(k, str) or not k for k in indexed):
        raise ValueError('IDs must be unique nonempty strings')
    return indexed


def _finite(value, shape):
    arr = np.asarray(value, dtype=float)
    if arr.shape != shape or not np.isfinite(arr).all():
        raise ValueError('Nonfinite value or incorrect coordinate shape')
    return arr


def _camera(camera):
    validate_camera(camera)
    size = camera['image_size']
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError('Camera needs positive integer image dimensions')
    rotation = _finite(camera['rotation_world_to_cv'], (3, 3))
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-6):
        raise ValueError('Camera rotation is not a proper orthonormal matrix')
    _finite(camera['position'], (3,))
    _finite(camera['principal_point'], (2,))
    if not math.isfinite(camera['focal_px']) or camera['focal_px'] <= 0:
        raise ValueError('Camera focal length must be positive and finite')


def _project(xyz, camera):
    point = (_finite(xyz, (3,)) - camera['position']) @ np.asarray(camera['rotation_world_to_cv']).T
    if point[2] <= 0:
        raise ValueError('Landmark is behind the frozen camera')
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        uv = point[:2] / point[2] * focal_xy(camera) + camera['principal_point']
    if not np.isfinite(uv).all():
        raise ValueError('Landmark projection is nonfinite')
    return uv


def _boundary(mask):
    return mask & ~binary_erosion(mask, border_value=0)


def mask_metrics(source, rendered):
    """Equal weight per direction; an absent contour gets the image diagonal penalty."""
    diagonal = float(math.hypot(*source.shape))
    source_count, render_count = int(source.sum()), int(rendered.sum())
    intersection, union = int((source & rendered).sum()), int((source | rendered).sum())
    result = {'source_pixels': source_count, 'rendered_pixels': render_count,
              'intersection_pixels': intersection, 'union_pixels': union,
              'iou': intersection / union if union else 0.,
              'boundary_mean_px': diagonal, 'boundary_max_px': diagonal,
              'centroid_delta_xy_px': None, 'bbox_scale_xy': None}
    if source_count and render_count:
        a, b = _boundary(source), _boundary(rendered)
        ab, ba = distance_transform_edt(~b)[a], distance_transform_edt(~a)[b]
        result.update(boundary_mean_px=float((ab.mean() + ba.mean()) / 2),
                      boundary_max_px=float(max(ab.max(), ba.max())))
        sy, sx = np.where(source)
        ry, rx = np.where(rendered)
        result['centroid_delta_xy_px'] = [float(rx.mean() - sx.mean()), float(ry.mean() - sy.mean())]
        result['bbox_scale_xy'] = [float((np.ptp(rx) + 1) / (np.ptp(sx) + 1)),
                                  float((np.ptp(ry) + 1) / (np.ptp(sy) + 1))]
    return result


def _overlay(source_image, source_mask, rendered_mask, landmarks, output):
    rgb = np.array(source_image).copy()
    if source_mask is not None:
        rgb[_boundary(source_mask)] = [0, 255, 0]
        rgb[_boundary(rendered_mask)] = [255, 0, 255]
        rgb[_boundary(source_mask) & _boundary(rendered_mask)] = [255, 255, 255]
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    for landmark in landmarks:
        x, y = landmark['source_uv']
        draw.ellipse((x-3, y-3, x+3, y+3), outline='lime')
        if landmark['rendered_uv'] is not None:
            u, v = landmark['rendered_uv']
            draw.line((x, y, u, v), fill='yellow', width=1)
            draw.line((u-3, v-3, u+3, v+3), fill='magenta')
            draw.line((u-3, v+3, u+3, v-3), fill='magenta')
    image.save(output)
    return {'path': str(output), 'sha256': file_sha256(output)}


def _summary(rows):
    masks = [r['mask'] for r in rows if r['mask'] is not None]
    landmarks = [p for r in rows for p in r['landmarks']]
    passed = sum(r['status'] == 'passed' for r in rows)
    return {'expected_objects': len(rows), 'passed_objects': passed,
            'failed_objects': len(rows) - passed,
            'error_objects': sum(bool(r['errors']) for r in rows),
            'pass_rate': passed / len(rows) if rows else None,
            'expected_masks': len(masks),
            'mean_iou_with_failures': float(np.mean([m['iou'] for m in masks])) if masks else None,
            'mean_boundary_px_with_failures': float(np.mean([m['boundary_mean_px'] for m in masks])) if masks else None,
            'expected_landmarks': len(landmarks),
            'failed_landmarks': sum(not p['passed'] for p in landmarks),
            'mean_landmark_error_px_with_failures': float(np.mean([p['error_px'] for p in landmarks])) if landmarks else None}


def evaluate_geometry_feedback(protocol, candidate, protocol_base='.', candidate_base='.', output_dir=None):
    """Evaluate every declared view/object, including failed artifact reads and absent results.

    Invalid protocols raise ValueError. Candidate/reference artifact failures become failed
    rows, retaining the declared denominator. Pin digest(protocol) outside the candidate.
    """
    if protocol.get('schema') != 'real2sim.geometry-feedback-protocol/1.0':
        raise ValueError('Unsupported geometry feedback protocol')
    views = _unique(protocol['views'])
    if not views:
        raise ValueError('Empty evaluation scope')
    limits = protocol['thresholds']
    for key in ('minimum_iou', 'maximum_boundary_mean_px', 'maximum_landmark_error_px'):
        if not math.isfinite(limits[key]) or limits[key] < 0:
            raise ValueError('Invalid threshold: ' + key)
    if limits['minimum_iou'] > 1:
        raise ValueError('IoU threshold exceeds one')
    source_roles = {}
    for view in views.values():
        _camera(view['camera'])
        if view['role'] not in ('fit', 'heldout'):
            raise ValueError('View role must be fit or heldout')
        sha = view['source']['sha256']
        if sha in source_roles and source_roles[sha] != view['role']:
            raise ValueError('Identical source bytes cannot be both fit and heldout')
        source_roles[sha] = view['role']
        objects = _unique(view['objects'])
        if not objects:
            raise ValueError('Every view needs a predeclared object denominator')
        for obj in objects.values():
            if 'mask' not in obj and not obj.get('landmarks'):
                raise ValueError('Expected object has no observations')
            for point in _unique(obj.get('landmarks', [])).values():
                uv = _finite(point['uv'], (2,))
                if np.any(uv < 0) or np.any(uv >= view['camera']['image_size']):
                    raise ValueError('Source landmark lies outside the frozen image')
    errors = []
    if candidate.get('schema') != 'real2sim.geometry-feedback-candidate/1.0':
        errors.append('Unsupported candidate schema')
    if candidate.get('protocol_sha256') != digest(protocol):
        errors.append('Candidate is bound to a different protocol')
    if 'reconstruction_source_sha256' not in candidate:
        errors.append('Candidate must declare reconstruction source hashes, including an empty list when applicable')
    used = candidate.get('reconstruction_source_sha256', [])
    if any(source_roles.get(sha) == 'heldout' for sha in used):
        errors.append('Heldout source was used for reconstruction; it cannot be reported as heldout')
    try:
        _artifact(candidate['model'], candidate_base)
        candidate_views = _unique(candidate.get('views', []))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
        candidate_views = {}
    if set(candidate_views) - set(views):
        errors.append('Candidate has undeclared views')
    output = Path(output_dir) if output_dir else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    rows = []
    for view_index, view in enumerate(views.values()):
        cv = candidate_views.get(view['id'], {})
        view_errors = list(errors)
        source_image, id_image = None, None
        objects = {}
        size = view['camera']['image_size']
        diagonal = float(math.hypot(*size))
        try:
            source_image = _image(view['source'], protocol_base, size)
            if cv.get('camera') != view['camera']:
                raise ValueError('Missing or changed fixed render camera')
            _image(cv['render'], candidate_base, size)
            objects = _unique(cv.get('objects', []))
            expected_ids = {o['id'] for o in view['objects']}
            if set(objects) - expected_ids:
                raise ValueError('Candidate contains undeclared objects')
            if 'id_image' in cv:
                id_image = np.array(_image(cv['id_image'], candidate_base, size))
                palette = cv['palette']
                colors = [tuple(color) for color in palette.values()]
                if len(set(colors)) != len(colors):
                    raise ValueError('ID palette has duplicate colors')
                for color in colors:
                    if len(color) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in color) or color == (0, 0, 0):
                        raise ValueError('ID palette requires unique nonblack RGB integer colors; background is black')
                observed = {tuple(c) for c in np.unique(id_image.reshape(-1, 3), axis=0).tolist()}
                if observed - set(colors) - {(0, 0, 0)}:
                    raise ValueError('ID image has unregistered or antialiased colors')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            view_errors.append(str(exc))
        for obj_index, obj in enumerate(view['objects']):
            co = objects.get(obj['id'], {})
            row = {'view_id': view['id'], 'role': view['role'], 'object_id': obj['id'],
                   'source': view['source'], 'source_mask': obj.get('mask'),
                   'render': cv.get('render'), 'rendered_mask': co.get('mask', cv.get('id_image')),
                   'camera_sha256': digest(view['camera']),
                   'unscored_palette_entities': sorted(set(cv.get('palette', {})) - {o['id'] for o in view['objects']}),
                   'errors': list(view_errors), 'mask': None, 'landmarks': [], 'overlay': None}
            source_mask, rendered_mask = None, None
            if 'mask' in obj:
                row['mask'] = {'iou': 0., 'boundary_mean_px': diagonal, 'boundary_max_px': diagonal,
                               'source_pixels': None, 'rendered_pixels': None}
                try:
                    source_mask = _image(obj['mask'], protocol_base, size, binary=True)
                    rendered_mask = np.zeros(source_mask.shape, bool)
                    if not source_mask.any():
                        raise ValueError('Empty reference mask is invalid; visibility must be declared before freezing')
                    if 'mask' in co:
                        if id_image is not None:
                            raise ValueError('Use either per-object masks or ID palette, not both')
                        rendered_mask = _image(co['mask'], candidate_base, size, binary=True)
                    elif id_image is not None and obj['id'] in cv['palette']:
                        rendered_mask = np.all(id_image == cv['palette'][obj['id']], axis=-1)
                    else:
                        raise ValueError('Missing rendered mask: ' + obj['id'])
                    row['mask'] = mask_metrics(source_mask, rendered_mask)
                    if not rendered_mask.any():
                        row['errors'].append('Expected visible object is absent from render')
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    row['errors'].append(str(exc))
            try:
                predicted_points = _unique(co.get('landmarks', []))
                if set(predicted_points) - {p['id'] for p in obj.get('landmarks', [])}:
                    raise ValueError('Candidate contains undeclared landmarks')
            except (ValueError, KeyError, TypeError) as exc:
                row['errors'].append(str(exc))
                predicted_points = {}
            for point in obj.get('landmarks', []):
                result = {'id': point['id'], 'source_uv': point['uv'], 'rendered_uv': None,
                          'delta_xy_px': None, 'error_px': diagonal, 'passed': False}
                try:
                    uv = _project(predicted_points[point['id']]['xyz'], view['camera'])
                    error = math.hypot(*(uv-point['uv']))
                    if not math.isfinite(error):
                        raise ValueError('Landmark residual is nonfinite')
                    result.update(rendered_uv=uv.tolist(), delta_xy_px=(uv-point['uv']).tolist(),
                                  error_px=error)
                    result['passed'] = bool(np.all(uv >= 0) and np.all(uv < size) and
                                            result['error_px'] <= limits['maximum_landmark_error_px'])
                except (ValueError, KeyError, TypeError) as exc:
                    row['errors'].append('Landmark ' + point['id'] + ': ' + str(exc))
                row['landmarks'].append(result)
            # Invalid artifact provenance cannot retain a flattering conditional score.
            if row['errors']:
                if row['mask'] is not None:
                    row['mask'].update(iou=0., boundary_mean_px=diagonal, boundary_max_px=diagonal)
                for point in row['landmarks']:
                    point.update(passed=False, error_px=diagonal)
            mask_pass = row['mask'] is None or (row['mask']['iou'] >= limits['minimum_iou'] and
                                               row['mask']['boundary_mean_px'] <= limits['maximum_boundary_mean_px'])
            row['status'] = 'passed' if not row['errors'] and mask_pass and all(p['passed'] for p in row['landmarks']) else 'failed'
            if output and source_image is not None:
                row['overlay'] = _overlay(source_image, source_mask, rendered_mask, row['landmarks'],
                                          output / f'view_{view_index:04d}_object_{obj_index:04d}.png')
            rows.append(row)
    summaries = {role: _summary([r for r in rows if r['role'] == role]) for role in ('fit', 'heldout')}
    return {'schema': 'real2sim.geometry-feedback-report/1.0',
            'status': 'passed' if all(r['status'] == 'passed' for r in rows) else 'failed',
            'protocol_sha256': digest(protocol), 'candidate_sha256': digest(candidate),
            'candidate_model': candidate.get('model'), 'global_errors': errors,
            'thresholds': limits, 'summary': _summary(rows), 'by_role': summaries, 'results': rows,
            'interpretation': 'Fixed-camera 2-D diagnostic only; fit is in-sample. Heldout means declared unused image evidence, not independently verified 3-D or physical accuracy.',
            'limitations': ['Camera/model/render bindings are checked declarations, not proof of a trusted renderer.',
                            'Unobserved geometry, friction, material identity and physical task success are not measured.',
                            'Failure penalties are the image diagonal; no failed object or landmark is dropped.']}
