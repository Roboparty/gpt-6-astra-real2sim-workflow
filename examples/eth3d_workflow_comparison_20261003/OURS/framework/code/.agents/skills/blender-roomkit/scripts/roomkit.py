"""Small deterministic static-part authoring backend. Run inside Blender."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def validate(spec):
    if spec.get('schema') != 'roomkit/1' or spec.get('units') != 'm':
        raise ValueError('Expected roomkit/1 with metre units')
    if not spec.get('parts'):
        raise ValueError('At least one explicit part required')
    ids = set()
    for p in spec['parts']:
        if not isinstance(p['id'], str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}', p['id']) or '__collision' in p['id'] or p['id'] in ids:
            raise ValueError('Unique nonempty part ids required')
        ids.add(p['id'])
        if not p.get('assembly') or p['kind'] not in ('box', 'cushion', 'folded-sheet', 'ellipsoid'):
            raise ValueError('Unsupported part recipe or missing assembly')
        for key in ('size', 'position', 'rotation'):
            v = p[key]
            if len(v) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in v):
                raise ValueError('Finite three-vectors required')
        if min(p['size']) <= 0 or p.get('prior_status') != 'assumed' or not p.get('prior_source'):
            raise ValueError('Positive dimensions and explicit assumed prior provenance required')
        if p.get('collision') not in ('box', 'none'):
            raise ValueError('Explicit collision policy required')
        color = p.get('color', [0.6, 0.6, 0.6])
        if len(color) != 3 or any(not math.isfinite(x) or not 0 <= x <= 1 for x in color):
            raise ValueError('RGB must be finite within [0,1]')
        for key, default, low, high in [('roughness', .6, 0, 1), ('fold_amplitude', .02, 0, .25)]:
            x = p.get(key, default)
            if not math.isfinite(x) or not low <= x <= high:
                raise ValueError('Invalid ' + key)
    if any(spec.get('dynamics', {}).values()):
        raise ValueError('This static backend does not implement dynamics; use an explicit engine adapter')


def build(spec, output):
    validate(spec)
    import bpy
    from mathutils import Vector
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    visual = bpy.data.collections.new('RoomKitVisual')
    collision = bpy.data.collections.new('RoomKitCollision')
    scene.collection.children.link(visual)
    scene.collection.children.link(collision)

    def move(obj, collection):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)

    def cube(size):
        bpy.ops.mesh.primitive_cube_add(size=1)
        obj = bpy.context.object
        obj.dimensions = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return obj

    records = []
    for p in spec['parts']:
        kind, size = p['kind'], p['size']
        if kind == 'folded-sheet':
            # Static analytic folds, NOT cloth simulation or recovered wrinkles.
            n = 32
            amp = p.get('fold_amplitude', .02)
            verts = [(size[0]*(i/n-.5), size[1]*(j/n-.5),
                      amp*math.sin(i/n*6*math.pi)*math.sin(j/n*3*math.pi))
                     for j in range(n+1) for i in range(n+1)]
            faces = [(j*(n+1)+i, j*(n+1)+i+1, (j+1)*(n+1)+i+1, (j+1)*(n+1)+i)
                     for j in range(n) for i in range(n)]
            mesh = bpy.data.meshes.new(p['id'])
            mesh.from_pydata(verts, [], faces)
            obj = bpy.data.objects.new(p['id'], mesh)
            visual.objects.link(obj)
            mod = obj.modifiers.new('static_thickness', 'SOLIDIFY')
            mod.thickness, mod.offset = size[2], 0
        elif kind == 'ellipsoid':
            bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1)
            obj = bpy.context.object
            obj.dimensions = size
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        else:
            obj = cube(size)
            if kind == 'cushion':
                bevel = obj.modifiers.new('upholstery_rounding', 'BEVEL')
                bevel.width, bevel.segments = min(size)*.3, 4
        obj.name = p['id']
        obj.location, obj.rotation_euler = p['position'], p['rotation']
        move(obj, visual)
        for key in ('assembly', 'prior_status', 'prior_source'):
            obj[key] = p[key]
        obj['part_id'] = p['id']
        mat = bpy.data.materials.new(p['id'] + '_material')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (*p.get('color', [.6]*3), 1)
        bsdf.inputs['Roughness'].default_value = p.get('roughness', .6)
        obj.data.materials.append(mat)
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        corners = [obj.matrix_world @ Vector(v) for v in ev.bound_box]
        lo = [min(v[k] for v in corners) for k in range(3)]
        hi = [max(v[k] for v in corners) for k in range(3)]
        proxy = None
        if p['collision'] == 'box':
            # Conservative world AABB; unsuitable for concavity/openings.
            co = cube([hi[k]-lo[k] for k in range(3)])
            co.name = p['id'] + '__collision'
            co.location = [(lo[k]+hi[k])/2 for k in range(3)]
            co.hide_render, co.display_type = True, 'WIRE'
            co['part_id'], co['proxy_kind'] = p['id'], 'assumed_world_aabb'
            move(co, collision)
            proxy = {'object': co.name, 'min': lo, 'max': hi, 'status': 'assumed'}
        records.append({'id': p['id'], 'assembly': p['assembly'], 'kind': kind,
                        'bounds': {'min': lo, 'max': hi}, 'collision': proxy})
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'scene.blend'))
    receipt = {'schema': 'roomkit-receipt/1', 'blender': bpy.app.version_string,
               'units': 'm', 'parts': records, 'dynamics': False,
               'geometry_accuracy': 'unverified', 'collision_engine_test': 'not_run',
               'model_sha256': hashlib.sha256((output/'scene.blend').read_bytes()).hexdigest()}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    spec = json.loads(args.manifest.read_text(encoding='utf-8'))
    build(spec, args.output)
    receipt_path = args.output/'receipt.json'
    receipt = json.loads(receipt_path.read_text())
    receipt['manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
