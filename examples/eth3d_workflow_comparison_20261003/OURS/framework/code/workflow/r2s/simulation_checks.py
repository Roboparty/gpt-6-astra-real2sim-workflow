"""Check enclosing collision surfaces without confusing foreground trim with walls."""
import numpy as np
import mujoco
if __package__:
    from .shell_collision import room_openings,shell_boxes
else:
    from shell_collision import room_openings,shell_boxes


def check_enclosure_rays(model, data, room, probe_xy):
    xm,xM,ym,yM,h=[room[k] for k in ('x_min','x_max','y_min','y_max','height')]
    mx,my=(xm+xM)/2,(ym+yM)/2
    group=np.array([0,0,1,0,0,0],np.uint8);hit_id=np.zeros(1,np.int32)
    specs={
        'left':('wall_left',[-1,0,0],.05,[[xm+.05,my,h-.04]]+[[xm+.05,y,z] for z in [h-.04,h*.8,h*.5] for y in np.linspace(ym+.12,yM-.12,9)]),
        'right':('wall_right',[1,0,0],.05,[[xM-.05,my,h-.04]]+[[xM-.05,y,z] for z in [h-.04,h*.8,h*.5] for y in np.linspace(ym+.12,yM-.12,9)]),
        'back':('wall_back',[0,1,0],.05,[[mx,yM-.05,h-.04]]+[[x,yM-.05,z] for z in [h-.04,h*.8,h*.5] for x in np.linspace(xm+.12,xM-.12,9)]),
        'front':('wall_front',[0,-1,0],.05,[[mx,ym+.05,h-.04]]+[[x,ym+.05,z] for z in [h-.04,h*.8,h*.5] for x in np.linspace(xm+.12,xM-.12,9)]),
        'ceiling':('ceiling',[0,0,1],.04,[[*probe_xy,h-.04]]),
        'floor':('floor',[0,0,-1],h*.5,[[*probe_xy,h*.5]])}
    result={}
    openings=room_openings(room)
    for name,(expected_body,direction,expected,origins) in specs.items():
        rejected=[]
        if any(o['wall']==expected_body for o in openings):
            # Narrow lintels/sills can fall between the regular grid samples.
            for proxy in shell_boxes(room,expected_body):
                origin=list(proxy['position'])
                # Only tangential coordinates come from the proxy. Deriving the
                # normal coordinate from it would move the test with a bad wall.
                axis,boundary={'wall_left':(0,xm),'wall_right':(0,xM),
                               'wall_front':(1,ym),'wall_back':(1,yM)}[expected_body]
                origin[axis]=boundary-direction[axis]*.05
                origins.append(origin)
        for origin in origins:
            u=origin[0] if expected_body in ('wall_back','wall_front') else origin[1]
            if any(o['wall']==expected_body and o['bounds'][0]<u<o['bounds'][1] and
                   o['bounds'][2]<origin[2]<o['bounds'][3] for o in openings):
                continue
            distance=mujoco.mj_ray(model,data,np.asarray(origin,float),np.asarray(direction,float),group,True,-1,hit_id)
            body=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,int(model.geom_bodyid[hit_id[0]])) if hit_id[0]>=0 else None
            error=abs(distance-expected)
            if body==expected_body and error<.006:
                result[name]=dict(origin_m=list(map(float,origin)),hit_body=body,distance_m=float(distance),expected_m=expected,error_m=float(error),rejected_candidate_count=len(rejected),occluded_examples=rejected[:3]);break
            rejected.append(dict(origin_m=list(map(float,origin)),hit_body=body,distance_m=float(distance)))
        else:
            raise ValueError('No unobstructed valid '+expected_body+' collision-surface ray; candidates: '+str(rejected[:3]))
    return result


def check_opening_rays(model, data, room):
    """Wall-only rays reject filled apertures while allowing separate glazing.

    Nine samples cover each declared opening. This is a collision export check,
    not a proof of complete visual mesh topology or real-world passability.
    """
    results=[]
    directions={'wall_left':[-1,0,0],'wall_right':[1,0,0],
                'wall_front':[0,-1,0],'wall_back':[0,1,0]}
    original_groups=model.geom_group.copy()
    try:
        for opening in room_openings(room):
            wall=opening['wall'];bid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,wall)
            if bid<0:raise ValueError('Opening wall missing: '+wall)
            # Isolate this wall's collision geoms, excluding decorative visuals
            # and the aperture's independent glass/frame/door entities.
            model.geom_group[:]=0
            model.geom_group[(model.geom_bodyid==bid)&(original_groups==2)]=5
            group=np.array([0,0,0,0,0,1],np.uint8);hit_id=np.zeros(1,np.int32)
            a,b,c,d=opening['bounds'];samples=[]
            for fu in (.1,.5,.9):
                for fz in (.1,.5,.9):
                    u=a+(b-a)*fu;z=c+(d-c)*fz
                    origin={'wall_left':[room['x_min']+.05,u,z],
                            'wall_right':[room['x_max']-.05,u,z],
                            'wall_front':[u,room['y_min']+.05,z],
                            'wall_back':[u,room['y_max']-.05,z]}[wall]
                    distance=mujoco.mj_ray(model,data,np.asarray(origin,float),
                        np.asarray(directions[wall],float),group,True,-1,hit_id)
                    if 0<=distance<=.05+room['thickness']+.006:
                        raise ValueError('Wall collision fills declared opening: '+str(opening))
                    samples.append({'origin_m':origin,'wall_distance_m':float(distance)})
            results.append({'wall':wall,'bounds':opening['bounds'],'status':'passed',
                            'samples':samples,'scope':'structural wall only; glazing not tested'})
    finally:
        model.geom_group[:]=original_groups
    return results
