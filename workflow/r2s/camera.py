"""Calibrated pinhole cameras in metres, Z-up world and OpenCV optical axes."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np


def focal_xy(camera):
    return np.array([camera['focal_px'], camera.get('focal_y_px', camera['focal_px'])], float)


def principal_for_raster(camera):
    """Blender/MuJoCo use raster boundaries; OpenCV labels pixel centres by integers."""
    return np.asarray(camera['principal_point'],float)+(.5 if camera.get('pixel_coordinates')=='integer_centers' else 0.)


def validate_camera(camera):
    if camera.get('pixel_coordinates') not in {None,'integer_centers'}:
        raise ValueError('Unknown camera pixel-coordinate convention')
    size = camera['image_size']
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError('Camera image_size must contain positive integers')
    for key, shape in [('position', (3,)), ('rotation_world_to_cv', (3, 3)), ('principal_point', (2,))]:
        value = np.asarray(camera[key], float)
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError('Invalid camera ' + key)
    rotation = np.asarray(camera['rotation_world_to_cv'], float)
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-6, rtol=0) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-6, rtol=0):
        raise ValueError('Camera rotation must be proper orthonormal')
    focal = focal_xy(camera)
    if not np.isfinite(focal).all() or np.any(focal <= 0):
        raise ValueError('Camera focal lengths must be finite and positive')


def load_observations(config, sources):
    """Read only the hash-pinned reconstruction camera manifest; never evaluator inputs."""
    reference = config.get('camera_observations')
    if reference is None:
        return None
    path = Path(reference['path'])
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != reference['sha256']:
        raise ValueError('Camera observation manifest hash mismatch')
    data = json.loads(raw)
    expected = dict(schema='real2sim.camera-observations/1', units='m', up_axis='Z',
                    camera_frame='opencv', pixel_coordinates='integer_centers')
    if any(data.get(key) != value for key, value in expected.items()) or not data.get('frames'):
        raise ValueError('Camera manifest must declare metres, Z-up, OpenCV axes and integer pixel centres')
    result = []; keys = set(); ids = set()
    for entry in data['frames']:
        index = entry['input_index']
        if type(index) is not int or not 0 <= index < len(sources):
            raise ValueError('Camera input_index is outside the reconstruction allowlist')
        source = sources[index]
        if entry.get('role') != 'reconstruction' or entry['source_sha256'] != source['sha256']:
            raise ValueError('Camera is not bound to an allowed reconstruction input')
        if entry['image_size'] != source['image_size']:
            raise ValueError('Calibration resolution differs from decoded input (including EXIF orientation)')
        frame = entry.get('source_frame')
        if config['mode'] == 'video':
            if type(frame) is not int or frame < 0:
                raise ValueError('Video camera needs an exact nonnegative source_frame')
        elif frame is not None:
            raise ValueError('Still-image cameras must not declare a video frame')
        key = (index, frame)
        frame_id = entry['frame_id']
        if key in keys or not isinstance(frame_id, str) or not frame_id or frame_id in ids:
            raise ValueError('Duplicate camera source or frame_id')
        keys.add(key); ids.add(frame_id)
        if entry.get('pose_source') not in {'measured', 'estimated', 'ground_truth'} or not entry.get('evidence'):
            raise ValueError('Camera needs pose_source and provenance evidence')
        if entry['pose_source'] == 'ground_truth' and reference.get('allow_ground_truth_pose') is not True:
            raise ValueError('GT poses require an explicit diagnostic allow_ground_truth_pose opt-in')
        if entry.get('distortion_model') != 'none':
            raise ValueError('Only undistorted pinhole images are supported; rectify images and K first')
        K = np.asarray(entry['K'], float); T = np.asarray(entry['T_world_camera'], float)
        if K.shape != (3, 3) or not np.isfinite(K).all() or not np.allclose(K[[0, 1, 2, 2, 2], [1, 0, 0, 1, 2]], [0, 0, 0, 0, 1], atol=1e-9, rtol=0):
            raise ValueError('Expected zero-skew pixel K with homogeneous last row')
        if T.shape != (4, 4) or not np.isfinite(T).all() or not np.allclose(T[3], [0, 0, 0, 1], atol=1e-9, rtol=0):
            raise ValueError('Expected homogeneous camera-to-world transform')
        camera = dict(frame_id=frame_id, role='reconstruction', position=T[:3, 3].tolist(),
                      rotation_world_to_cv=T[:3, :3].T.tolist(), focal_px=float(K[0, 0]),
                      focal_y_px=float(K[1, 1]), principal_point=K[:2, 2].tolist(),
                      image_size=entry['image_size'], pose_source=entry['pose_source'], evidence=entry['evidence'],
                      input_index=index, source_sha256=source['sha256'], source_frame=frame,pixel_coordinates='integer_centers')
        validate_camera(camera); result.append(camera)
    if config['mode'] != 'video' and {x['input_index'] for x in result} != set(range(len(sources))):
        raise ValueError('Calibrated still-image inputs require one camera per image')
    return dict(manifest_sha256=sha, cameras=result, locked=True,
                scope='GT-pose diagnostic' if any(c['pose_source'] == 'ground_truth' for c in result) else 'supplied camera constraints')


def resize_camera(camera, size):
    result = copy.deepcopy(camera)
    scale = np.asarray(size, float) / camera['image_size']
    result['focal_px'], result['focal_y_px'] = (focal_xy(camera) * scale).tolist()
    # OpenCV resize maps pixel centres as (u + 0.5) * scale - 0.5.
    result['principal_point'] = ((np.asarray(camera['principal_point']) + .5) * scale - .5).tolist()
    result['image_size'] = list(size)
    validate_camera(result)
    return result


def workflow_constraints(workflow):
    if not workflow.config.get('camera_observations'):
        return None
    for artifact in workflow.state['stages'].get('preprocess', {}).get('outputs', []):
        if Path(artifact['path']).name == 'preprocess.json':
            data = json.loads(Path(artifact['path']).read_text())
            from .contracts import digest
            cameras = [frame['camera'] for frame in data['accepted']]
            return dict(cameras=cameras, sha256=digest(cameras), locked=True,
                        scope=data['camera_observations']['scope'])
    return None


def check_scene_cameras(scene, constraints):
    if not constraints:
        return
    expected = constraints['cameras']; actual = scene.get('cameras') or [scene['camera']]
    if len(actual) != len(expected):
        raise ValueError('Scene must retain every accepted supplied camera')
    for found, wanted in zip([scene['camera']] + actual, [expected[0]] + expected):
        validate_camera(found)
        if found.get('frame_id') != wanted['frame_id'] or found.get('pixel_coordinates')!=wanted.get('pixel_coordinates'):
            raise ValueError('Supplied camera order/identity changed')
        for key in ['position', 'rotation_world_to_cv', 'principal_point', 'image_size']:
            if not np.allclose(found[key], wanted[key], atol=1e-8, rtol=0):
                raise ValueError('Locked camera changed: ' + key)
        if not np.allclose(focal_xy(found), focal_xy(wanted), atol=1e-8, rtol=0):
            raise ValueError('Locked camera focal lengths changed')
