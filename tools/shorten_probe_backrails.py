"""Case regression: distinguish the chair back from the overlapping table stretcher.

Fit the rail's visible endpoints in the original photograph. This is a fitting
residual, not independent accuracy. Keep the original curve around both supports
and trim its excessive ends; only the two rail meshes may change.
"""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

source, dest = [Path(x) for x in sys.argv[sys.argv.index('--') + 1:]]
dest.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source / 'model.blend'))
scene = json.loads((source / 'scene.json').read_text())
camera = scene['camera']
assemblies = {a['entity']: a for a in scene['structure']['assemblies']}
parameters = assemblies['chair_near']['fit']['parameters']
targets = [[865, 590], [822, 601]]


def point(p, xx):
    x, y, yaw, w, d, h, bh = p
    original_span = w/2 + .070
    yy = d/2 + .008 - .25*(abs(xx)/original_span)**4
    zz = bh - .014*(abs(xx)/original_span)**2
    return [x+math.cos(yaw)*xx-math.sin(yaw)*yy, y+math.sin(yaw)*xx+math.cos(yaw)*yy, zz]


def project(pt):
    q = [sum(camera['rotation_world_to_cv'][i][j]*(pt[j]-camera['position'][j]) for j in range(3)) for i in range(3)]
    return [q[i]/q[2]*camera['focal_px']+camera['principal_point'][i] for i in range(2)]


def errors(span):
    uv = [project(point(parameters, xx)) for xx in [-span, span]]
    return [math.dist(a,b) for a,b in zip(uv,targets)]


def geometry(o):
    return hashlib.sha256(repr(([list(r) for r in o.matrix_world], [list(v.co) for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])).encode()).hexdigest()


# Bounded 1D fit, with approximately five-pixel endpoint uncertainty.
span = min([.14+i*.0002 for i in range(301)], key=lambda s:sum(e*e for e in errors(s)))
before = {o.name: geometry(o) for o in bpy.context.scene.objects if o.type == 'MESH'}
changed=[]
for entity in ['chair_near','chair_far']:
    p=assemblies[entity]['fit']['parameters'];yaw=p[2];original_span=p[3]/2+.070
    o=bpy.data.objects[entity+'__back_rail'];vertices=[];faces=[];n=40
    for i in range(n+1):
        xx=-span+2*span*i/n
        derivative=-math.copysign(1,xx)*abs(xx)**3/original_span**4 if xx else 0
        normal=Vector((-derivative,1,0)).normalized()
        normal=Vector((math.cos(yaw)*normal.x-math.sin(yaw)*normal.y,math.sin(yaw)*normal.x+math.cos(yaw)*normal.y,0))
        for dn,dz in [(-.010,-.013),(.010,-.013),(.010,.013),(-.010,.013)]:
            vertices.append(list(Vector(point(p,xx))+normal*dn+Vector((0,0,dz))))
    for i in range(n):
        for k in range(4):a=i*4+k;b=i*4+(k+1)%4;faces.append((a,b,b+4,a+4))
    faces.extend([(3,2,1,0),(n*4,n*4+1,n*4+2,n*4+3)])
    mesh=bpy.data.meshes.new(o.name+'_endpoint_fit');mesh.from_pydata(vertices,[],faces);mesh.update()
    for material in o.data.materials:mesh.materials.append(material)
    o.data=mesh;changed.append(o.name)
after={o.name:geometry(o) for o in bpy.context.scene.objects if o.type=='MESH'}
assert set(before)==set(after)
assert {name for name in before if before[name]!=after[name]}==set(changed)
scene['model_version']+=1
(dest/'scene.json').write_text(json.dumps(scene,indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(dest/'model.blend'))
old_span=parameters[3]/2+.070
report={'changed_meshes':changed,'unchanged_mesh_count':len(before)-len(changed),'support_curve_and_layout_preserved':True,
    'half_span_before_m':old_span,'half_span_after_m':span,'endpoint_targets_px':targets,'endpoint_uncertainty_px':5,
    'endpoint_error_before_px':errors(old_span),'endpoint_error_after_px':errors(span),
    'interpretation':'Long overlapping member belongs to table. Rail ends terminate close to rear support posts; far chair shares the same family as an explicit assumption.',
    'scope':'Fitting residual on the input photograph; not independent accuracy or recovered hidden shape. Collision proxies unchanged; no dynamic validation claimed.'}
(dest/'local_edit_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
