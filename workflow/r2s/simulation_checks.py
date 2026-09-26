"""Check enclosing collision surfaces without confusing foreground trim with walls."""
import numpy as np
import mujoco


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
    for name,(expected_body,direction,expected,origins) in specs.items():
        rejected=[]
        for origin in origins:
            distance=mujoco.mj_ray(model,data,np.asarray(origin,float),np.asarray(direction,float),group,True,-1,hit_id)
            body=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,int(model.geom_bodyid[hit_id[0]])) if hit_id[0]>=0 else None
            error=abs(distance-expected)
            if body==expected_body and error<.006:
                result[name]=dict(origin_m=list(map(float,origin)),hit_body=body,distance_m=float(distance),expected_m=expected,error_m=float(error),rejected_candidate_count=len(rejected),occluded_examples=rejected[:3]);break
            rejected.append(dict(origin_m=list(map(float,origin)),hit_body=body,distance_m=float(distance)))
        else:
            raise ValueError('No unobstructed valid '+expected_body+' collision-surface ray; candidates: '+str(rejected[:3]))
    return result
