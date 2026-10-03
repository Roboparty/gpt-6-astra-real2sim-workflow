"""Common modelling checks against allowed RGB/learned depth only, never evaluator truth.

Run in Blender with -- --model MODEL --inputs METHOD/inputs --transform JSON
--out METHOD/checks/v1 --mode paired|all --version N. Transform JSON contains
model_from_input (rigid4x4), or may itself be that matrix. Model bytes stay unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_visibility import render_members,include_instance

CHECKS=[0,4,8,12,16,20,24,28,32,35]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def sample_reference(depth,valid,K,rays):
    projected=rays@K.T;x=projected[:,0]/projected[:,2];y=projected[:,1]/projected[:,2]
    x0=np.floor(x).astype(int);y0=np.floor(y).astype(int);x1=x0+1;y1=y0+1
    support=(x0>=0)&(y0>=0)&(x1<depth.shape[1])&(y1<depth.shape[0]);ids=np.flatnonzero(support)
    ids=ids[valid[y0[ids],x0[ids]]&valid[y0[ids],x1[ids]]&valid[y1[ids],x0[ids]]&valid[y1[ids],x1[ids]]]
    a=x[ids]-x0[ids];b=y[ids]-y0[ids];result=np.full(len(rays),np.nan)
    result[ids]=depth[y0[ids],x0[ids]]*(1-a)*(1-b)+depth[y0[ids],x1[ids]]*a*(1-b)+depth[y1[ids],x0[ids]]*(1-a)*b+depth[y1[ids],x1[ids]]*a*b
    return result


def metrics(pred,reference):
    domain=np.isfinite(reference)&(reference>=.1)&(reference<=30);valid=domain&np.isfinite(pred)&(pred>=.1)&(pred<=30)
    n=int(domain.sum());count=int(valid.sum());error=pred[valid]-reference[valid]
    return dict(domain_pixels=n,predicted_pixels=count,coverage=count/n if n else None,
        signed_mean_m=float(error.mean()) if count else None,mae_m=float(np.abs(error).mean()) if count else None,
        rmse_m=float(np.sqrt(np.mean(error**2))) if count else None,absrel=float(np.mean(np.abs(error)/reference[valid])) if count else None,
        missing_penalty_mae_m=float((np.abs(error).sum()+30*(n-count))/n) if n else None)


def scene_tree():
    vertices=[];faces=[];objects=[];graph=bpy.context.evaluated_depsgraph_get();members=render_members(bpy.context.scene)
    for instance in graph.object_instances:
        obj=instance.object
        if not include_instance(instance,members):continue
        mesh=obj.to_mesh()
        try:
            mesh.calc_loop_triangles();start=len(vertices)
            vertices.extend(instance.matrix_world@v.co for v in mesh.vertices)
            faces.extend(tuple(start+i for i in triangle.vertices) for triangle in mesh.loop_triangles)
            objects.append(dict(name=obj.original.name,vertices=len(mesh.vertices),triangles=len(mesh.loop_triangles)))
        finally:obj.to_mesh_clear()
    if not faces:raise ValueError('No visible surface geometry')
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),objects


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--transform',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['paired','all'],required=True);p.add_argument('--version',type=int,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=a.inputs.resolve().parent
    if not 1<=a.version<=5:raise ValueError('Version budget is1..5')
    for path in [a.model,a.transform,a.out]:
        if not path.resolve().is_relative_to(root):raise ValueError('Checker paths must stay in this method scope')
    packet=json.loads((a.inputs/'packet.json').read_text());frames=packet['frames'];assert len(frames)==36
    manifest_path=a.inputs/'depth_reference/manifest.json';manifest=json.loads(manifest_path.read_text())
    refs={frame['sample_index']:frame for frame in manifest['frames']};assert set(refs)==set(range(36))
    transform=json.loads(a.transform.read_text());G=np.asarray(transform['model_from_input'] if isinstance(transform,dict) else transform,float)
    if G.shape!=(4,4) or not np.isfinite(G).all() or not np.allclose(G[3],[0,0,0,1],atol=1e-8) or not np.allclose(G[:3,:3]@G[:3,:3].T,np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(G[:3,:3]),1,atol=1e-6):raise ValueError('Only one rigid model_from_input is permitted')
    a.out.mkdir(parents=True,exist_ok=False);before=sha(a.model);started=time.monotonic();implementation={name:sha(Path(__file__).parent/name) for name in ['check_agent_scene.py','render_visibility.py']}
    bpy.ops.wm.open_mainfile(filepath=str(a.model.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;bpy.context.view_layer.update()
    tree,inventory=scene_tree();save=lambda path,value:path.write_text(json.dumps(value,indent=2,allow_nan=False))
    rows=[];indices=CHECKS if a.mode=='paired' else list(range(36));depths=[];reference_depths=[]
    camera=bpy.data.objects.new('paired_check_camera',bpy.data.cameras.new('paired_check_camera'));scene.collection.objects.link(camera)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene.render.use_border=False;scene.render.use_crop_to_border=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.render.threads_mode='FIXED';scene.render.threads=2
    for index in indices:
        frame=frames[index];source=Path(frame['path']).resolve()
        if not source.is_relative_to(a.inputs.resolve()) or sha(source)!=frame['sha256']:raise ValueError('RGB is outside or differs from frozen inputs')
        ref=refs[index];path=(manifest_path.parent/ref['path']).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()) or sha(path)!=ref['sha256']:raise ValueError('Depth reference hash/scope mismatch')
        data=np.load(path);W,H=frame['image_size'];K=np.asarray(frame['K']);T=G@np.asarray(frame['T_world_camera'])
        u,v=np.meshgrid((np.arange(160)+.5)*W/160-.5,(np.arange(120)+.5)*H/120-.5)
        rays=np.column_stack([(u.ravel()-K[0,2])/K[0,0],(v.ravel()-K[1,2])/K[1,1],np.ones(u.size)])
        reference=sample_reference(data['depth_z_m'],data['valid_mask'],data['K_depth'],rays)
        world=rays@T[:3,:3].T;length=np.linalg.norm(world,axis=1);model_depth=np.full(len(rays),np.nan);origin=Vector(T[:3,3])
        for j,ray in enumerate(world):
            hit,normal,face,distance=tree.ray_cast(origin,Vector(ray/length[j]),30*length[j])
            if hit is not None:model_depth[j]=distance/length[j]
        row=dict(index=index,frame_id=frame['frame_id'],source=str(source),source_sha256=frame['sha256'],reference_sha256=ref['sha256'],**metrics(model_depth,reference))
        if a.mode=='paired':
            width=640;height=round(H*width/W);sx=width/W;sy=height/H;fx=K[0,0]*sx;fy=K[1,1]*sy;cx=(K[0,2]+.5)*sx;cy=(K[1,2]+.5)*sy;ratio=fx/fy
            camera.matrix_world=Matrix(T.tolist())@Matrix.Diagonal((1,-1,-1,1));camera.data.type='PERSP';camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=36;camera.data.lens=fx*36/width;camera.data.shift_x=(width/2-cx)/width;camera.data.shift_y=(cy-height/2)*ratio/width
            camera.data.clip_start=.01;camera.data.clip_end=100;camera.data.dof.use_dof=False;scene.camera=camera
            scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.pixel_aspect_x=max(1,1/ratio);scene.render.pixel_aspect_y=max(1,ratio)
            name=f'view_{index:03d}.png';scene.render.filepath=str(a.out/name);bpy.ops.render.render(write_still=True);row.update(render=name,render_sha256=sha(a.out/name),render_size=[width,height])
        rows.append(row);depths.append(model_depth.reshape(120,160));reference_depths.append(reference.reshape(120,160))
        print('CHECKED',a.mode,index,flush=True)
    np.savez_compressed(a.out/'depth_checks.npz',sample_indices=indices,model_depth_z_m=np.asarray(depths),reference_depth_z_m=np.asarray(reference_depths))
    report=dict(status='complete',scope='fit-only RGB and learned-depth checks, not heldout/GT evaluation or visual acceptance',mode=a.mode,version=a.version,
        model=str(a.model),model_sha256=before,model_unchanged=sha(a.model)==before,model_from_input=G.tolist(),reference_manifest_sha256=sha(manifest_path),
        rows=rows,visible_inventory=inventory,seconds=time.monotonic()-started,implementation_sha256=implementation,blender=bpy.app.version_string,render_settings=dict(engine='CPU Cycles',samples=12,threads=2,width=640))
    assert report['model_unchanged'];save(a.out/'report.json',report)
    ledger=root/'logs/common_check_runs.jsonl';ledger.parent.mkdir(exist_ok=True)
    with ledger.open('a') as stream:stream.write(json.dumps(dict(mode=a.mode,version=a.version,model_sha256=before,output=str(a.out),views=len(rows),seconds=report['seconds']))+'\n')
    print('COMMON_CHECK_COMPLETE',a.mode,a.version,len(rows),flush=True)


if __name__=='__main__':main()
