"""Photo-guided local edit for the regression case; not a generic furniture generator.

Replace only the two flat solidified seat pads with shallow rounded upholstery.
Preserve their footprint, support height, ownership, material and all other meshes.
"""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

source, dest, *reference = [Path(x) for x in sys.argv[sys.argv.index('--') + 1:]]
dest.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source / 'model.blend'))


def geometry(o):
    return hashlib.sha256(repr(([list(r) for r in o.matrix_world], [list(v.co) for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])).encode()).hexdigest()


before = {o.name: geometry(o) for o in bpy.context.scene.objects if o.type == 'MESH'}
reference_pads={}
if reference:
    with bpy.data.libraries.load(str(reference[0]/'model.blend'),link=False) as (available,loaded):
        loaded.objects=[name for name in available.objects if name in {'chair_near__pad','chair_far__pad'}]
    reference_pads={o.get('furniture_id'):o for o in loaded.objects}
changed = []
for o in list(bpy.context.scene.objects):
    if o.get('furniture_id') not in {'chair_near', 'chair_far'} or o.get('part_id') != 'pad':
        continue
    original=reference_pads.get(o.get('furniture_id'),o)
    if len(original.data.vertices) != 4:
        raise ValueError('Probe expects the original flat four-vertex seat, not an already modified candidate')
    q = [v.co.copy() for v in original.data.vertices]
    center = sum(q, Vector()) / 4
    u = q[1] - q[0]; v = q[3] - q[0]
    width, depth = u.length, v.length
    u.normalize(); v.normalize()
    z = Vector((0, 0, 1))
    radius = min(.008, width / 8, depth / 8)
    ring = []
    for cx, cy, start in [(width/2-radius, depth/2-radius, 0), (-width/2+radius, depth/2-radius, 90), (-width/2+radius, -depth/2+radius, 180), (width/2-radius, -depth/2+radius, 270)]:
        for i in range(9):
            angle = math.radians(start + i * 90 / 8)
            ring.append((cx + radius*math.cos(angle), cy + radius*math.sin(angle)))
    n = len(ring); verts = []; faces = []
    for scale, height in [(.98, -.030), (1, -.024), (1, -.004), (.99, -.003), (.85, -.001), (.55, 0)]:
        verts.extend([list(center + u*x*scale + v*y*scale + z*height) for x, y in ring])
    # Ring winding in this local frame may be reversed; recalculate normals below.
    for j in range(5):
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n; faces.append((a,b,b+n,a+n))
    faces.append(tuple(reversed(range(n))))
    verts.append(list(center)); top=len(verts)-1
    for i in range(n):faces.append((5*n+i,5*n+(i+1)%n,top))
    mesh=bpy.data.meshes.new(o.name+'_upholstery');mesh.from_pydata(verts,[],faces);mesh.update()
    for material in o.data.materials:mesh.materials.append(material)
    o.data=mesh;o.modifiers.clear()
    bpy.context.view_layer.objects.active=o;o.select_set(True)
    # Data-space construction preserves world transform and support height.
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
    for face in mesh.polygons:face.use_smooth=True
    o.select_set(False);changed.append(o.name)
for obj in reference_pads.values():bpy.data.objects.remove(obj,do_unlink=True)
after={o.name:geometry(o) for o in bpy.context.scene.objects if o.type=='MESH'}
assert set(before)==set(after)
assert {name for name in before if before[name]!=after[name]}==set(changed)
assert len(changed)==2
scene=json.loads((source/'scene.json').read_text());scene['model_version']+=1
(dest/'scene.json').write_text(json.dumps(scene,indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(dest/'model.blend'))
(dest/'local_edit_audit.json').write_text(json.dumps({'changed_meshes':changed,'unchanged_mesh_count':len(before)-len(changed),'layout_transforms_preserved':True,'support_height_preserved':True,'new_geometry':'Rounded perimeter and shallow convex upholstery; hidden padding shape is a labelled plausible hypothesis','scope':'Local visual edit; collision proxies unchanged, no dynamic validation claimed'},indent=2))
