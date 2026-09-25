"""Blender: compare closed V5 cabinets with supplied ArtVIP reference meshes.

blender -b -t 2 --python measure_reference_surfaces.py -- MODEL REF OUTPUT
No files are saved to either input. Distances are model-to-model, not to reality.
"""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

model, reference, output = map(Path, sys.argv[sys.argv.index('--') + 1:])
products = [('VITBERGET', '30 Shoe'), ('BRUKSVARA', '20 Wardrobe')]

def triangles(collection, transform=None):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    result = []
    for obj in collection.all_objects:
        if obj.type not in {'MESH', 'CURVE'} or obj.hide_render or obj.name.startswith('Stored slipper'):
            continue
        ev = obj.evaluated_get(dg)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        matrix = ev.matrix_world if transform is None else transform @ ev.matrix_world
        vertices = np.array([tuple(matrix @ v.co) for v in mesh.vertices])
        result.extend(vertices[list(t.vertices)] for t in mesh.loop_triangles)
        ev.to_mesh_clear()
    tri = np.array(result)
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    tri = tri[area > 1e-12]
    lo, hi = tri.min(axis=(0, 1)), tri.max(axis=(0, 1))
    tri -= np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    return tri

def tree(tri):
    vertices = tri.reshape(-1, 3)
    return BVHTree.FromPolygons([Vector(v) for v in vertices],
                                [(i, i + 1, i + 2) for i in range(0, len(vertices), 3)], all_triangles=True)

def sample(tri, seed, n=20000):
    rng = np.random.default_rng(seed)
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
    chosen = tri[rng.choice(len(tri), n, p=area / area.sum())]
    uv = rng.random((n, 2))
    u, v = np.sqrt(uv[:, 0]), uv[:, 1]
    return (1-u[:, None])*chosen[:, 0] + (u*(1-v))[:, None]*chosen[:, 1] + (u*v)[:, None]*chosen[:, 2]

bpy.ops.wm.open_mainfile(filepath=str(model))
scene = bpy.data.scenes['01_bedroom']
bpy.context.window.scene = scene
scene.frame_set(1)
ours = {}
for product, prefix in products:
    collection = next(c for c in scene.collection.children if c.name.startswith(prefix))
    bpy.context.view_layer.update()
    # V5 has baked room placement into geometry: the assembly empty is identity.
    # Invert the documented +90-degree shoe-cabinet placement, not the empty.
    rotation = Matrix.Rotation(-math.pi/2, 4, 'Z') if product == 'VITBERGET' else Matrix.Identity(4)
    ours[product] = triangles(collection, rotation)

bpy.ops.wm.open_mainfile(filepath=str(reference))
rows = []
for product, _ in products:
    scene = bpy.data.scenes['COMPARE_' + product]
    bpy.context.window.scene = scene
    scene.frame_set(1)
    ref = triangles(bpy.data.collections['ARTVIP_' + product])
    a, b = ours[product], ref
    ta, tb = tree(a), tree(b)
    runs, da, db = [], [], []
    for seed in [91, 192, 293]:
        d1 = np.array([tb.find_nearest(Vector(p))[3] for p in sample(a, seed)]) * 1000
        d2 = np.array([ta.find_nearest(Vector(p))[3] for p in sample(b, seed+1000)]) * 1000
        ds = np.r_[d1, d2]
        runs.append({'seed': seed, 'mean_mm': float(ds.mean()), 'p95_mm': float(np.quantile(ds, .95))})
        da.extend(d1); db.extend(d2)
    da, db = np.array(da), np.array(db)
    ds = np.r_[da, db]
    thresholds = []
    for mm in [1, 5, 10, 20, 50]:
        p, r = float(np.mean(da <= mm)), float(np.mean(db <= mm))
        thresholds.append({'threshold_mm': mm, 'ours_to_ref_fraction': p, 'ref_to_ours_fraction': r,
                           'f_score': 2*p*r/(p+r) if p+r else 0})
    rows.append({'product': product, 'triangles_ours': len(a), 'triangles_reference': len(b),
                 'samples_per_direction': len(da), 'mean_mm': float(ds.mean()),
                 'median_mm': float(np.median(ds)), 'rms_mm': float(np.sqrt(np.mean(ds**2))),
                 'p95_mm': float(np.quantile(ds, .95)), 'p99_mm': float(np.quantile(ds, .99)),
                 'sampled_max_mm': float(ds.max()), 'thresholds': thresholds, 'runs': runs})
report = {'schema': 'real2sim.surface-audit/1', 'date': '2026-09-25',
          'inputs': [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [model, reference]],
          'blender_version': bpy.app.version_string,
          'method': 'Evaluated V5 frame-1 meshes; documented shoe-cabinet room placement inverted by -90 degrees around Z, wardrobe rotation unchanged; metric units, base Z and XY bbox centres aligned; no scale fitting or ICP; shoes excluded; internal surfaces included. Area-weighted sampling in three seeds, nearest point on opposite triangle mesh.',
          'limits': 'Reference-model agreement only. BRUKSVARA reference is brown variant. Sampled maximum is not exact Hausdorff. Seed spread measures sampling variability, not physical uncertainty. References and catalogue dimensions informed modelling, so this is not held-out validation.',
          'assets': rows}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(rows, indent=2))
