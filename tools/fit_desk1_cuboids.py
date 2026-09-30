"""Bounded single-view camera/cuboid ablation; no GT or comparator image input."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.optimize import least_squares

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rotation(pitch,roll):
    a,r=math.radians(pitch),math.radians(roll)
    return np.array([[1,0,0],[0,-math.sin(a),math.cos(a)],[0,-math.cos(a),-math.sin(a)]])@np.array([[math.cos(r),-math.sin(r),0],[math.sin(r),math.cos(r),0],[0,0,1]])
def vertices(x,y,yaw,d):
    w,depth,h=d;t=np.array([[-w/2,-depth/2,0],[w/2,-depth/2,0],[w/2,depth/2,0],[-w/2,depth/2,0]])
    t=np.concatenate([t,t+[0,0,h]])
    a=math.radians(yaw);R=np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]])
    return t@R.T+[x,y,0]
def project(points,cam):
    q=(points-np.array([0,-.65,cam[3]]))@rotation(cam[1],cam[2]);z=q[:,2]
    return q[:,:2]/z[:,None]*math.exp(cam[0])+[640,360]
def unproject(pixel,z,cam):
    C=np.array([0,-.65,cam[3]]);ray=rotation(cam[1],cam[2])@np.array([(pixel[0]-640)/math.exp(cam[0]),(pixel[1]-360)/math.exp(cam[0]),1])
    return C+ray*((z-C[2])/ray[2])

def main():
    p=argparse.ArgumentParser();p.add_argument('--annotation',type=Path,required=True);p.add_argument('--phase',type=Path,required=True)
    p.add_argument('--web-report',type=Path);p.add_argument('--arm',choices=['B_image_cuboids','C_web_soft_cuboids','D_web_fixed_cuboids'],required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    cfg=json.loads(a.annotation.read_text());phase=json.loads(a.phase.read_text())
    report=json.loads(a.web_report.read_text()) if a.web_report is not None else None
    if a.arm!='B_image_cuboids' and (not report or report.get('status')!='validated'):raise ValueError('Web evidence gate did not validate')
    if report and report.get('status')!='validated':report=None
    if cfg['source_sha256']!=phase['source_sha256'] or sha(cfg['source_image'])!=phase['source_sha256']:raise ValueError('Source/phase hash mismatch')
    cam0=np.array([math.log(cfg['camera']['focal_px']/1.5),cfg['camera']['down_pitch_deg'],cfg['camera']['roll_deg'],cfg['camera']['position'][2]])
    obs=[];initial=[];web=[];held=[]
    eligible={r['object_id']:r for r in report['model_priors']} if report else {}
    for box in cfg['boxes']:
        top=np.array([unproject(px,box['height_assumed_m'],cam0) for px in box['top_front_order']])
        d=[(np.linalg.norm(top[1]-top[0])+np.linalg.norm(top[2]-top[3]))/2,
           (np.linalg.norm(top[3]-top[0])+np.linalg.norm(top[2]-top[1]))/2,box['height_assumed_m']]
        pose=[*top[:,:2].mean(axis=0),math.degrees(math.atan2(*(top[1]-top[0])[:2][::-1]))]
        initial.append((pose,np.array(d)))
        nominal=eligible.get(box['id'],{}).get('dimensions_m')
        if nominal is None and a.arm!='B_image_cuboids':raise ValueError('Required dimension prior unavailable for '+box['id'])
        web.append(None if nominal is None else np.array(nominal if box['id']!='chocolate_jello_box' else [nominal[0],nominal[2],nominal[1]]))
        fit=[(i+4,px) for i,px in enumerate(box['top_front_order'])]+[(i,box['bottom_pixels'][str(i)]) for i in [0,1]]
        hold=[(int(i),px) for i,px in box['bottom_pixels'].items() if int(i) not in [0,1]]
        obs.append(fit);held.append(hold)
    fixed=a.arm=='D_web_fixed_cuboids';soft=a.arm=='C_web_soft_cuboids';x0=cam0.tolist();lo=[math.log(400),10,-10,.12];hi=[math.log(5000),75,10,1.8]
    for pose,d in initial:
        x0+=pose;lo+=[-1,-.6,-180];hi+=[1,2,180]
        if not fixed:x0+=np.log(d).tolist();lo+=np.log([.005]*3).tolist();hi+=np.log([.3]*3).tolist()
    x0=np.clip(x0,np.array(lo)+1e-7,np.array(hi)-1e-7)
    def decode(x):
        result=[];offset=4
        for i in range(3):
            pose=x[offset:offset+3];offset+=3;d=web[i] if fixed else np.exp(x[offset:offset+3]);offset+=0 if fixed else 3
            result.append((pose,d))
        return result
    def errors(x,rows):
        result=[]
        for i,(pose,d) in enumerate(decode(x)):
            v=project(vertices(*pose,d),x[:4]);result.extend((v[j]-px).tolist() for j,px in rows[i])
        return np.array(result)
    def residual(x):
        e=errors(x,obs).ravel().tolist()
        if soft:
            for (_,d),nominal in zip(decode(x),web):e+=(np.log(d/nominal)/.1*4).tolist()
        elif not fixed:e+=[(decode(x)[0][1][2]-.175)*1e5]  # declared source-only scale gauge
        return np.array(e)
    trials=[];best=None
    for trial,factor in enumerate([.75,1,1.25,1.5]):
        start=x0.copy();start[0]+=math.log(factor);t=time.monotonic()
        fit=least_squares(residual,start,bounds=(lo,hi),loss='soft_l1',f_scale=4,max_nfev=phase['fit_protocol']['maximum_solver_evaluations_per_start'],x_scale='jac')
        training=errors(fit.x,obs);holdout=errors(fit.x,held)
        row={'start':trial,'focal_factor':factor,'solver_success':bool(fit.success),'solver_message':fit.message,'nfev':fit.nfev,'cost':float(fit.cost),
             'fit_rmse_px':float(np.sqrt(np.mean(training**2))),'fit_mean_corner_distance_px':float(np.mean(np.linalg.norm(training,axis=1))),
             'heldout_rmse_px':float(np.sqrt(np.mean(holdout**2))),'heldout_mean_corner_distance_px':float(np.mean(np.linalg.norm(holdout,axis=1))),
             'wall_seconds':time.monotonic()-t,'parameters':fit.x.tolist()};trials.append(row)
        if best is None or fit.cost<best[0]:best=(fit.cost,fit.x,trial)
    _,x,selected=best;cam={'focal_px':math.exp(x[0])*1.5,'position':[0,-.65,float(x[3])],'down_pitch_deg':float(x[1]),'roll_deg':float(x[2]),
        'status':'single-view joint fit with declared priors; no calibrated instance camera truth'}
    boxes=[]
    for i,(pose,d) in enumerate(decode(x)):
        predictions=project(vertices(*pose,d),x[:4])
        boxes.append({'id':cfg['boxes'][i]['id'],'pose_xy_yaw_deg':pose.tolist(),'dimensions_world_local_m':d.tolist(),
            'world_vertices':vertices(*pose,d).tolist(),'projected_vertices_1280':predictions.tolist(),
            'fit_corner_indices':[j for j,_ in obs[i]],'heldout_corner_indices':[j for j,_ in held[i]],
            'nominal_web_local_dimensions_m':None if web[i] is None else web[i].tolist(),'web_prior_used':a.arm!='B_image_cuboids',
            'relative_web_prior_deviation':None if web[i] is None else (d/web[i]-1).tolist()})
    result={'schema':'real2sim.desk1-cuboid-fit/1','arm':a.arm,'source_sha256':cfg['source_sha256'],'phase_sha256':sha(a.phase),
        'annotation_sha256':sha(a.annotation),'web_report_sha256':sha(a.web_report) if a.web_report is not None else None,'solver_script_sha256':sha(__file__),
        'camera':cam,'boxes':boxes,'selected_start':selected,'selection_rule':'minimum training robust cost, no heldout selection',
        'starts':trials,'metrics':{k:v for k,v in trials[selected].items() if k.startswith(('fit_','heldout_'))},
        'tolerance_status':'10 percent log dimension regularization in C is an experiment assumption; source tolerance is unquantified',
        'metric_truth_status':'No instance GT; nominal deviation and single-image reprojection are diagnostics only',
        'heldout_status':'three manually annotated corners of the same image; no novel real observation',
        'web_consumption':[] if a.arm=='B_image_cuboids' else [{'object_id':b['id'],'parameter':'dimensions','application':'orthogonal box dimensions and joint camera metric-scale prior'} for b in boxes],
        'wall_seconds':time.monotonic()-started}
    (a.output/'fit.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({'arm':a.arm,**result['metrics'],'wall_seconds':result['wall_seconds']}))

if __name__=='__main__':main()
