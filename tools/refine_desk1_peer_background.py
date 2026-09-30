"""One common RGB-driven background correction; foreground/camera are immutable."""
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
from build_desk1_moge_instances import sha,save,image_array

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--masks',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic();bpy.ops.wm.open_mainfile(filepath=str(a.input/'scene.blend'));scene=bpy.context.scene;cam=scene.camera;old_cam=cam.matrix_world.copy();data=json.loads((a.input/'receipt.json').read_text());R=np.asarray(data['camera']['optical_rotation_to_world']);C=np.asarray(data['camera']['position']);fx,fy=data['camera']['fx_px'],data['camera']['fy_px'];img=image_array(a.source)[...,:3];H,W=img.shape[:2]
    # Focal values in the prior receipt correspond to its prediction raster.
    K=np.asarray(data['camera']['K_normalized']);fx,fy=K[0,0]*W,K[1,1]*H;foreground=np.zeros((H,W),bool)
    for key in ['domino_sugar_box','chocolate_jello_box','red_jello_box','expo_marker']:foreground|=image_array(a.masks/(key+'_mask.png'))[...,0]>.5
    def unproject(x,y):
        ray=R@np.array([(x-W*.5)/fx,(y-H*.5)/fy,1.]);return C+ray*(-C[2]/ray[2])
    # Derive the table/wall contrast from the unchanged source samples instead of
    # assuming Blender image pixels are encoded in a particular intensity range.
    gray=img.mean(axis=-1);upper=gray[int(.10*H):int(.25*H)];lower=gray[int(.85*H):int(.97*H)];threshold=float((np.median(upper)+np.median(lower))/2)
    boundaries=[]
    for x in np.linspace(8,W-9,100).astype(int):
        for y in range(int(.28*H),int(.75*H)):
            if not foreground[y:y+10,x].any() and (gray[y:y+10,x]<threshold).all():boundaries.append([x,y]);break
    if len(boundaries)<20:raise ValueError('Source wall/table boundary cannot be established')
    boundary=np.array([unproject(x,y) for x,y in boundaries]);center=boundary[:,:2].mean(axis=0);_,_,V=np.linalg.svd(boundary[:,:2]-center,full_matrices=False);direction=V[0];length=max(1.5,float(np.ptp((boundary[:,:2]-center)@direction))*1.5)
    wall=bpy.data.objects['plain_back_wall'];wall.location=(*center,1.5);wall.rotation_euler=(0,0,math.atan2(direction[1],direction[0]));wall.scale=(1,1,1);wall.dimensions=(length,.02,3.)
    ygrid,xgrid=np.mgrid[:H,:W];table_pixels=(ygrid>.3*H)&~foreground&(gray<threshold);ys,xs=np.where(table_pixels);chosen=np.linspace(0,len(xs)-1,min(12000,len(xs))).astype(int);table_points=np.array([unproject(xs[i],ys[i]) for i in chosen]);existing=[obj for obj in scene.objects if obj.type=='MESH' and obj.get('object_id')];fg_vertices=np.array([list(obj.matrix_world@v.co) for obj in existing for v in obj.data.vertices]);limits=np.concatenate([table_points[:,:2],fg_vertices[:,:2]]);lo=limits.min(axis=0);hi=limits.max(axis=0);margin=.03*max(hi-lo);lo-=margin;hi+=margin;table=bpy.data.objects['desk_support'];table.location=(*((lo+hi)/2),-.025);table.scale=(1,1,1);table.dimensions=(*(hi-lo),.05)
    before_fg={obj.name:[list(obj.matrix_world@v.co) for v in obj.data.vertices] for obj in existing};bpy.context.view_layer.update();after_fg={obj.name:[list(obj.matrix_world@v.co) for v in obj.data.vertices] for obj in existing}
    if before_fg!=after_fg or any(abs(old_cam[i][j]-cam.matrix_world[i][j])>1e-10 for i in range(4) for j in range(4)):raise ValueError('Foreground or source camera changed')
    scene.render.resolution_x=1280;scene.render.resolution_y=720;bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'scene.blend'));receipt={'status':'saved','parent_model_sha256':sha(a.input/'scene.blend'),'model_sha256':sha(a.output/'scene.blend'),'extension_sha256':sha(a.phase),'script_sha256':sha(__file__),'source_sha256':sha(a.source),'foreground_and_source_camera_unchanged':True,'boundary_samples':len(boundaries),'world_wall_line_center':center.tolist(),'world_wall_direction':direction.tolist(),'support_extent':(hi-lo).tolist(),'renders':[],'scope':'Background feedback only; source point/camera model and all foreground meshes preserved'};save(a.output/'receipt.json',receipt)
    scene.render.filepath=str(a.output/'source_view.png');t=time.monotonic();bpy.ops.render.render(write_still=True);receipt['renders'].append({'kind':'source','sha256':sha(a.output/'source_view.png'),'wall_seconds':time.monotonic()-t})
    bounds=[fg_vertices.min(axis=0),fg_vertices.max(axis=0)];target=Vector((bounds[0]+bounds[1])/2);span=max(.3,float(np.linalg.norm(bounds[1]-bounds[0])));cam.location=target+Vector((.65,-.8,.7))*span;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=38;scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.filepath=str(a.output/'virtual_inspection.png');t=time.monotonic();bpy.ops.render.render(write_still=True);receipt['renders'].append({'kind':'virtual_display_only','sha256':sha(a.output/'virtual_inspection.png'),'wall_seconds':time.monotonic()-t});receipt.update(status='rendered',wall_seconds=time.monotonic()-started);save(a.output/'receipt.json',receipt);print(json.dumps({'status':'rendered','wall_seconds':receipt['wall_seconds'],'foreground_and_camera_unchanged':True}))

if __name__=='__main__':main()
