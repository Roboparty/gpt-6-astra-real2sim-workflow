"""Raycast frozen editable meshes at all real cameras; never revise geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.blender_camera import apply_camera
from r2s.camera import resize_camera


def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False))


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=Path,required=True);p.add_argument('--variant',required=True);p.add_argument('--output-suffix',default='')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=a.benchmark;ev=root/'evaluation'
    variant=next(x for x in json.loads((ev/'variants.json').read_text()) if x['id']==a.variant)
    model=root/'models'/variant['condition']/'editable_mesh.npz';receipt=json.loads((ev/'truth_receipt.json').read_text())
    if sha(model)!=receipt['model_hashes'][variant['condition']]:raise ValueError('Frozen model hash mismatch')
    out=ev/(a.variant+a.output_suffix);out.mkdir(exist_ok=False);start=time.monotonic()
    with np.load(model) as arrays:
        T=np.array(variant['transform']);vertices=arrays['vertices'].astype(float)@T[:3,:3].T+T[:3,3];faces=arrays['faces'];colors=arrays['colors'];counts=arrays['frame_face_counts']
    tree=BVHTree.FromPolygons(vertices.tolist(),faces.tolist(),all_triangles=True)
    with np.load(ev/'truth_grid.npz') as arrays:truth=arrays['depth'];rays=arrays['rays'];poses=arrays['poses']
    predictions=np.full(truth.shape,np.nan,np.float32)
    for i,(camera,ray,domain) in enumerate(zip(poses,rays,np.isfinite(truth))):
        origin=Vector(camera[:3,3]);world=ray@camera[:3,:3].T;norm=np.linalg.norm(world,axis=1)
        for j in np.flatnonzero(domain):
            hit,normal,face,distance=tree.ray_cast(origin,Vector(world[j]/norm[j]),30*norm[j])
            if hit is not None:predictions[i,j]=distance/norm[j]
    np.save(out/'rendered_z.npy',predictions)
    truth_points=np.load(ev/'laser_sample.npy');completeness=np.full(len(truth_points),np.nan)
    for i,point in enumerate(truth_points):
        location,normal,index,distance=tree.find_nearest(Vector(point))
        if location is not None:completeness[i]=distance
    np.save(out/'gt_to_model_m.npy',completeness)
    triangles=vertices[faces];cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);area=np.linalg.norm(cross,axis=1)/2
    if not np.isfinite(area).all() or area.sum()<=0:raise ValueError('No finite surface to evaluate')
    rng=np.random.default_rng(20261003);selected=rng.choice(len(faces),100000,p=area/area.sum());r1=np.sqrt(rng.random(100000));r2=rng.random(100000)
    sampled=(1-r1[:,None])*triangles[selected,0]+(r1*(1-r2))[:,None]*triangles[selected,1]+(r1*r2)[:,None]*triangles[selected,2]
    np.save(out/'model_surface_samples.npy',sampled.astype(np.float32));del triangles,cross,tree
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    mesh=bpy.data.meshes.new('photo_patch_surface');mesh.from_pydata(vertices.tolist(),[],faces.tolist());mesh.update()
    obj=bpy.data.objects.new('reconstructed_photo_patches',mesh);scene.collection.objects.link(obj)
    obj['representation']='Static observed-surface patches; semantic instances and closed solids not established'
    attr=mesh.color_attributes.new(name='photographic_color',type='FLOAT_COLOR',domain='POINT')
    linear=np.where(colors<=.04045,colors/12.92,((colors+.055)/1.055)**2.4)
    rgba=np.column_stack([linear,np.ones(len(colors),np.float32)]).astype(np.float32);attr.data.foreach_set('color',rgba.ravel())
    mat=bpy.data.materials.new('unlit_photographic_reprojection');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
    vertex=nodes.new('ShaderNodeVertexColor');vertex.layer_name=attr.name;emission=nodes.new('ShaderNodeEmission');output=nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(vertex.outputs['Color'],emission.inputs['Color']);mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface']);obj.data.materials.append(mat)
    scene.world=bpy.data.worlds.new('unobserved_background');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    camera=bpy.data.objects.new('evaluation_camera',bpy.data.cameras.new('evaluation_camera'));scene.collection.objects.link(camera);camera.data.clip_start=.01;camera.data.clip_end=100
    views=json.loads((ev/'views.json').read_text());mapping=[(i,v) for i,v in enumerate(views) if v['role']=='reconstruction'];held=[(i,v) for i,v in enumerate(views) if v['role']=='heldout']
    renders=[]
    # Identical preselected views for all candidates; five input views and three heldout previews.
    for i,view in [mapping[j] for j in [0,7,14,21,28]]+[held[j] for j in [0,3,7]]:
        pose=np.array(view['T_world_camera']);K=np.array(view['K']);W,H=view['image_size'];size=[640,round(H*640/W)]
        camera_spec=resize_camera(dict(position=pose[:3,3].tolist(),rotation_world_to_cv=pose[:3,:3].T.tolist(),image_size=[W,H],
                                      focal_px=K[0,0],focal_y_px=K[1,1],principal_point=K[:2,2].tolist(),pixel_coordinates='integer_centers'),size)
        apply_camera(scene,camera,camera_spec);scene.render.filepath=str(out/(view['frame_id']+'.png'));bpy.ops.render.render(write_still=True)
        renders.append(dict(frame_id=view['frame_id'],split=view['role'],source=view['path'],render=scene.render.filepath,size=size))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'editable_scene.blend'))
    save(out/'render_manifest.json',renders)
    save(out/'receipt.json',dict(status='complete',variant=variant,source_mesh_sha256=sha(model),model_unchanged=sha(model)==receipt['model_hashes'][variant['condition']],
        camera_views=len(views),mapping_views=36,withheld_views=8,truth_domain_pixels=int(np.isfinite(truth).sum()),
        rendered_valid_on_truth_domain=int(np.isfinite(predictions).sum()),surface_samples_each_direction=100000,vertices=len(vertices),triangles=len(faces),
        wall_seconds=time.monotonic()-start,appearance_scope='sRGB input converted to linear emission then Standard display; unlit photo reprojection, not recovered materials/lighting',
        model_scope='Static triangle patches. Editable Blender mesh, not semantic object reconstruction or physics acceptance',blender=bpy.app.version_string))
    print('EVALUATION_COMPLETE',a.variant,round(time.monotonic()-start,3),flush=True)


if __name__=='__main__':main()
