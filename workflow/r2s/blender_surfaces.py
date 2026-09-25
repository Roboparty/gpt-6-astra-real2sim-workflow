"""Source-bound surface diagnostics on evaluated geometry, never collision proxies."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def components(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    try:
        points = np.array([ev.matrix_world @ v.co for v in mesh.vertices])
        adjacent = [set() for _ in points]
        for edge in mesh.edges:
            a, b = edge.vertices
            adjacent[a].add(b); adjacent[b].add(a)
        remaining = set(range(len(points))); groups = []
        while remaining:
            pending = [remaining.pop()]; group = []
            while pending:
                i = pending.pop(); group.append(i)
                for j in adjacent[i] & remaining:
                    remaining.remove(j); pending.append(j)
            groups.append(points[group])
        return points, groups
    finally:
        ev.to_mesh_clear()


def clipped_area(subject, clip):
    """Convex triangle intersection, excluding shared edges and empty spans."""
    cross=lambda a,b:float(a[0]*b[1]-a[1]*b[0])
    orientation=1 if cross(clip[1]-clip[0],clip[2]-clip[0])>0 else -1
    polygon=list(subject)
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        previous=polygon;polygon=[]
        if not previous:break
        for p,q in zip(previous,previous[1:]+previous[:1]):
            dp=orientation*cross(b-a,p-a);dq=orientation*cross(b-a,q-a)
            if dp>=-1e-10:polygon.append(p)
            if (dp>0) != (dq>0):polygon.append(p+(q-p)*dp/(dp-dq))
    return abs(sum(cross(a,b) for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2 if len(polygon)>=3 else 0.


def exterior_triangles(objects,basis,plane):
    faces=[]
    for obj in objects:
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        try:
            mesh.calc_loop_triangles();p=np.array([ev.matrix_world@v.co for v in mesh.vertices])@basis.T
            for triangle in mesh.loop_triangles:
                v=p[list(triangle.vertices)]
                if np.max(abs(v[:,2]-plane))<1e-5:
                    faces.append((obj.name,triangle.polygon_index,v[:,:2]))
        finally:ev.to_mesh_clear()
    return faces


def group_component_count(obj,name):
    group=obj.vertex_groups.get(name)
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        selected={v.index for v in mesh.vertices if group and any(g.group==group.index and g.weight>0 for g in v.groups)}
        if len(selected)<4:raise ValueError('Missing/empty geometric feature group')
        adjacent={i:set() for i in selected}
        for edge in mesh.edges:
            a,b=edge.vertices
            if a in selected and b in selected:adjacent[a].add(b);adjacent[b].add(a)
        count=0
        while selected:
            pending=[selected.pop()];count+=1
            while pending:
                for j in adjacent[pending.pop()] & selected:selected.remove(j);pending.append(j)
        return count
    finally:ev.to_mesh_clear()


def audit(out, render=True):
    out = Path(out)
    observed = json.loads((out / 'surface_observation.json').read_text())
    model = json.loads((out / 'surface_realization.json').read_text())
    result = dict(schema='real2sim.surface-audit/1', model_sha256=sha(bpy.data.filepath),
                  observation_sha256=sha(out/'surface_observation.json'),
                  realization_sha256=sha(out/'surface_realization.json'),
                  regions=[], failures=[], images={},
                  limits='Connected-component repetition is a heuristic; continuous carved relief and semantic proportions still require source-first visual review.')
    if model['observation_sha256'] != result['observation_sha256']:
        raise ValueError('Surface observation binding changed')
    sources = {r['id']: r for r in observed['regions']}
    for region in model['regions']:
        source = sources[region['id']]; objects = [bpy.data.objects.get(n) for n in region['inspection_objects']]
        if any(o is None or o.type != 'MESH' or o.hide_render for o in objects):
            raise ValueError('Inspection must bind visible mesh objects')
        normal = Vector(region['normal_world']).normalized(); up = Vector(region['up_world']).normalized()
        if abs(normal.dot(up)) > .001: raise ValueError('Surface basis must be perpendicular')
        right = up.cross(normal).normalized(); basis = np.array([right, up, normal])
        geometry = {o.name: components(o) for o in objects}
        points = np.concatenate([p for p, _ in geometry.values()]); projected = points @ basis.T
        span = np.ptp(projected, axis=0); strips = []
        for name, (_, groups) in geometry.items():
            for p in groups:
                d = np.ptp(p @ basis.T, axis=0)
                if d[0] > span[0]*.20 and 0 < d[1] < span[1]*.02 and d[0]/d[1] > 8 and d[2] < span[0]*.025:
                    strips.append(dict(object=name, dimensions_m=d.tolist(), center_up_m=float((p@basis.T)[:,1].mean())))
        if len(strips) >= 3 and not source['allow_repeated_relief']:
            result['failures'].append(dict(region=region['id'], kind='unsupported_repeated_relief', measured_count=len(strips)))
        coplanar_overlaps=[]
        if source.get('continuous_outer_plane'):
            # A shelf ending on the exterior panel face creates a visible seam/
            # z-fighting even when all parts belong to the same joined object.
            faces=exterior_triangles(objects,basis,float(projected[:,2].max()))
            for i,(name,face,a) in enumerate(faces):
                for other,face2,b in faces[i+1:]:
                    if name==other and face==face2:continue
                    if np.min(np.minimum(a.max(0),b.max(0))-np.maximum(a.min(0),b.min(0)))<=0:continue
                    area=clipped_area(a,b)
                    if area>1e-6:coplanar_overlaps.append(dict(objects=[name,other],overlap_area_m2=area))
            if coplanar_overlaps:
                result['failures'].append(dict(region=region['id'],kind='overlapping_exterior_component_faces',count=len(coplanar_overlaps)))
        feature_rows = []; used_refs = set()
        for feature in region['features']:
            if feature['representation'] != 'geometry': continue
            measured = 0
            for ref in feature['mesh_refs']:
                key = (ref['object'], ref.get('vertex_group'))
                if key in used_refs: raise ValueError('Duplicate surface feature geometry binding')
                used_refs.add(key)
                obj = bpy.data.objects.get(ref['object'])
                if obj not in objects: raise ValueError('Feature is outside inspected objects')
                if ref.get('vertex_group'):
                    measured+=group_component_count(obj,ref['vertex_group'])
                else:
                    measured += 1 if ref.get('whole_surface') else len(geometry[obj.name][1])
            if measured != feature['count']:
                result['failures'].append(dict(region=region['id'], kind='feature_count', feature=feature['id'], expected=feature['count'], measured=measured))
            feature_rows.append(dict(id=feature['id'], measured_count=measured))
        row=dict(id=region['id'], entity=region['entity'], pattern=region['pattern'], source_crop=source['source_crop'],
                 front_view=region['id']+'_front.png', raking_view=region['id']+'_raking.png',
                 thin_horizontal_components=strips, exterior_face_overlaps=coplanar_overlaps,features=feature_rows)
        if render: render_region(out, row, objects, points, normal, up, right)
        result['regions'].append(row)
        for p in [row['source_crop'],row['front_view'],row['raking_view']]:
            if (out/p).exists(): result['images'][p]=sha(out/p)
    result['status']='failed' if result['failures'] else 'passed'
    (out/'surface_audit.json').write_text(json.dumps(result,indent=2))
    return result


def render_region(out, row, objects, points, normal, up, right):
    sc=bpy.context.scene; original_camera=sc.camera; original_world=sc.world
    visibility={o:o.hide_render for o in sc.objects}; material=sc.view_layers[0].material_override
    settings={k:getattr(sc.render,k) for k in ['engine','resolution_x','resolution_y','resolution_percentage','filepath','use_border','use_crop_to_border']}
    samples=sc.cycles.samples; exposure=sc.view_settings.exposure; created=[]; data=[]
    clay=bpy.data.materials.new('surface_inspection_clay');clay.use_nodes=True
    clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.55,.55,.55,1)
    clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
    world=bpy.data.worlds.new('surface_inspection_world');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[1].default_value=.2
    try:
        for o in visibility: o.hide_render=o not in objects
        sc.world=world;sc.view_layers[0].material_override=clay;sc.view_settings.exposure=0
        sc.render.engine='CYCLES';sc.cycles.samples=16;sc.render.resolution_x=600;sc.render.resolution_y=600
        sc.render.resolution_percentage=100;sc.render.use_border=False;sc.render.use_crop_to_border=False
        center=Vector((points.min(axis=0)+points.max(axis=0))/2)
        # The inspected object can be the whole carcass. Place grazing light
        # outside its FRONT plane, not inside its bounding-box centre.
        center+=normal*(float((points@np.array(normal)).max())-center.dot(normal))
        extent=max(np.ptp(points@np.array([right,up]).T,axis=0))*1.18
        camdata=bpy.data.cameras.new('surface_camera');data.append(camdata)
        cam=bpy.data.objects.new('surface_camera',camdata);sc.collection.objects.link(cam);created.append(cam)
        cam.data.type='ORTHO';cam.data.ortho_scale=extent;cam.location=center+normal*max(2,extent*2)
        cam.rotation_euler=Matrix((right,up,normal)).transposed().to_euler();sc.camera=cam
        lightdata=bpy.data.lights.new('surface_light','AREA');data.append(lightdata)
        light=bpy.data.objects.new('surface_light',lightdata);sc.collection.objects.link(light);created.append(light)
        for mode in ['front','raking']:
            light.location=center+(normal*2+up+right) if mode=='front' else center+normal*.18-right*1.5+up*.3
            lightdata.energy=150 if mode=='front' else 70;lightdata.size=2 if mode=='front' else .35
            light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
            sc.render.filepath=str(out/row[mode+'_view']);bpy.ops.render.render(write_still=True)
    finally:
        sc.camera=original_camera;sc.world=original_world;sc.view_layers[0].material_override=material
        sc.cycles.samples=samples;sc.view_settings.exposure=exposure
        for k,v in settings.items():setattr(sc.render,k,v)
        for o,hidden in visibility.items():o.hide_render=hidden
        for o in created:bpy.data.objects.remove(o,do_unlink=True)
        for d in data:
            (bpy.data.cameras if isinstance(d,bpy.types.Camera) else bpy.data.lights).remove(d)
        bpy.data.materials.remove(clay);bpy.data.worlds.remove(world)
