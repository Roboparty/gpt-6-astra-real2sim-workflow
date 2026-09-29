"""Independent source-to-export checks inside Blender; never saves input models.

blender -b -P validate_scene_interchange.py -- EXPORT_DIR
    --source-model ORIGINAL.blend --source-scene ORIGINAL.json
Importable capture_scene/compare_snapshots helpers support in-memory negatives.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

GEOMETRY_TYPES = {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}
BOUND_TOLERANCE_M = .002
CAMERA_MATRIX_TOLERANCE = 1e-4
PROJECTION_TOLERANCE = 1e-5


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def ancestry(obj):
    while obj is not None:
        yield obj
        obj = obj.parent


def canonical_owner(obj, ids):
    for current in ancestry(obj):
        declared = {current.get(key) for key in ('entity_id', 'furniture_id', 'userProperties:entity_id')
                    if current.get(key) is not None}
        if declared:
            return next(iter(declared)) if len(declared) == 1 and declared <= ids else None
        if current.name in ids:
            return current.name
    return None


def camera_matches(obj, identity):
    if obj.type != 'CAMERA':
        return False
    for current in ancestry(obj):
        frame = identity.get('frame_id')
        if frame is not None and current.get('frame_id') == frame:
            return True
        if current.name == identity['object_name']:
            return True
    return obj.data.name == identity['data_name']


def capture_scene(spec, identity=None, pixel_aspect=None):
    """Capture evaluated render-visible geometry and an explicitly identified camera.

    Camera projection is compared on the SAME original JSON raster and source
    pixel aspect. GLB/USD do not generally serialize Blender's render resolution.
    No identity is inferred from geometric proximity or object order.
    """
    import bpy
    scene = bpy.context.scene
    ids = {obj['id'] for obj in spec['objects']}
    result = {'failures': [], 'bounds': {}, 'geometry': [], 'camera': None}
    width, height = spec['camera']['image_size']
    if any(type(v) is not int or v <= 0 for v in (width, height)):
        raise ValueError('Positive original source image_size required')
    if pixel_aspect is None:
        pixel_aspect = [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y]
    if any(not math.isfinite(v) or v <= 0 for v in pixel_aspect):
        raise ValueError('Invalid source pixel aspect')
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = pixel_aspect
    result['projection_context'] = {'source_image_size': [width, height], 'pixel_aspect': list(pixel_aspect)}

    # Collection render visibility is additional to each object's hide_render.
    visible_collections = set()
    def visit(collection):
        if collection.hide_render:
            return
        visible_collections.add(collection.as_pointer())
        for child in collection.children:
            visit(child)
    visit(scene.collection)
    def visible(obj):
        return not obj.hide_render and any(c.as_pointer() in visible_collections for c in obj.users_collection)

    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    for instance in graph.object_instances:
        obj = instance.object
        if obj.type not in GEOMETRY_TYPES or obj.original.hide_render:
            continue
        if instance.is_instance:
            if instance.parent is None or not visible(instance.parent.original):
                continue
        elif not visible(obj.original):
            continue
        entity = canonical_owner(obj.original, ids)
        row = {'name': obj.original.name, 'data_name': obj.data.name, 'type': obj.type,
               'owner': entity, 'instance': bool(instance.is_instance)}
        result['geometry'].append(row)
        if entity is None:
            result['failures'].append('Unowned visible geometry: ' + obj.original.name)
        mesh = obj.to_mesh()
        try:
            mesh.calc_loop_triangles()
            row.update(vertices=len(mesh.vertices), triangles=len(mesh.loop_triangles))
            if not mesh.vertices or not mesh.loop_triangles:
                result['failures'].append('Empty/non-surface geometry: ' + obj.original.name)
                continue
            points = [list(instance.matrix_world @ vertex.co) for vertex in mesh.vertices]
            if any(not math.isfinite(value) for point in points for value in point):
                result['failures'].append('Nonfinite geometry: ' + obj.original.name)
                continue
            lo = [min(point[i] for point in points) for i in range(3)]
            hi = [max(point[i] for point in points) for i in range(3)]
            row['world_aabb'] = [lo, hi]
            if entity is not None:
                bounds = result['bounds'].setdefault(entity, [lo[:], hi[:]])
                for i in range(3):
                    bounds[0][i] = min(bounds[0][i], lo[i])
                    bounds[1][i] = max(bounds[1][i], hi[i])
        finally:
            obj.to_mesh_clear()
    missing = sorted(ids - result['bounds'].keys())
    if missing:
        result['failures'].append('Missing canonical geometry: ' + repr(missing))
    required = [(assembly['entity'], part['object']) for assembly in spec.get('structure', {}).get('assemblies', [])
                for part in assembly['parts']]
    result['required_parts'] = [{'owner': owner, 'object': name} for owner, name in required]
    for owner, name in required:
        matches = [row for row in result['geometry'] if row['owner'] == owner and 'world_aabb' in row
                   and name in (row['name'], row['data_name'])]
        if len(matches) != 1:
            result['failures'].append(f'Required visible part missing, wrong-owner or ambiguous: {owner}/{name} ({len(matches)} matches)')

    if identity is None:
        camera = scene.camera
        if camera is None or camera.type != 'CAMERA':
            result['failures'].append('Source scene has no active CAMERA')
            return result
        identity = {'object_name': camera.name, 'data_name': camera.data.name, 'frame_id': camera.get('frame_id')}
    else:
        matches = [obj for obj in scene.objects if camera_matches(obj, identity)]
        if len(matches) != 1:
            result['failures'].append(f'Explicit source CAMERA missing or ambiguous: {len(matches)} matches')
            result['camera_identity'] = identity
            return result
        camera = matches[0]
    result['camera_identity'] = identity
    matrix = [list(row) for row in camera.matrix_world]
    kind = camera.data.type
    if kind not in {'PERSP', 'ORTHO'}:
        result['failures'].append('Unsupported camera projection: ' + kind)
        return result
    frame = camera.data.view_frame(scene=scene)
    projection = []
    for point in frame:
        if kind == 'PERSP':
            if point.z >= 0:
                result['failures'].append('Invalid perspective view frame')
                return result
            projection.append([float(point.x/-point.z), float(point.y/-point.z)])
        else:
            projection.append([float(point.x), float(point.y)])
    if any(not math.isfinite(v) for row in matrix + projection for v in row):
        result['failures'].append('Nonfinite camera matrix or projection')
        return result
    result['camera'] = {'name': camera.name, 'data_name': camera.data.name, 'type': camera.type,
                        'projection_type': kind, 'world_matrix': matrix,
                        'normalized_view_frame_xy': sorted(projection),
                        'clip_start': camera.data.clip_start, 'clip_end': camera.data.clip_end}
    return result


def compare_snapshots(reference, actual):
    failures = ['Source invalid: ' + item for item in reference['failures']] + list(actual['failures'])
    errors = {}
    for entity, bounds in reference['bounds'].items():
        if entity not in actual['bounds']:
            failures.append('Missing source entity: ' + entity)
            continue
        error = max(abs(a-b) for ra, rb in zip(bounds, actual['bounds'][entity]) for a, b in zip(ra, rb))
        errors[entity] = error
        if error > BOUND_TOLERANCE_M:
            failures.append('Source AABB differs by more than 2 mm: ' + entity)
    camera_error = projection_error = None
    a, b = reference['camera'], actual['camera']
    if a is None or b is None:
        failures.append('Cannot compare a valid source CAMERA')
    else:
        camera_error = max(abs(x-y) for ra, rb in zip(a['world_matrix'], b['world_matrix']) for x, y in zip(ra, rb))
        if camera_error > CAMERA_MATRIX_TOLERANCE:
            failures.append('Source camera world matrix changed')
        if a['projection_type'] != b['projection_type']:
            failures.append('Source camera projection type changed')
        projection_error = max(abs(x-y) for ra, rb in zip(a['normalized_view_frame_xy'], b['normalized_view_frame_xy']) for x, y in zip(ra, rb))
        if projection_error > PROJECTION_TOLERANCE:
            failures.append('Source camera normalized view frame changed (FOV/shift)')
    return {'status': 'failed' if failures else 'passed', 'failures': failures,
            'bounds_error_by_entity_m': errors, 'maximum_bound_error_m': max(errors.values(), default=None),
            'source_camera_matrix_max_error': camera_error, 'source_camera_projection_max_error': projection_error,
            'actual': actual}


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export_directory', type=Path)
    parser.add_argument('--source-model', type=Path, required=True)
    parser.add_argument('--source-scene', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    root = args.export_directory.resolve()
    output = root/'strict_reload_validation.json'
    if output.exists():
        raise ValueError('Keep historical result; strict_reload_validation.json already exists')
    sources = {'source_model': args.source_model.resolve(), 'source_scene': args.source_scene.resolve()}
    source_hashes = {key: sha(path) for key, path in sources.items()}
    report = {'schema': 'real2sim.strict-interchange/1', 'status': 'failed', 'records': [],
              'inputs': {key: {'path': str(path), 'sha256': source_hashes[key]} for key, path in sources.items()},
              'evaluator_sha256': sha(__file__), 'blender_version': bpy.app.version_string,
              'thresholds': {'canonical_aabb_m': BOUND_TOLERANCE_M, 'camera_matrix': CAMERA_MATRIX_TOLERANCE,
                             'normalized_view_frame': PROJECTION_TOLERANCE},
              'scope': 'Independent frozen-source comparison; actual three-format loading; render-visible ownership and part identity; canonical AABBs; explicit CAMERA identity, world matrix and normalized view frame on original JSON raster. AABB agreement is not full-surface/topology/collision equivalence. Clip distances are recorded but not acceptance-tested. PBR/procedural material, texture, lighting, real-world accuracy and image fidelity are not validated.'}
    reference = spec = None
    try:
        spec = json.loads(args.source_scene.read_text(encoding='utf-8-sig'))
        bpy.ops.wm.open_mainfile(filepath=str(args.source_model.resolve()))
        reference = capture_scene(spec)
        report['source_snapshot'] = reference
    except Exception as error:
        report['source_error'] = repr(error)
    for extension in ('blend', 'glb', 'usdc'):
        path = root/('scene.'+extension)
        row = {'format': extension, 'path': str(path), 'status': 'failed', 'failures': []}
        report['records'].append(row)
        try:
            row['sha256'] = sha(path)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if extension == 'blend':
                bpy.ops.wm.open_mainfile(filepath=str(path))
            elif extension == 'glb':
                bpy.ops.import_scene.gltf(filepath=str(path))
            else:
                bpy.ops.wm.usd_import(filepath=str(path))
            if reference is None or reference.get('camera_identity') is None:
                raise ValueError('Independent source snapshot is unavailable or lacks a camera identity')
            actual = capture_scene(spec, reference['camera_identity'], reference['projection_context']['pixel_aspect'])
            row.update(compare_snapshots(reference, actual))
            if sha(path) != row['sha256']:
                row['failures'].append('Export bytes changed during reload')
                row['status'] = 'failed'
        except Exception as error:
            row['status'] = 'failed'
            row['failures'].append(repr(error))
    report['sources_unchanged'] = all(path.is_file() and sha(path) == source_hashes[key] for key, path in sources.items())
    report['status'] = 'passed' if report['sources_unchanged'] and all(row['status'] == 'passed' for row in report['records']) else 'failed'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({'status': report['status'], 'formats': [{key: row[key] for key in ('format', 'status', 'failures')} for row in report['records']]}))
    if report['status'] != 'passed':
        raise RuntimeError('Strict interchange failed; all format records retained')


if __name__ == '__main__':
    main()
