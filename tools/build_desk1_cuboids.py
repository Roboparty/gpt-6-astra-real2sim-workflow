"""Render an independently saved orthogonal Desk1 fit, preserving visible photo texture."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import bpy
import numpy as np
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_desk1_scene import sha,save,plain,project_material

def main():
    p=argparse.ArgumentParser();p.add_argument('--annotation',type=Path,required=True);p.add_argument('--fit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    cfg=json.loads(a.annotation.read_text());fit=json.loads(a.fit.read_text());a.output.mkdir(parents=True,exist_ok=False);t0=time.monotonic()
    if sha(cfg['source_image'])!=fit['source_sha256'] or sha(a.annotation)!=fit['annotation_sha256']:raise ValueError('Frozen fitting input changed')
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC'
    W,H=1920,1080;camera=np.array(fit['camera']['position']);fx=fy=fit['camera']['focal_px'];alpha=math.radians(fit['camera']['down_pitch_deg']);roll=math.radians(fit['camera']['roll_deg'])
    R=np.array([[1,0,0],[0,-math.sin(alpha),math.cos(alpha)],[0,-math.cos(alpha),-math.sin(alpha)]])@np.array([[math.cos(roll),-math.sin(roll),0],[math.sin(roll),math.cos(roll),0],[0,0,1]])
    image=bpy.data.images.load(cfg['source_image']);image.pack();objects=[]
    def unproject(pixel,z):
        u,v=np.array(pixel)*1.5;ray=R@np.array([(u-W/2)/fx,(v-H/2)/fy,1]);return camera+ray*((z-camera[2])/ray[2])
    for box,spec in zip(fit['boxes'],cfg['boxes']):
        if box['id']!=spec['id']:raise ValueError('Stable object identity changed')
        verts=np.array(box['world_vertices']);origin=verts.mean(axis=0)
        mesh=bpy.data.meshes.new(box['id']+'_orthogonal_mesh');mesh.from_pydata((verts-origin).tolist(),[],[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]);mesh.update()
        obj=bpy.data.objects.new(box['id'],mesh);scene.collection.objects.link(obj);obj.location=origin
        obj.data.materials.append(plain(box['id']+'_hidden_prior',spec['hidden_color_linear']))
        obj.data.materials.append(project_material(box['id']+'_source_photo',image,origin,camera,R,fx,fy,W,H))
        for face in mesh.polygons:face.material_index=1 if face.index in spec['visible_faces'] else 0
        bevel=obj.modifiers.new('paper_edge_softness','BEVEL');bevel.width=.0003;bevel.segments=2
        obj['object_id']=box['id'];obj['scale_status']='external_nominal_prior' if box['web_prior_used'] else 'source_only_assumed_sugar_height_gauge'
        obj['geometry_origin']=fit['arm'];objects.append(obj)
    marker=cfg['marker'];left=unproject(marker['axis_pixels'][0],marker['radius_assumed_m']);right=unproject(marker['axis_pixels'][1],marker['radius_assumed_m']);axis=right-left;length=np.linalg.norm(axis);direction=Vector(axis).normalized()
    for name,lo,hi,radius,color in [('black_cap',0,.23,1.,(.005,.005,.006)),('white_barrel',.23,.95,.92,(.82,.82,.79)),('white_end_plug',.95,1.02,.92,(.88,.88,.84))]:
        center=left+(lo+hi)/2*axis;bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=marker['radius_assumed_m']*radius,depth=length*(hi-lo),location=center)
        obj=bpy.context.object;obj.name='expo_'+name;obj.rotation_euler=direction.to_track_quat('Z','Y').to_euler();bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        obj.data.materials.append(plain(obj.name+'_hidden_prior',color));obj.data.materials.append(project_material(obj.name+'_source_photo',image,center,camera,R,fx,fy,W,H))
        for face in obj.data.polygons:face.material_index=1 if Vector(face.normal).dot(Vector(camera-center))>0 else 0;face.use_smooth=abs(face.normal.dot(direction))<.9
        bevel=obj.modifiers.new('cap_edge','BEVEL');bevel.width=.0005;bevel.segments=3
        obj['object_id']='expo_marker';obj['scale_status']='assumed_radius_source_endpoints';obj['web_conflict_consumed']=False;objects.append(obj)
    for name,position,dimensions,color in [('desk_support',(0,-.39,-.025),(1.4,.88,.05),cfg['desk_color']),('plain_back_wall',(0,.014,.72),(2,.02,1.44),cfg['wall_color'])]:
        bpy.ops.mesh.primitive_cube_add(size=1,location=position);obj=bpy.context.object;obj.name=name;obj.dimensions=dimensions;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);obj.data.materials.append(plain(name+'_material',color))
    data=bpy.data.cameras.new('source_fitted_camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam)
    M=np.eye(4);M[:3,:3]=R@np.diag([1,-1,-1]);M[:3,3]=camera;cam.matrix_world=Matrix(M.tolist());data.sensor_fit='HORIZONTAL';data.sensor_width=36;data.lens=fx*36/W;data.clip_start=.01;data.clip_end=20;scene.camera=cam
    scene.world=bpy.data.worlds.new('neutral_world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
    light=bpy.data.lights.new('softbox','AREA');light.energy=35;light.shape='DISK';light.size=1.2;lo=bpy.data.objects.new(light.name,light);scene.collection.objects.link(lo);lo.location=(-.15,-.4,1)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.seed=0;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=2
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=0
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene['arm']=fit['arm'];scene['source_sha256']=fit['source_sha256'];scene['fit_sha256']=sha(a.fit)
    scene['scope']='single-view authored cuboid scene; source texture contains captured lighting; no GT/SOTA/dynamics qualification'
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'scene.blend'))
    inventory=[{'name':o.name,'object_id':o.get('object_id'),'vertices_world':[list(o.matrix_world@v.co) for v in o.data.vertices],'faces':[list(f.vertices) for f in o.data.polygons]} for o in objects]
    save(a.output/'objects.json',inventory)
    receipt={'status':'model_frozen','arm':fit['arm'],'source_sha256':fit['source_sha256'],'fit_sha256':sha(a.fit),'script_sha256':sha(__file__),'shared_material_helper_sha256':sha(Path(__file__).with_name('build_desk1_scene.py')),'model_sha256':sha(a.output/'scene.blend'),'editable_object_count':4,'foreground_mesh_parts':len(objects),'renders':[]}
    save(a.output/'receipt.json',receipt)
    scene.render.filepath=str(a.output/'source_view.png');t=time.monotonic();bpy.ops.render.render(write_still=True)
    receipt['renders'].append({'kind':'source_view','path':str(a.output/'source_view.png'),'sha256':sha(a.output/'source_view.png'),'wall_seconds':time.monotonic()-t})
    cam.location=Vector((.38,-.56,.51));target=Vector((-.025,-.16,.07));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();data.lens=38
    scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.filepath=str(a.output/'virtual_inspection.png');t=time.monotonic();bpy.ops.render.render(write_still=True)
    receipt['renders'].append({'kind':'virtual_only','path':str(a.output/'virtual_inspection.png'),'sha256':sha(a.output/'virtual_inspection.png'),'wall_seconds':time.monotonic()-t})
    receipt.update(status='rendered',wall_seconds=time.monotonic()-t0,source_unchanged=sha(cfg['source_image'])==fit['source_sha256']);save(a.output/'receipt.json',receipt);print(json.dumps(receipt))

if __name__=='__main__':main()
