"""Evaluator-only real laser truth conversion, after all reconstruction models freeze."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from prepare_eth3d_camera_benchmark import read_cameras,read_images,sha,save
from run_large_scene_camera_ablation import similarity


def ply_vertices(path):
    types={'float':'<f4','float32':'<f4','double':'<f8','float64':'<f8','uchar':'u1','uint8':'u1','int':'<i4','uint':'<u4','short':'<i2','ushort':'<u2'}
    with path.open('rb') as stream:
        if stream.readline()!=b'ply\n':raise ValueError('Expected PLY')
        props=[];active=False;count=None;binary=False
        while True:
            line=stream.readline().decode('ascii').strip()
            if line=='end_header':break
            p=line.split()
            if p[:1]==['format']:binary=p[1]=='binary_little_endian'
            if p[:1]==['element']:
                active=p[1]=='vertex'
                if active:count=int(p[2])
            if p[:1]==['property'] and active:props.append((p[2],types[p[1]]))
        offset=stream.tell()
    if not binary or count is None:raise ValueError('Expected binary little endian vertex cloud')
    data=np.memmap(path,dtype=np.dtype(props),mode='r',offset=offset,shape=(count,))
    return np.column_stack([data[k] for k in ['x','y','z']])


def distorted_uv(rays,parameters):
    fx,fy,cx,cy,k1,k2,p1,p2,k3,k4,sx,sy=parameters
    x,y=rays[:,:2].T;r=np.hypot(x,y);theta=np.arctan(r);factor=np.divide(theta,r,out=np.ones_like(r),where=r>0)
    x=x*factor;y=y*factor;t2=theta**2;radial=1+k1*t2+k2*t2**2+k3*t2**3+k4*t2**4
    return np.column_stack([fx*(x*radial+2*p1*x*y+p2*(t2+2*x*x)+sx*t2)+cx,
                            fy*(y*radial+2*p2*x*y+p1*(t2+2*y*y)+sy*t2)+cy])


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--dataset',type=Path,required=True);a=p.parse_args()
    base=a.benchmark;models=base/'models';summary=json.loads((models/'summary.json').read_text())
    if summary['status']!='complete' or len(summary['conditions'])!=3:raise ValueError('All three models must freeze first')
    for row in summary['conditions']:
        if sha(models/row['condition']/'editable_mesh.npz')!=row['mesh_sha256']:raise ValueError('Frozen mesh changed')
    out=base/'evaluation';out.mkdir(exist_ok=False)
    views=json.loads((base/'evaluator/frames.json').read_text())['frames'];G=np.array(json.loads((base/'evaluator/canonical_from_eth3d.json').read_text())['matrix'])
    calibration=next((a.dataset/'original').rglob('cameras.txt'));cameras=read_cameras(calibration)
    original={Path(r['name']).stem:r for r in read_images(calibration.with_name('images.txt'))}
    grid_depth=[];grid_rays=[];coverage=[]
    for view in views:
        W,H=view['image_size'];K=np.array(view['K_raster']);u,v=np.meshgrid((np.arange(160)+.5)*W/160,(np.arange(120)+.5)*H/120)
        rays=np.stack([(u.ravel()-K[0,2])/K[0,0],(v.ravel()-K[1,2])/K[1,1],np.ones(u.size)],axis=1)
        raw=original[view['frame_id']];c=cameras[raw['camera_id']]
        if c['model']!='THIN_PRISM_FISHEYE':raise ValueError('Unexpected ETH3D raw camera')
        # Original/undistorted COLMAP cameras must describe the same optical frame.
        if not np.allclose(G@raw['T'],view['T_world_camera'],atol=1e-6,rtol=0):raise ValueError('Camera pose mismatch after undistortion')
        uv=distorted_uv(rays,c['parameters']);xy=np.floor(uv).astype(int);rw,rh=c['image_size']
        path=next((a.dataset/'depth').rglob(Path(raw['name']).name))
        if path.stat().st_size!=rw*rh*4:raise ValueError('GT raw depth size mismatch')
        depth=np.memmap(path,dtype='<f4',mode='r',shape=(rh,rw))
        valid=(xy[:,0]>=0)&(xy[:,0]<rw)&(xy[:,1]>=0)&(xy[:,1]<rh)
        z=np.full(len(rays),np.nan,np.float32);z[valid]=depth[xy[valid,1],xy[valid,0]]
        z[~np.isfinite(z)|(z<.1)|(z>30)]=np.nan
        grid_depth.append(z);grid_rays.append(rays);coverage.append(dict(frame=view['frame_id'],valid_gt=int(np.isfinite(z).sum()),rays=len(z),depth_file_sha256=sha(path)))
    np.savez_compressed(out/'truth_grid.npz',depth=np.array(grid_depth),rays=np.array(grid_rays),poses=np.array([v['T_world_camera'] for v in views]))
    save(out/'views.json',views)
    scanroot=next((a.dataset/'scan_eval').rglob('scan_alignment.mlp')).parent
    clouds=[];scan_records=[]
    for mesh in ET.parse(scanroot/'scan_alignment.mlp').findall('.//MLMesh'):
        path=scanroot/mesh.attrib['filename'];M=np.fromstring(mesh.find('MLMatrix44').text,sep=' ').reshape(4,4);T=G@M
        points=ply_vertices(path);points=(points@T[:3,:3].T+T[:3,3]).astype(np.float32)
        if not np.isfinite(points).all():raise ValueError('Nonfinite GT scan')
        clouds.append(points);scan_records.append(dict(path=str(path),sha256=sha(path),points=len(points)))
    points=np.concatenate(clouds);np.save(out/'laser_points.npy',points)
    rng=np.random.default_rng(20261003);indices=rng.choice(len(points),100000,replace=len(points)<100000);np.save(out/'laser_sample.npy',points[indices])
    mapping=[v for v in views if v['role']=='reconstruction'];target=np.array([v['T_world_camera'] for v in mapping])[:,:3,3];variants=[]
    for condition in ['RGB','RGB_K','RGB_K_T']:
        with np.load(models/condition/'editable_mesh.npz') as data:pred=data['camera_poses'][:,:3,3]
        if condition=='RGB_K_T':variants.append(dict(id=condition,condition=condition,alignment='supplied_reference_camera_world',transform=np.eye(4).tolist()));continue
        scale,R,t=similarity(pred,target)
        for mode in ['SE3','Sim3']:
            s=scale if mode=='Sim3' else 1.;translation=target.mean(0)-s*R@pred.mean(0);T=np.eye(4);T[:3,:3]=s*R;T[:3,3]=translation
            error=np.linalg.norm(pred@T[:3,:3].T+translation-target,axis=1)
            variants.append(dict(id=condition+'_'+mode,condition=condition,alignment=mode,scale=s,transform=T.tolist(),camera_translation_rmse_m=float(np.sqrt(np.mean(error**2))),
                                 scope='GT-mapping-camera alignment after freeze; Sim3 is a diagnostic, not native metric recovery'))
    save(out/'variants.json',variants)
    save(out/'truth_receipt.json',dict(status='ready',GT_access_after_all_models_frozen=True,model_hashes={r['condition']:r['mesh_sha256'] for r in summary['conditions']},
        truth_grid_sha256=sha(out/'truth_grid.npz'),laser_points_sha256=sha(out/'laser_points.npy'),scan_sources=scan_records,laser_points=len(points),
        depth_axis='optical Z; upstream GroundTruthCreator writes image_point.z()',depth_sampling='160x120 undistorted rays mapped through official THIN_PRISM_FISHEYE into raw GT; nearest containing raw pixel; nonfinite/absent GT excluded and counted',
        GT_coverage=coverage,truth_scope='Published ETH3D eval laser points (observed by2+ official images); not all unseen physical surfaces'))
    print(json.dumps(dict(status='ready',views=len(views),laser_points=len(points),depth_domain_pixels=sum(x['valid_gt'] for x in coverage))))


if __name__=='__main__':main()
