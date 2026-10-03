"""Move structural bindings with the pilot's world-space XY/yaw rigid transform.

This updates annotations only. Blender remains authoritative for object AABBs.
Pixel observations and horizontal support planes stay fixed; old fit/mesh audit
measurements are discarded so a subsequent structural audit must recompute them.
Active dynamics and target collision proxies need a separate supported adapter.
"""
import copy
import math
from .contracts import ContractError


def _vector(value,length,name):
    if not isinstance(value,(list,tuple)) or len(value)!=length or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ContractError('Invalid '+name)
    return value


def update_xy_yaw_annotations(scene,actions):
    """Return a new scene and receipt; never change the supplied initial state."""
    dynamics=scene.get('dynamics',{})
    if not isinstance(dynamics,dict) or dynamics.get('hinges') or dynamics.get('deformables') or set(dynamics)-{'not_applicable','hinges','deformables','test_steps','timestep_s'}:
        raise ContractError('Pose annotation update does not support active or unknown dynamic recipes')
    if scene.get('room',{}).get('collision_proxies'):
        raise ContractError('Pose annotation update does not support explicit room collision proxies')
    result=copy.deepcopy(scene);objects={o['id']:o for o in result['objects']}
    if len(objects)!=len(result['objects']):raise ContractError('Duplicate scene object IDs')
    assemblies=result.get('structure',{}).get('assemblies',[]);seen=set();updates=[]
    for action in actions:
        if set(action)-{'entity','xy_m','yaw_deg','reason'}:raise ContractError('Only XY translation and yaw actions are supported')
        entity=action['entity']
        if entity in seen or entity not in objects:raise ContractError('Duplicate or unknown pose target')
        seen.add(entity);obj=objects[entity]
        if obj.get('collision_proxies') or obj.get('parameters',{}).get('collision_proxies'):
            raise ContractError('Pose annotation update does not support target collision proxies: '+entity)
        matches=[a for a in assemblies if a['entity']==entity]
        if len(matches)!=1:raise ContractError('Pose target needs exactly one declared assembly: '+entity)
        assembly=matches[0];center=_vector(obj['position'],3,'pivot position')
        dx,dy=_vector(action['xy_m'],2,'XY translation');angle=math.radians(_vector([action['yaw_deg']],1,'yaw')[0])
        c,s=math.cos(angle),math.sin(angle)
        def transform(point):
            x,y,z=_vector(point,3,'world-space annotation')
            return [center[0]+c*(x-center[0])-s*(y-center[1])+dx,
                    center[1]+s*(x-center[0])+c*(y-center[1])+dy,z]
        frame=assembly['frame']
        if set(frame)-{'position','yaw_rad'}:raise ContractError('Unsupported assembly frame representation')
        frame['yaw_rad']=_vector([frame['yaw_rad']],1,'frame yaw')[0]+angle
        if 'position' in frame:frame['position']=transform(frame['position'])
        joints=assembly['joints'];landmarks=assembly['fit']['landmarks']
        for joint in joints:joint['anchor_world']=transform(joint['anchor_world'])
        for landmark in landmarks:
            landmark['world']=transform(landmark['world'])
            # UV/sigma/visibility are observations. Projection and closest-mesh
            # values are old measured results and cannot be carried as new ones.
            for field in ('projected','error_px','measured_world_point','distance_to_bound_mesh_m'):
                landmark.pop(field,None)
        for field in ('median_error_px','max_error_px'):assembly['fit'].pop(field,None)
        updates.append(dict(entity=entity,pivot_world=list(center),translation_world=[dx,dy,0],
                            yaw_rad=angle,joint_anchors_updated=len(joints),landmarks_updated=len(landmarks)))
    return result,dict(status='updated',entities=updates,observed_uv_unchanged=True,
                       tolerances_and_support_planes_unchanged=True,
                       derived_measurements='invalidated; require a new bound structural audit',
                       scope='XY/yaw binding update only, not visual or physical acceptance')
