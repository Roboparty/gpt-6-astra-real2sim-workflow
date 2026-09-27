"""Blender read-only surface evaluation of the retained 2026-09-26 candidate.

Usage: blender -b -t 2 --python measure_artvip.py -- MODEL REF_ROOT OUTPUT_DIR
Matches the published area-weighted, bidirectional point-to-triangle protocol.
Does not import prior reconstruction scenes or save any input scene.
"""
import bpy
import datetime
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

model, refroot, out = map(Path, sys.argv[sys.argv.index('--') + 1:])
out.mkdir(parents=True, exist_ok=True)
assert not (out/'surface_metrics.json').exists(), 'Preserve previous evaluation attempts'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected_model = 'e140b8ae0f133a87cbaa77e576ea164512e57c3bd9a56552841f8596b9126e51'
assert sha(model) == expected_model, 'Candidate changed since convergence evaluation'
products = {'VITBERGET': 'shoe_cabinet', 'BRUKSVARA': 'wardrobe'}
expected_refs = {
    'VITBERGET': 'e9f1f0739cd0f0ec3f072cfbe04d72d2eb266a85ab9af76d867ad44d26f2803f',
    'BRUKSVARA': 'b39147e0ed82e38b107e415247fee991a1002990464ec16aefcdd1ef434c27ed',
}
refs = {}
for product in products:
    matches = list(refroot.rglob('model_'+product+'*.usd'))
    assert len(matches) == 1
    refs[product] = matches[0]
    assert sha(matches[0]) == expected_refs[product]
protocol = dict(
    candidate_sha256=expected_model, reference_sha256=expected_refs,
    started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    seeds=[91, 192, 293], samples_per_seed_per_direction=20000,
    thresholds_mm=[1, 5, 10, 20, 50, 100],
    alignment='Preserve metric scale; shoe known front +X rotated -90 degrees to front -Y; wardrobe unchanged; independently align bottom Z and XY envelope centers. No ICP, scaling or optimized registration.',
    scope='Existing closed cabinet surfaces including interiors/hardware; stored footwear excluded by declared structural part identities. Missing interiors remain missing and contribute reference-to-candidate distance.',
    no_model_edits=True,
)
(out/'protocol.json').write_text(json.dumps(protocol, indent=2))


def extract(objects, rotation):
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    parts, tris, removed = [], [], 0
    for obj in objects:
        if obj.type not in {'MESH', 'CURVE'} or obj.hide_render:
            continue
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        matrix = rotation @ ev.matrix_world
        vertices = np.array([matrix @ v.co for v in mesh.vertices])
        tris.extend(vertices[list(t.vertices)] for t in mesh.loop_triangles)
        parts.append(obj.name)
        ev.to_mesh_clear()
    tri = np.array(tris)
    assert len(tri) and np.isfinite(tri).all()
    areas = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)/2
    removed = int(np.count_nonzero(areas <= 1e-12))
    tri = tri[areas > 1e-12]
    lo, hi = tri.min((0, 1)), tri.max((0, 1))
    offset = np.array([(lo[0]+hi[0])/2, (lo[1]+hi[1])/2, lo[2]])
    return tri-offset, dict(dimensions_m=(hi-lo).tolist(), normalization_translation_m=(-offset).tolist(),
                           triangles=len(tri), degenerate_triangles_excluded=removed, objects=parts)


def tree(tri):
    return BVHTree.FromPolygons([Vector(p) for p in tri.reshape(-1, 3)],
                               [(i, i+1, i+2) for i in range(0, len(tri)*3, 3)], all_triangles=True)


def sample(tri, seed):
    rng = np.random.default_rng(seed)
    area = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)/2
    chosen = tri[rng.choice(len(tri), 20000, p=area/area.sum())]
    uv = rng.random((len(chosen), 2))
    u, v = np.sqrt(uv[:, 0]), uv[:, 1]
    return (1-u[:, None])*chosen[:, 0]+(u*(1-v))[:, None]*chosen[:, 1]+(u*v)[:, None]*chosen[:, 2]


bpy.ops.wm.open_mainfile(filepath=str(model))
bpy.context.scene.frame_set(1)
assert bpy.context.scene.unit_settings.scale_length == 1.0
spec = json.loads(model.with_name('scene.json').read_text())
shoe_assembly = next(a for a in spec['structure']['assemblies'] if a['entity'] == 'shoe_cabinet')
excluded = {p['object'] for p in shoe_assembly['parts'] if p['id'].startswith('footwear_')}
assert len(excluded) == 8, 'Verify explicit footwear exclusion, not a broad object-name guess'
ours, reference, metadata = {}, {}, {}
for product, entity in products.items():
    objects = [o for o in bpy.context.scene.objects if o.get('entity_id') == entity and o.name not in excluded]
    rotation = Matrix.Rotation(-math.pi/2, 4, 'Z') if entity == 'shoe_cabinet' else Matrix.Identity(4)
    ours[product], metadata[product+'_candidate'] = extract(objects, rotation)
for product, path in refs.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.usd_import(filepath=str(path), import_cameras=False, import_lights=False,
                         import_proxy=False, import_guide=False, merge_parent_xform=False)
    bpy.context.scene.frame_set(1)
    reference[product], metadata[product+'_reference'] = extract(bpy.context.scene.objects, Matrix.Identity(4))

rows, arrays = [], {}
for product in products:
    a, b = ours[product], reference[product]
    ta, tb = tree(a), tree(b)
    da, db, runs = [], [], []
    for seed in protocol['seeds']:
        x = np.array([tb.find_nearest(Vector(p))[3]*1000 for p in sample(a, seed)])
        y = np.array([ta.find_nearest(Vector(p))[3]*1000 for p in sample(b, seed+1000)])
        d = np.r_[x, y]
        runs.append(dict(seed=seed, mean_mm=float(d.mean()), p95_mm=float(np.quantile(d, .95))))
        da.extend(x)
        db.extend(y)
    da, db = np.array(da), np.array(db)
    d = np.r_[da, db]
    assert len(da) == len(db) == 60000 and np.isfinite(d).all() and (d >= 0).all()
    arrays[product+'_ours_to_ref_mm'], arrays[product+'_ref_to_ours_mm'] = da, db
    scores = []
    for mm in protocol['thresholds_mm']:
        p, r = float(np.mean(da <= mm)), float(np.mean(db <= mm))
        scores.append(dict(threshold_mm=mm, ours_to_ref_fraction=p, ref_to_ours_fraction=r,
                           ours_to_ref_count=int(np.count_nonzero(da <= mm)), ref_to_ours_count=int(np.count_nonzero(db <= mm)),
                           f_score=2*p*r/(p+r) if p+r else 0))
    dims = np.array(metadata[product+'_candidate']['dimensions_m'])
    rdims = np.array(metadata[product+'_reference']['dimensions_m'])
    rows.append(dict(product=product, entity=products[product], samples_per_direction=60000,
                     mean_mm=float(d.mean()), median_mm=float(np.median(d)), rms_mm=float(np.sqrt(np.mean(d*d))),
                     p95_mm=float(np.quantile(d, .95)), p99_mm=float(np.quantile(d, .99)), sampled_max_mm=float(d.max()),
                     thresholds=scores, runs=runs, dimensions_m=dims.tolist(), reference_dimensions_m=rdims.tolist(),
                     dimension_difference_mm=((dims-rdims)*1000).tolist(), relative_dimension_error_percent=((dims-rdims)/rdims*100).tolist()))
np.savez_compressed(out/'surface_distances.npz', **arrays)
assert sha(model) == expected_model
assert all(sha(refs[p]) == expected_refs[p] for p in refs)
report = dict(schema='real2sim.independent-artvip-surface-evaluation/1', status='complete', protocol=protocol,
              inputs_unchanged=True, candidate_file=model.name, references=[dict(product=p, file=str(refs[p].relative_to(refroot)), sha256=expected_refs[p]) for p in refs],
              blender_version=bpy.app.version_string, numpy_version=np.__version__, script_sha256=sha(__file__),
              distance_archive_sha256=sha(out/'surface_distances.npz'), excluded_footwear=sorted(excluded), extraction=metadata, assets=rows,
              limitations=['Reference-model agreement, not measured physical-world error or whole-room accuracy.',
                           'Candidate fixed before this reference evaluation; reference results were not used to revise it. Not a filesystem-isolated third-party blind test.',
                           'Shoe cabinet was unidentified during reconstruction; VITBERGET is evaluated now as the same conditional reference used in the published GitHub benchmark.',
                           'BRUKSVARA reference is the brown variant; finish/material differences are ignored.',
                           'Sampled maximum is not exact Hausdorff; seed range is sampling variability, not real-world uncertainty.',
                           'No hinge/slide geometry accuracy score: current candidate has no reconstructed dynamic joint model.'])
(out/'surface_metrics.json').write_text(json.dumps(report, indent=2))
print(json.dumps(rows, indent=2))
print('SURFACE_EVALUATION_COMPLETE_INPUTS_UNCHANGED')
