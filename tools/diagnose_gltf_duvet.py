"""Read-only world-space surface/loose-vertex diagnostic inside Blender.

CLI: -- --source-model SOURCE.blend --source-sha256 HASH --gltf MODEL.glb
        --gltf-sha256 HASH --output NEW.json [--object bed_duvet]
No modifier edits, file saves, cleanup or rendering. Area epsilon is 1e-12 m^2.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

AREA_EPSILON_M2 = 1e-12


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def aabb(points):
    return None if not points else [[min(p[i] for p in points) for i in range(3)],
                                    [max(p[i] for p in points) for i in range(3)]]


def modifiers(obj):
    rows = []
    for modifier in obj.modifiers:
        values = {}
        for prop in modifier.bl_rna.properties:
            if prop.identifier == 'rna_type' or prop.type == 'COLLECTION':
                continue
            value = getattr(modifier, prop.identifier)
            if prop.type == 'POINTER':
                value = None if value is None else getattr(value, 'name', str(type(value)))
            elif getattr(prop, 'is_array', False):
                value = list(value)
            elif isinstance(value, set):
                value = sorted(value)
            if isinstance(value, (str, int, float, bool, list)) or value is None:
                values[prop.identifier] = value
        rows.append(values)
    return rows


def mesh_statistics(obj, matrix, mesh):
    mesh.calc_loop_triangles()
    points = [matrix @ vertex.co for vertex in mesh.vertices]
    if any(not math.isfinite(float(v)) for point in points for v in point):
        raise ValueError('Nonfinite world vertex: '+obj.name)
    referenced, surface = set(), set()
    zero_count = 0
    surface_area = 0.
    for triangle in mesh.loop_triangles:
        indices = list(triangle.vertices)
        referenced.update(indices)
        a, b, c = [points[i] for i in indices]
        area = float((b-a).cross(c-a).length)*.5
        if not math.isfinite(area):
            raise ValueError('Nonfinite world triangle area')
        if area > AREA_EPSILON_M2:
            surface.update(indices)
            surface_area += area
        else:
            zero_count += 1
    loose = set(range(len(points))) - referenced
    degenerate_only = referenced - surface
    bounds = aabb(points)
    extremes = []
    if bounds:
        for side in (0, 1):
            for axis in range(3):
                index = (min if side == 0 else max)(range(len(points)), key=lambda i: points[i][axis])
                extremes.append({'axis': axis, 'side': 'min' if side == 0 else 'max', 'vertex_index': index,
                                 'world': list(points[index]), 'referenced_by_any_triangle': index in referenced,
                                 'referenced_by_nonzero_triangle': index in surface})
    return {'object_name': obj.name, 'data_name': mesh.name, 'world_matrix': [list(row) for row in matrix],
            'vertices': len(points), 'edges': len(mesh.edges), 'polygons': len(mesh.polygons),
            'loop_triangles': len(mesh.loop_triangles), 'triangles_at_or_below_epsilon': zero_count,
            'nonzero_world_surface_area_m2': surface_area, 'area_epsilon_m2': AREA_EPSILON_M2,
            'all_vertices_aabb': bounds,
            'triangle_referenced_vertex_count': len(referenced),
            'triangle_referenced_vertices_aabb': aabb([points[i] for i in sorted(referenced)]),
            'nonzero_surface_vertex_count': len(surface),
            'nonzero_surface_vertices_aabb': aabb([points[i] for i in sorted(surface)]),
            'loose_vertex_count': len(loose), 'loose_vertices_aabb': aabb([points[i] for i in sorted(loose)]),
            'degenerate_only_vertex_count': len(degenerate_only),
            'degenerate_only_vertices_aabb': aabb([points[i] for i in sorted(degenerate_only)]),
            'all_vertex_extreme_examples': extremes}


def evaluated(obj, graph):
    evaluated_obj = obj.evaluated_get(graph)
    mesh = evaluated_obj.to_mesh()
    try:
        return mesh_statistics(obj, evaluated_obj.matrix_world, mesh)
    finally:
        evaluated_obj.to_mesh_clear()


def combined_bounds(rows, field):
    points = [point for row in rows if row[field] for point in row[field]]
    return aabb(points)


def max_delta(left, right):
    return None if left is None or right is None else max(abs(a-b) for ra, rb in zip(left, right) for a, b in zip(ra, rb))


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-model', type=Path, required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--gltf', type=Path, required=True)
    parser.add_argument('--gltf-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--object', default='bed_duvet')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.output.exists():
        raise ValueError('Keep previous diagnostic; output must be new')
    expected = {args.source_model.resolve(): args.source_sha256, args.gltf.resolve(): args.gltf_sha256}
    report = {'schema': 'real2sim.gltf-surface-bounds-diagnostic/1', 'status': 'failed',
              'blender': bpy.app.version_string, 'script_sha256': sha(__file__),
              'inputs': [{'path': str(path), 'expected_sha256': digest} for path, digest in expected.items()],
              'area_epsilon_m2': AREA_EPSILON_M2,
              'scope': 'World-coordinate mesh diagnostics only. Nonzero-surface AABB agreement can explain loose/degenerate-vertex loss but does not establish full surface, modifier, normal or material equivalence. No cleanup or source mutation.'}
    try:
        if any(sha(path) != digest for path, digest in expected.items()):
            raise ValueError('Input hash mismatch before inspection')
        bpy.ops.wm.open_mainfile(filepath=str(args.source_model.resolve()))
        obj = bpy.data.objects.get(args.object)
        if obj is None or obj.type != 'MESH':
            raise ValueError('Exact source MESH identity missing: '+args.object)
        bpy.context.view_layer.update()
        report['source_modifiers'] = modifiers(obj)
        report['source_raw_mesh'] = mesh_statistics(obj, obj.matrix_world, obj.data)
        report['source_evaluated_mesh'] = evaluated(obj, bpy.context.evaluated_depsgraph_get())
        report['source_evaluation_context'] = {'frame': bpy.context.scene.frame_current,
            'depsgraph_mode': bpy.context.evaluated_depsgraph_get().mode,
            'note': 'Current evaluated dependency graph, matching strict bounds evaluator; not a render-time displacement bake.'}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(args.gltf.resolve()))
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        direct = [o for o in meshes if args.object in (o.name, o.data.name)]
        if direct:
            candidates = direct; report['import_identity_rule'] = 'exact object or mesh-data name'
        else:
            candidates = []
            for candidate in meshes:
                parent = candidate.parent
                while parent:
                    if parent.name == args.object:
                        candidates.append(candidate); break
                    parent = parent.parent
            report['import_identity_rule'] = 'exact named ancestor; all matching mesh children, no spatial guessing'
        if not candidates:
            raise ValueError('Imported named geometry missing: '+args.object)
        bpy.context.view_layer.update(); graph = bpy.context.evaluated_depsgraph_get()
        rows = [evaluated(candidate, graph) for candidate in candidates]
        report['gltf_meshes'] = rows
        surface_bounds = combined_bounds(rows, 'nonzero_surface_vertices_aabb')
        all_bounds = combined_bounds(rows, 'all_vertices_aabb')
        source = report['source_evaluated_mesh']
        report['comparison'] = {'gltf_all_vertices_aabb': all_bounds, 'gltf_nonzero_surface_vertices_aabb': surface_bounds,
            'source_all_vs_gltf_all_max_delta_m': max_delta(source['all_vertices_aabb'], all_bounds),
            'source_surface_vs_gltf_surface_max_delta_m': max_delta(source['nonzero_surface_vertices_aabb'], surface_bounds),
            'source_all_vs_source_surface_max_delta_m': max_delta(source['all_vertices_aabb'], source['nonzero_surface_vertices_aabb'])}
        report['status'] = 'inspected'
    except Exception as error:
        report['error'] = repr(error)
    report['source_bytes_unchanged'] = all(path.is_file() and sha(path) == digest for path, digest in expected.items())
    if not report['source_bytes_unchanged']:
        report['status'] = 'failed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(json.dumps({'status': report['status'], 'comparison': report.get('comparison'), 'error': report.get('error')}))
    if report['status'] == 'failed':
        raise RuntimeError('Read-only GLTF surface diagnostic failed; evidence retained')


if __name__ == '__main__':
    main()
