"""Read-only Blender audit. Run: blender -b --python audit_geometry.py -- CASE OUTPUT.json

CASE contains model.blend, asset_inventory.json and standalone_assets.json.
Evaluated geometry and selection match export_assets.py. No source is saved.
Topology is counted per object, not a union or a collision test. Catalogue
dimensions are constraints, not independent measurements of the photographed item.
"""
import bpy, bmesh, json, sys, math, hashlib
from pathlib import Path

case, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
bpy.ops.wm.open_mainfile(filepath=str(case / 'model.blend'))
inventory = json.loads((case / 'asset_inventory.json').read_text())
previous = json.loads((case / 'standalone_assets.json').read_text())
items = [(x['scene'], x['collection'], None) for x in inventory
         if not x['collection'].startswith(('40 Wall whiteboard', '50 Whiteboard', '60 Utility'))]
items += [('01_bedroom', 'mattress', 'Mattress'), ('01_bedroom', 'duvet', 'Duvet'), ('01_bedroom', 'pillow', 'Pillow')]
results = []
for scene, label, prefix in items:
    sc = bpy.data.scenes[scene]
    bpy.context.window.scene = sc
    frame = 48 if scene == '03_utility' else 1
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    collection = bpy.data.collections[label] if prefix is None else next(c for c in sc.collection.children if c.name.startswith('10 Oak'))
    objects = [o for o in collection.all_objects if o.type in {'MESH', 'CURVE', 'FONT'} and not o.hide_render and (prefix is None or o.name.startswith(prefix))]
    details = []
    for ob in objects:
        ev = ob.evaluated_get(dg)
        mesh = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
        mesh.transform(ev.matrix_world)
        mesh.calc_loop_triangles()
        coords = [list(v.co) for v in mesh.vertices]
        finite = all(math.isfinite(a) for v in coords for a in v)
        lo = [min(v[i] for v in coords) for i in range(3)] if coords else None
        hi = [max(v[i] for v in coords) for i in range(3)] if coords else None
        bm = bmesh.new(); bm.from_mesh(mesh)
        boundary = sum(e.is_boundary for e in bm.edges)
        nonmanifold = sum(not e.is_manifold for e in bm.edges)
        zero = sum(f.calc_area() <= 1e-12 for f in bm.faces)
        exact_zero = sum(f.calc_area() == 0 for f in bm.faces)
        zero_tri = sum(t.area <= 1e-12 for t in mesh.loop_triangles)
        details.append(dict(name=ob.name, source_type=ob.type, vertices=len(coords), faces=len(mesh.polygons),
            triangles=len(mesh.loop_triangles), finite_vertices=finite, zero_area_faces=zero,
            exactly_zero_area_faces=exact_zero, minimum_face_area_m2=min((f.calc_area() for f in bm.faces), default=None),
            zero_area_triangles=zero_tri, boundary_edges=boundary, nonmanifold_edges=nonmanifold,
            closed_topology=bool(len(bm.faces)) and nonmanifold == 0, bounds_m=[lo,hi],
            dimensions_m=[hi[i]-lo[i] for i in range(3)] if lo else None))
        bm.free(); bpy.data.meshes.remove(mesh)
    valid = [x for x in details if x['bounds_m'][0] is not None]
    lo = [min(x['bounds_m'][0][i] for x in valid) for i in range(3)]
    hi = [max(x['bounds_m'][1][i] for x in valid) for i in range(3)]
    size = [hi[i]-lo[i] for i in range(3)]
    extrema = {axis: {'min': [{'object':x['name'],'coordinate_m':x['bounds_m'][0][i]} for x in valid if abs(x['bounds_m'][0][i]-lo[i])<1e-7],
                     'max': [{'object':x['name'],'coordinate_m':x['bounds_m'][1][i]} for x in valid if abs(x['bounds_m'][1][i]-hi[i])<1e-7]} for i,axis in enumerate('xyz')}
    old = next(x for x in previous if x['source_scene'] == scene and x['source_collection'] == label)
    results.append(dict(scene=scene, collection=label, frame=frame, geometry_objects=len(details), bounds_m=[lo,hi], dimensions_m=size,
        previous_export_dimensions_m=old['dimensions_m'], max_dimension_difference_from_previous_m=max(abs(size[i]-old['dimensions_m'][i]) for i in range(3)),
        all_vertices_finite=all(x['finite_vertices'] for x in details), zero_area_faces=sum(x['zero_area_faces'] for x in details),
        zero_area_triangles=sum(x['zero_area_triangles'] for x in details),
        closed_objects=sum(x['closed_topology'] for x in details), open_or_nonmanifold_objects=sum(not x['closed_topology'] for x in details),
        extrema=extrema, objects=details))
comparisons = []
for product, collection_prefix, axes, target in [('VITBERGET','30 Shoe',[1,0,2],[1.05,.4,1.07]),('BRUKSVARA','20 Wardrobe',[0,1,2],[.794,.565,2.01])]:
    row = next(x for x in results if x['collection'].startswith(collection_prefix))
    actual = [row['dimensions_m'][i] for i in axes]
    comparisons.append(dict(product=product, reference_kind='candidate product catalogue; not verified physical identity',
        scope='full closed-pose assembly including protrusions, not isolated cabinet carcass', axes='width depth height', target_m=target,
        actual_m=actual, signed_difference_m=[actual[i]-target[i] for i in range(3)],
        absolute_difference_m=[abs(actual[i]-target[i]) for i in range(3)], relative_absolute_difference_percent=[100*abs(actual[i]-target[i])/target[i] for i in range(3)]))
bed = next(x for x in results if x['collection'].startswith('10 Oak'))
bed_components = [x for x in bed['objects'] if 'rail' in x['name'].lower() or 'bed frame' in x['name'].lower()]
bed_checks = [dict(object=x['name'], target_length_m=2.0, actual_length_m=x['dimensions_m'][1], absolute_difference_m=abs(x['dimensions_m'][1]-2), relative_absolute_difference_percent=50*abs(x['dimensions_m'][1]-2)) for x in bed_components if x['name'].startswith('Bed side rail')]
carcass_checks = []
for row in results:
    for ob in row['objects']:
        if ob['name'].startswith('Shoe cabinet top.') and not ob['name'].startswith('Shoe cabinet top front'):
            carcass_checks.append(dict(object=ob['name'], dimension='depth x', target_m=.4, actual_m=ob['dimensions_m'][0], absolute_difference_m=abs(ob['dimensions_m'][0]-.4)))
        if ob['name'].startswith('Wardrobe carcass side.'):
            carcass_checks.append(dict(object=ob['name'], dimension='depth y', target_m=.565, actual_m=ob['dimensions_m'][1], absolute_difference_m=abs(ob['dimensions_m'][1]-.565)))
unique = {(row['scene'],ob['name']):ob for row in results for ob in row['objects']}
summary = dict(asset_groups=len(results), unique_geometry_objects=len(unique), all_vertices_finite=all(o['finite_vertices'] for o in unique.values()),
    closed_topology_objects=sum(o['closed_topology'] for o in unique.values()), open_or_nonmanifold_objects=sum(not o['closed_topology'] for o in unique.values()),
    faces_at_or_below_area_threshold=sum(o['zero_area_faces'] for o in unique.values()), exactly_zero_area_faces=sum(o['exactly_zero_area_faces'] for o in unique.values()),
    triangles_at_or_below_area_threshold=sum(o['zero_area_triangles'] for o in unique.values()),
    max_difference_from_previous_export_dimensions_m=max(r['max_dimension_difference_from_previous_m'] for r in results))
report = dict(schema_version=1, blender_version=bpy.app.version_string, model_sha256=hashlib.sha256((case/'model.blend').read_bytes()).hexdigest(),
    method='Evaluated world-space geometry; same object selection/frame as static exports. Area threshold 1e-12 square meters. Each object topology assessed independently.',
    limitations=['No real-world ground truth for unmeasured assets; no physical accuracy percentages assigned.',
        'Closed topology does not establish absence of self-intersection, positive volume, inter-object collision or correct dimensions.',
        'Nonmanifold/open meshes can be intentional sheets, garments or construction details; classification requires inspection.',
        'Static asset groups overlap for the full bed and three bedding components; do not sum counts as unique scene objects.'],
    summary=summary, assets=results, catalogue_assembly_comparisons=comparisons, bed_rail_candidates=bed_components,
    bed_length_constraint_checks=bed_checks, cabinet_component_depth_checks=carcass_checks)
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('AUDIT_COMPLETE', len(results), 'assets')
