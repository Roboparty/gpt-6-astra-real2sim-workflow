"""GPT-authored static adapter for the published MoGe3 + RGB-instance route.

Consumes only new predicted geometry, original RGB and labelled manual masks.
It does not load any previous Desk1 scene, camera, pose or dimension fit.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import bpy
import numpy as np
from mathutils import Matrix,Vector

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False))
def image_array(path):
    image=bpy.data.images.load(str(path),check_existing=False);w,h=image.size
    values=np.empty(w*h*4,np.float32);image.pixels.foreach_get(values)
    return np.flipud(values.reshape(h,w,4))
def plain(name,color):
    material=bpy.data.materials.new(name);material.use_nodes=True;node=material.node_tree.nodes.get('Principled BSDF');node.inputs['Base Color'].default_value=(*map(float,color),1);node.inputs['Roughness'].default_value=.8;return material
def projected(name,image,origin,camera,R,fx,fy,W,H):
    material=bpy.data.materials.new(name);material.use_nodes=True;tree=material.node_tree;n=tree.nodes;n.clear()
    coord=n.new('ShaderNodeTexCoord');offset=n.new('ShaderNodeVectorMath');offset.operation='ADD';offset.inputs[1].default_value=Vector(origin)-Vector(camera);tree.links.new(coord.outputs['Object'],offset.inputs[0])
    dots=[]
    for j in range(3):
        dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=R[:,j];tree.links.new(offset.outputs['Vector'],dot.inputs[0]);dots.append(dot)
    uv=[]
    for j,factor in [(0,fx/W),(1,-fy/H)]:
        div=n.new('ShaderNodeMath');div.operation='DIVIDE';tree.links.new(dots[j].outputs['Value'],div.inputs[0]);tree.links.new(dots[2].outputs['Value'],div.inputs[1]);mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY_ADD';mul.inputs[1].default_value=factor;mul.inputs[2].default_value=.5;tree.links.new(div.outputs[0],mul.inputs[0]);uv.append(mul)
    combine=n.new('ShaderNodeCombineXYZ');tree.links.new(uv[0].outputs[0],combine.inputs[0]);tree.links.new(uv[1].outputs[0],combine.inputs[1]);tex=n.new('ShaderNodeTexImage');tex.image=image;tex.extension='EXTEND';tree.links.new(combine.outputs[0],tex.inputs['Vector'])
    diffuse=n.new('ShaderNodeBsdfPrincipled');diffuse.inputs['Roughness'].default_value=.8;tree.links.new(tex.outputs['Color'],diffuse.inputs['Base Color']);emission=n.new('ShaderNodeEmission');emission.inputs['Strength'].default_value=1;tree.links.new(tex.outputs['Color'],emission.inputs['Color']);mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=.78;tree.links.new(diffuse.outputs[0],mix.inputs[1]);tree.links.new(emission.outputs[0],mix.inputs[2]);out=n.new('ShaderNodeOutputMaterial');tree.links.new(mix.outputs[0],out.inputs['Surface']);return material
def hull(points):
    values=sorted(set(map(tuple,np.asarray(points,float))))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[]
    for p in values:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(values):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return np.asarray(lower[:-1]+upper[:-1])
def rectangle(points):
    points=np.asarray(points);center=np.median(points,axis=0);distance=np.linalg.norm(points-center,axis=1);points=points[distance<=np.percentile(distance,99)]
    boundary=hull(points);best=None
    for p,q in zip(boundary,np.roll(boundary,-1,axis=0)):
        e=q-p
        if np.linalg.norm(e)<1e-8:continue
        x=e/np.linalg.norm(e);y=np.array([-x[1],x[0]]);R=np.stack([x,y],axis=1);coordinates=points@R
        lo,hi=np.percentile(coordinates,[1,99],axis=0);size=hi-lo;area=float(np.prod(size))
        if best is None or area<best[0]:best=(area,((lo+hi)/2)@R.T,size,R)
    if best is None:raise ValueError('Instance cloud does not define a rectangle')
    return best[1:]
def table_plane(points):
    rng=np.random.default_rng(2026);points=np.asarray(points);points=points[rng.choice(len(points),min(len(points),6000),replace=False)];scale=np.median(np.linalg.norm(points,axis=1));tolerance=max(.002,scale*.004);best=[]
    for _ in range(300):
        p=points[rng.choice(len(points),3,replace=False)];n=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(n)
        if length<1e-8:continue
        n/=length;d=-n@p[0];chosen=np.abs(points@n+d)<tolerance
        if int(chosen.sum())>len(best):best=np.flatnonzero(chosen)
    if len(best)<100:raise ValueError('Source table plane reference insufficient')
    selected=points[best];center=np.mean(selected,axis=0);_,_,V=np.linalg.svd(selected-center,full_matrices=False);n=V[-1];d=-n@center
    if d<0:n=-n;d=-d
    return n,float(d),{'inliers':len(best),'sampled_points':len(points),'tolerance_model_m':tolerance,'rmse_model_m':float(np.sqrt(np.mean((selected@n+d)**2)))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--mask-directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reference-kind',choices=['moge3_metric_estimate','pi3x_relative'],default='moge3_metric_estimate');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(a.phase.read_text());a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    if sha(cfg['source_image'])!=cfg['source_sha256']:raise ValueError('Original RGB changed')
    data=np.load(a.reference/'prediction.npz');points=data['points'];depth=data['depth'];valid=data['mask'].astype(bool)&np.isfinite(points).all(axis=-1)&(depth>0);H,W=depth.shape;K=data['intrinsics'];fx,fy=K[0,0]*W,K[1,1]*H
    if abs(K[0,2]-.5)>1e-4 or abs(K[1,2]-.5)>1e-4:raise ValueError('Adapter requires centred intrinsics; do not silently change the predicted camera')
    rgb=image_array(a.reference/'input.png')[...,:3];masks={};mask_bindings=[]
    for key in ['domino_sugar_box','chocolate_jello_box','red_jello_box','expo_marker']:
        path=a.mask_directory/(key+'_mask.png');raw=image_array(path)[...,0];ys=np.minimum((np.arange(H)+.5)*raw.shape[0]/H,raw.shape[0]-1).astype(int);xs=np.minimum((np.arange(W)+.5)*raw.shape[1]/W,raw.shape[1]-1).astype(int);masks[key]=raw[ys[:,None],xs[None,:]]>.5;mask_bindings.append({'object_id':key,'sha256':sha(path),'origin':'prior source-image manual polygon, not SAM'})
    yy,xx=np.mgrid[:H,:W];foreground=np.logical_or.reduce(list(masks.values()));table_selection=valid&~foreground&(yy>.54*H)&(rgb.mean(axis=-1)<.22)
    if table_selection.sum()<100:raise ValueError('Too few visible table pixels')
    normal,height,plane_evidence=table_plane(points[table_selection]);x=np.array([1.,0,0]);x=x-normal*(x@normal);x/=np.linalg.norm(x);y=np.cross(normal,x);R=np.stack([x,y,normal]);camera=np.array([0,-.65,height]);world=points@R.T+camera;scale_info={'kind':a.reference_kind,'factor':1.,'status':'MoGe model metric estimate, not independently measured'}
    if a.reference_kind=='pi3x_relative':
        estimated=float(np.percentile(world[valid&masks['domino_sugar_box'],2],98))
        if estimated<=0:raise ValueError('Relative sugar height cannot anchor scale')
        factor=.175/estimated;world*=factor;camera*=factor;shift=np.array([0,-.65-camera[1],0]);world+=shift;camera+=shift;scale_info={'kind':a.reference_kind,'factor':factor,'status':'assumed historical family sugar-height anchor0.175m, not recovered true scale'}
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC';source=bpy.data.images.load(cfg['source_image']);source.pack();objects=[];decisions=[]
    for key in ['domino_sugar_box','chocolate_jello_box','red_jello_box']:
        selected=valid&masks[key];cloud=world[selected]
        if len(cloud)<100:raise ValueError('Missing instance points: '+key)
        center,size,axes=rectangle(cloud[:,:2]);top=float(np.percentile(cloud[:,2],98));top=max(top,.003)
        # Full supported cuboid completion; RGB identifies carton category, depth guides size/pose.
        w,d=size;local=np.array([[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]]);xy=local@axes.T+center;verts=np.concatenate([np.c_[xy,np.zeros(4)],np.c_[xy,np.full(4,top)]]);origin=verts.mean(axis=0)
        mesh=bpy.data.meshes.new(key+'_closed_carton');mesh.from_pydata((verts-origin).tolist(),[],[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]);mesh.update();obj=bpy.data.objects.new(key,mesh);scene.collection.objects.link(obj);obj.location=origin;obj.data.materials.append(plain(key+'_hidden_prior',(.5,.5,.5)));obj.data.materials.append(projected(key+'_source_photo',source,origin,camera,R,fx,fy,W,H))
        for face in obj.data.polygons:face.material_index=1 if Vector(face.normal).dot(Vector(camera-origin))>0 else 0
        bevel=obj.modifiers.new('paper_edge_softness','BEVEL');bevel.width=.0003;bevel.segments=2;obj['object_id']=key;objects.append(obj)
        decisions.append({'object_id':key,'reference_points':len(cloud),'dimensions_m_estimated':[float(w),float(d),top],'center_xy':center.tolist(),'support':'assumed on inferred table plane','hidden_completion':'orthogonal carton, unknown back/bottom details','prior_scale':scale_info['status']})
    cloud=world[valid&masks['expo_marker']]
    if len(cloud)<100:raise ValueError('Missing marker points')
    centered=cloud[:,:2]-np.median(cloud[:,:2],axis=0);_,_,V=np.linalg.svd(centered,full_matrices=False);axis=V[0];coordinate=cloud[:,:2]@axis;lo,hi=np.percentile(coordinate,[1,99]);cross=np.array([-axis[1],axis[0]]);offset=np.median(cloud[:,:2]@cross);radius=max(.002,float(np.percentile(cloud[:,2],98)/2));start=np.r_[axis*lo+cross*offset,radius];end=np.r_[axis*hi+cross*offset,radius]
    colors=rgb[valid&masks['expo_marker']];black=colors.mean(axis=1)<.2
    if black.sum() and np.median(coordinate[black])>(lo+hi)/2:start,end=end,start
    delta=end-start;length=np.linalg.norm(delta);direction=Vector(delta).normalized()
    for name,low,high,r,color in [('black_cap',0,.23,1.,(.005,.005,.006)),('white_barrel',.23,.95,.92,(.82,.82,.79)),('white_end_plug',.95,1.02,.92,(.88,.88,.84))]:
        center=start+(low+high)/2*delta;bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius*r,depth=length*(high-low),location=center);obj=bpy.context.object;obj.name='expo_'+name;obj.rotation_euler=direction.to_track_quat('Z','Y').to_euler();bpy.ops.object.transform_apply(location=False,rotation=True,scale=True);obj.data.materials.append(plain(obj.name+'_hidden',color));obj.data.materials.append(projected(obj.name+'_source_photo',source,center,camera,R,fx,fy,W,H))
        for face in obj.data.polygons:face.material_index=1 if Vector(face.normal).dot(Vector(camera-center))>0 else 0;face.use_smooth=abs(face.normal.dot(direction))<.9
        obj['object_id']='expo_marker';objects.append(obj)
    decisions.append({'object_id':'expo_marker','reference_points':len(cloud),'radius_m_estimated':radius,'length_m_estimated':float(length),'hidden_completion':'three cylinder sections; cap ratios assumed from visible RGB, not manufacturer specification'})
    table_world=world[table_selection];lo=np.percentile(table_world[:,:2],1,axis=0);hi=np.percentile(table_world[:,:2],99,axis=0);center=(lo+hi)/2;dimensions=np.maximum(hi-lo,.5)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(*center,-.025));table=bpy.context.object;table.name='desk_support';table.dimensions=(*dimensions,.05);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);table.data.materials.append(plain('desk_charcoal',(.015,.015,.018)))
    wall_pixels=valid&~foreground&(yy<.4*H);wall_cloud=world[wall_pixels];wall_y=float(np.median(wall_cloud[:,1]));bpy.ops.mesh.primitive_cube_add(size=1,location=(0,wall_y,1.5));wall=bpy.context.object;wall.name='plain_back_wall';wall.dimensions=(4,.02,3);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);wall.data.materials.append(plain('wall_neutral',(.413,.413,.404)))
    camdata=bpy.data.cameras.new('source_moge_camera');cam=bpy.data.objects.new(camdata.name,camdata);scene.collection.objects.link(cam);M=np.eye(4);M[:3,:3]=R@np.diag([1,-1,-1]);M[:3,3]=camera;cam.matrix_world=Matrix(M.tolist());camdata.sensor_fit='HORIZONTAL';camdata.sensor_width=36;camdata.lens=float(fx*36/W);camdata.clip_start=.01;camdata.clip_end=100;scene.camera=cam
    scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=float(fx/fy);scene.world=bpy.data.worlds.new('neutral_world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55;light=bpy.data.lights.new('softbox','AREA');light.energy=35;light.shape='DISK';light.size=1.2;lamp=bpy.data.objects.new(light.name,light);scene.collection.objects.link(lamp);lamp.location=(-.15,-.4,1)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.seed=0;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=2;scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene['method']='GPT6-peer geometry-reference adaptation, '+a.reference_kind+'; not independent Astra/original-framework reproduction';scene['source_sha256']=cfg['source_sha256'];bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'scene.blend'))
    from bpy_extras.object_utils import world_to_camera_view
    inventory=[]
    for obj in objects:
        verts=[obj.matrix_world@v.co for v in obj.data.vertices];pixels=[]
        for v in verts:uv=world_to_camera_view(scene,cam,v);pixels.append([float(uv.x*1280),float((1-uv.y)*720)])
        inventory.append({'name':obj.name,'object_id':obj['object_id'],'vertices_world':[list(v) for v in verts],'projected_vertices_1280':pixels,'faces':[list(f.vertices) for f in obj.data.polygons]})
    save(a.output/'objects.json',inventory);receipt={'status':'model_saved','source_sha256':cfg['source_sha256'],'phase_sha256':sha(a.phase),'reference_sha256':sha(a.reference/'prediction.npz'),'script_sha256':sha(__file__),'model_sha256':sha(a.output/'scene.blend'),'masks':mask_bindings,'reference_kind':a.reference_kind,'scale':scale_info,'camera':{'position':camera.tolist(),'optical_rotation_to_world':R.tolist(),'fx_px':float(fx),'fy_px':float(fy),'K_normalized':K.tolist()},'table_plane':plane_evidence,'decisions':decisions,'expected_objects':4,'semantic_objects':4,'foreground_parts':6,'renders':[],'scope':'static workflow adaptation; no exact GPT6Astra version confirmation, no independent3D/physics/true novelview quality'};save(a.output/'receipt.json',receipt)
    scene.render.filepath=str(a.output/'source_view.png');t=time.monotonic();bpy.ops.render.render(write_still=True);receipt['renders'].append({'kind':'source','sha256':sha(a.output/'source_view.png'),'wall_seconds':time.monotonic()-t})
    all_vertices=np.array([v for item in inventory for v in item['vertices_world']]);bounds=[all_vertices.min(axis=0),all_vertices.max(axis=0)];target=Vector((bounds[0]+bounds[1])/2);span=max(.3,float(np.linalg.norm(bounds[1]-bounds[0])));cam.location=target+Vector((.65,-.8,.7))*span;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.lens=38;scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.filepath=str(a.output/'virtual_inspection.png');t=time.monotonic();bpy.ops.render.render(write_still=True);receipt['renders'].append({'kind':'virtual_no_real_reference','camera_scope':'display view fitted to candidate bounds; not a matched real or old-world camera','sha256':sha(a.output/'virtual_inspection.png'),'wall_seconds':time.monotonic()-t});receipt.update(status='rendered',wall_seconds=time.monotonic()-started,source_unchanged=sha(cfg['source_image'])==cfg['source_sha256']);save(a.output/'receipt.json',receipt);print(json.dumps({'status':receipt['status'],'expected_objects':4,'objects':4,'wall_seconds':receipt['wall_seconds']}))

if __name__=='__main__':main()
