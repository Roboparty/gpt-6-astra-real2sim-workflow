"""In-memory Blender negatives against a real source fixture; source never saved.

blender -b -P test_validate_scene_interchange.py -- --source-model SOURCE.blend
    --source-scene SOURCE.json --output NEW_result.json
Use a fixture with declared furniture parts for the removed-part case.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_scene_interchange import capture_scene, compare_snapshots, sha


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-model', type=Path, required=True)
    parser.add_argument('--source-scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists():
        raise ValueError('Preserve previous test output')
    before = {'model': sha(args.source_model), 'scene': sha(args.source_scene)}
    spec = json.loads(args.source_scene.read_text(encoding='utf-8-sig'))
    bpy.ops.wm.open_mainfile(filepath=str(args.source_model.resolve()))
    reference = capture_scene(spec)
    if reference['failures']:
        raise ValueError('Source fixture invalid: ' + repr(reference['failures']))
    identity = reference['camera_identity']
    parts = [part['object'] for assembly in spec.get('structure', {}).get('assemblies', []) for part in assembly['parts']]
    if not parts:
        raise ValueError('Negative fixture must include a declared furniture part')
    rows = []
    for case in ('unchanged', 'fake_camera', 'orphan_mesh', 'removed_part', 'changed_fov'):
        bpy.ops.wm.open_mainfile(filepath=str(args.source_model.resolve()))
        camera = bpy.context.scene.camera
        if case == 'fake_camera':
            name, matrix = camera.name, camera.matrix_world.copy()
            bpy.data.objects.remove(camera, do_unlink=True)
            fake = bpy.data.objects.new(name, None)
            bpy.context.collection.objects.link(fake)
            fake.matrix_world = matrix
        elif case == 'orphan_mesh':
            bpy.ops.mesh.primitive_cube_add(size=.1)
            bpy.context.object.name = 'strict_negative_unowned_mesh'
        elif case == 'removed_part':
            target = bpy.data.objects.get(parts[0])
            if target is None:
                raise ValueError('Source declared part must have its exact object name')
            # Keep canonical geometry/bounds via a different object, then replace
            # the required editable identity with an Empty. Name-only validation
            # would miss this even though all entity AABBs remain unchanged.
            replacement = target.copy()
            replacement.data = target.data.copy()
            replacement.name = 'strict_negative_wrong_part'
            replacement.data.name = 'strict_negative_wrong_part_mesh'
            bpy.context.collection.objects.link(replacement)
            matrix = target.matrix_world.copy()
            bpy.data.objects.remove(target, do_unlink=True)
            fake = bpy.data.objects.new(parts[0], None)
            bpy.context.collection.objects.link(fake)
            fake.matrix_world = matrix
        elif case == 'changed_fov':
            if camera.data.type == 'PERSP':
                camera.data.lens *= 1.5
            else:
                camera.data.ortho_scale *= 1.5
        actual = capture_scene(spec, identity, reference['projection_context']['pixel_aspect'])
        verdict = compare_snapshots(reference, actual)
        expected = 'passed' if case == 'unchanged' else 'failed'
        rows.append({'case': case, 'passed': verdict['status'] == expected, 'observed_status': verdict['status'],
                     'retained_failures': verdict['failures']})
    unchanged = before == {'model': sha(args.source_model), 'scene': sha(args.source_scene)}
    report = {'status': 'passed' if unchanged and all(row['passed'] for row in rows) else 'failed',
              'cases': rows, 'sources_unchanged': unchanged, 'source_hashes': before,
              'scope': 'Real Blender fixture in-memory negative controls; no scene saved, no interchange fidelity claim from these controls alone.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps(report))
    if report['status'] != 'passed':
        raise RuntimeError('Strict interchange negative controls failed')


if __name__ == '__main__':
    main()
