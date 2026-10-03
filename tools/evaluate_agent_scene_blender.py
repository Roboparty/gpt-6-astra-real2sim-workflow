"""Evaluator-only: frozen semantic Blender scene vs frozen real-scene laser evidence.

Authored materials/lights are retained. All geometry is moved into INPUT coordinates
mathematically for measurement; source scene bytes are never modified.
"""
import argparse,hashlib,json,time
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_visibility import render_members,include_instance


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--truth',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);freeze=json.loads(a.freeze.read_text());G=np.asarray(freeze['model_from_input'],float)
    if sha(a.model)!=freeze['model_sha256']:raise ValueError('Frozen candidate model changed')
    if G.shape!=(4,4) or not np.isfinite(G).all() or not np.allclose(G[3],[0,0,0,1],atol=1e-8) or not np.allclose(G[:3,:3]@G[:3,:3].T,np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(G[:3,:3]),1,atol=1e-6):raise ValueError('Model gauge must be rigid')
    a.out.mkdir(parents=True,exist_ok=False);started=time.monotonic();inverse=np.linalg.inv(G)
    bpy.ops.wm.open_mainfile(filepath=str(a.model.resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get()
    vertices=[];faces=[];inventory=[];members=render_members(scene)
    for instance in graph.object_instances:
        obj=instance.object
        if not include_instance(instance,members):continue
        mesh=obj.to_mesh()
        try:
            mesh.calc_loop_triangles();offset=len(vertices);transform=Matrix(inverse.tolist())@instance.matrix_world
            vertices.extend(transform@v.co for v in mesh.vertices);faces.extend(tuple(offset+i for i in tri.vertices) for tri in mesh.loop_triangles)
            inventory.append(dict(name=obj.original.name,vertices=len(mesh.vertices),triangles=len(mesh.loop_triangles)))
        finally:obj.to_mesh_clear()
    if not faces:raise ValueError('No visible geometry')
    tree=BVHTree.FromPolygons(vertices,faces,all_triangles=True)
    with np.load(a.truth/'truth_grid.npz') as data:depth=data['depth'];rays=data['rays'];poses=data['poses']
    pred=np.full(depth.shape,np.nan,np.float32)
    for i,(T,ray,domain) in enumerate(zip(poses,rays,np.isfinite(depth))):
        origin=Vector(T[:3,3]);world=ray@T[:3,:3].T;length=np.linalg.norm(world,axis=1)
        for j in np.flatnonzero(domain):
            location,normal,face,distance=tree.ray_cast(origin,Vector(world[j]/length[j]),30*length[j])
            if location is not None:pred[i,j]=distance/length[j]
    np.save(a.out/'rendered_z.npy',pred)
    gt=np.load(a.truth/'laser_sample.npy');distances=np.full(len(gt),np.nan)
    for i,point in enumerate(gt):
        location,normal,face,distance=tree.find_nearest(Vector(point))
        if location is not None:distances[i]=distance
    np.save(a.out/'gt_to_model_m.npy',distances)
    xyz=np.asarray(vertices);tri=xyz[np.asarray(faces)];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    rng=np.random.default_rng(20261003);chosen=rng.choice(len(faces),100000,p=area/area.sum());r1=np.sqrt(rng.random(100000));r2=rng.random(100000)
    samples=(1-r1[:,None])*tri[chosen,0]+(r1*(1-r2))[:,None]*tri[chosen,1]+(r1*r2)[:,None]*tri[chosen,2];np.save(a.out/'model_surface_samples.npy',samples.astype(np.float32))
    views=json.loads((a.truth/'views.json').read_text());mapping=[v for v in views if v['role']=='reconstruction'];held=[v for v in views if v['role']=='heldout']
    camera=bpy.data.objects.new('independent_evaluation_camera',bpy.data.cameras.new('independent_evaluation_camera'));scene.collection.objects.link(camera)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.use_border=False;scene.render.use_crop_to_border=False;scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.render.threads_mode='FIXED';scene.render.threads=2;renders=[]
    for view in [mapping[i] for i in [0,7,14,21,28]]+held:
        T=G@np.asarray(view['T_world_camera']);K=np.asarray(view['K']);W,H=view['image_size'];width=640;height=round(H*width/W);sx=width/W;sy=height/H;fx=K[0,0]*sx;fy=K[1,1]*sy;cx=(K[0,2]+.5)*sx;cy=(K[1,2]+.5)*sy;ratio=fx/fy
        camera.matrix_world=Matrix(T.tolist())@Matrix.Diagonal((1,-1,-1,1));camera.data.type='PERSP';camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=36;camera.data.lens=fx*36/width;camera.data.shift_x=(width/2-cx)/width;camera.data.shift_y=(cy-height/2)*ratio/width;camera.data.clip_start=.01;camera.data.clip_end=100;camera.data.dof.use_dof=False
        scene.camera=camera;scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.pixel_aspect_x=max(1,1/ratio);scene.render.pixel_aspect_y=max(1,ratio)
        path=a.out/(view['frame_id']+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        renders.append(dict(frame_id=view['frame_id'],split=view['role'],source=view['path'],render=str(path),size=[width,height],render_sha256=sha(path)))
    save=lambda path,data:path.write_text(json.dumps(data,indent=2,allow_nan=False))
    save(a.out/'render_manifest.json',renders);save(a.out/'visible_inventory.json',inventory)
    save(a.out/'receipt.json',dict(status='complete',model_sha256=sha(a.model),model_unchanged=sha(a.model)==freeze['model_sha256'],freeze_sha256=sha(a.freeze),model_from_input=G.tolist(),
        source_truth_grid_sha256=sha(a.truth/'truth_grid.npz'),views=len(views),appearance_views=len(renders),vertices=len(vertices),triangles=len(faces),model_surface_samples=len(samples),laser_surface_samples=len(gt),
        candidate_quality_status=freeze.get('quality_status'),appearance_scope='Authored materials/lights/color settings retained; common CPU Cycles16samples and camera protocol',
        depth_scope='opaque visible geometry opticalZ in input frame; physical/transparent appearance is separate',wall_seconds=time.monotonic()-started,blender=bpy.app.version_string))
    print('SEMANTIC_EVALUATION_COMPLETE',a.out,time.monotonic()-started,flush=True)


if __name__=='__main__':main()
