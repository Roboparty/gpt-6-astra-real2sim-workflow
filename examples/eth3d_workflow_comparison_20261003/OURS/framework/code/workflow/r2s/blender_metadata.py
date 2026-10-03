"""Canonical world AABBs from evaluated visible geometry, including modifiers/instances.

Run update on a new stage copy after every rebuild; render/export must check it.
Never mutates the input Blender file or an earlier attempt's JSON.
"""
import json, math, sys
from pathlib import Path
import bpy

def measure(scene):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ids = {o['id'] for o in scene['objects']}
    bounds = {}
    for inst in deps.object_instances:
        obj = inst.object
        original = obj.original
        if original.hide_render or obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}:
            continue
        owner = original.get('entity_id', original.get('furniture_id', original.name))
        if owner not in ids:
            continue
        mesh = obj.to_mesh()
        try:
            for vertex in mesh.vertices:
                point = inst.matrix_world @ vertex.co
                if not all(math.isfinite(v) for v in point):
                    raise ValueError('Nonfinite evaluated vertex: ' + original.name)
                if owner not in bounds:
                    bounds[owner] = [list(point), list(point)]
                lo, hi = bounds[owner]
                for axis in range(3):
                    lo[axis] = min(lo[axis], point[axis])
                    hi[axis] = max(hi[axis], point[axis])
        finally:
            obj.to_mesh_clear()
    missing = ids - bounds.keys()
    if missing:
        raise ValueError('No evaluated visible geometry for: ' + ', '.join(sorted(missing)))
    return bounds

def synchronize(scene, update=False, tolerance=1e-5):
    rows = []
    bounds = measure(scene)
    for obj in scene['objects']:
        lo, hi = bounds[obj['id']]
        actual = {'position': [(a+b)/2 for a,b in zip(lo,hi)],
                  'dimensions': [b-a for a,b in zip(lo,hi)]}
        if min(actual['dimensions']) <= 0:
            raise ValueError('Empty volume: ' + obj['id'])
        delta = max(abs(a-b) for key in actual for a,b in zip(actual[key],obj[key]))
        rows.append({'entity':obj['id'], 'world_aabb':[lo,hi], 'max_metadata_error_before_m':delta})
        if update:
            obj.update(actual)
        elif delta > tolerance:
            raise ValueError(f"Stale geometry metadata: {obj['id']}, error {delta:.6f} m")
    if update:
        scene['metadata_geometry_convention'] = 'position = world evaluated visible AABB center; dimensions = world AABB spans; includes hardware and bedding; not catalogue dimensions'
    return {'status':'passed', 'evaluated_meshes':True, 'tolerance_m':tolerance, 'updated':update, 'entities':rows}

if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--')+1:]
    path = Path(args[0]); scene = json.loads(path.read_text())
    result = synchronize(scene, update=args[1]=='update')
    if args[1]=='update':
        path.write_text(json.dumps(scene,indent=2))
        synchronize(scene)
    Path(args[2]).write_text(json.dumps(result,indent=2))
