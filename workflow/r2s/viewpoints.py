"""Diagnostic cameras avoid furniture; they never modify reconstructed layout."""
import math
from mathutils import Vector

def inspection_targets(scene):
    shell={'floor','ceiling','wall_front','wall_back','wall_left','wall_right'}
    return [o for o in scene['objects'] if o['id'] not in shell
            and o['kind'] not in {'framed_art','rug','petal_pendant','tulip_lamp','lamp','room_surface'}
            and o.get('semantic_class')!='luminaire']

def diagnostic_focus(scene):
    objects=inspection_targets(scene)
    r=scene['room']
    if not objects:return Vector(((r['x_min']+r['x_max'])/2,(r['y_min']+r['y_max'])/2,r['height']*.35))
    return Vector((sum(o['position'][0] for o in objects)/len(objects),sum(o['position'][1] for o in objects)/len(objects),min(1.0,r['height']*.36)))

def safe_camera_position(scene,ideal):
    import bpy
    r=scene['room'];xm,xM,ym,yM=[r[k] for k in ['x_min','x_max','y_min','y_max']];dx=xM-xm;dy=yM-ym;z=ideal[2]
    targets=inspection_targets(scene);deps=bpy.context.evaluated_depsgraph_get()
    def clear(p):
        if not(xm+.05<p[0]<xM-.05 and ym+.05<p[1]<yM-.05):return False
        for o in targets:
            cx,cy,cz=o['position'];W,D,H=o['dimensions']
            if p[2]<cz-.12 or p[2]>cz+H+.12:continue
            t=o.get('rotation_z',0);xx=(p[0]-cx)*math.cos(t)+(p[1]-cy)*math.sin(t);yy=-(p[0]-cx)*math.sin(t)+(p[1]-cy)*math.cos(t)
            if abs(xx)<W/2+.18 and abs(yy)<D/2+.18:return False
        # A camera can be outside geometry yet be pressed against the back of a shelf.
        # Require unobstructed sightlines to a meaningful fraction of semantic objects.
        seen=0;origin=Vector(p)
        for o in targets:
            target=Vector(o['position'])+Vector((0,0,o['dimensions'][2]*.6));d=target-origin;distance=d.length
            if distance<.6:continue
            hit,point,normal,index,obj,matrix=bpy.context.scene.ray_cast(deps,origin,d.normalized(),distance=distance+.05)
            if not hit or (obj.get('entity_id')==o['id'] and (point-origin).length>.6):seen+=1
        return seen>=max(1,(len(targets)+1)//2) if targets else True
    candidates=[tuple(ideal)]+[(xm+dx*i/12,ym+dy*j/12,z) for i in range(1,12) for j in range(1,12)]
    candidates.sort(key=lambda p:(p[0]-ideal[0])**2+(p[1]-ideal[1])**2)
    for p in candidates:
        if clear(p):return p
    raise ValueError('No free diagnostic camera position; Agent must supply reviewed viewpoints')
