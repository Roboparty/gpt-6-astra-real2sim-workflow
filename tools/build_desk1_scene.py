"""Editable single-image Desk1 authoring; no external models or GT assets.

Visible texture projection is object-local and fixed, not a whole-image billboard.
Closed meshes have explicitly assumed thickness, camera and unseen surfaces.
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


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False))


def plain(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.8;m['prior_status']='assumed';return m


def project_material(name,image,origin,camera,R,fx,fy,W,H):
    """Project the sole source photo in fixed object-local coordinates.

    Textures remain attached when the object moves; hidden faces use plain priors.
    Captured illumination is retained, so this is not recovered intrinsic albedo.
    """
    m=bpy.data.materials.new(name);m.use_nodes=True;tree=m.node_tree;nodes=tree.nodes;nodes.clear()
    coord=nodes.new('ShaderNodeTexCoord');offset=nodes.new('ShaderNodeVectorMath');offset.operation='ADD'
    offset.inputs[1].default_value=Vector(origin)-Vector(camera);tree.links.new(coord.outputs['Object'],offset.inputs[0])
    dots=[]
    for j in range(3):
        n=nodes.new('ShaderNodeVectorMath');n.operation='DOT_PRODUCT';n.inputs[1].default_value=R[:,j];tree.links.new(offset.outputs['Vector'],n.inputs[0]);dots.append(n)
    values=[]
    for j,factor,bias in [(0,fx/W,.5),(1,-fy/H,.5)]:
        div=nodes.new('ShaderNodeMath');div.operation='DIVIDE';tree.links.new(dots[j].outputs['Value'],div.inputs[0]);tree.links.new(dots[2].outputs['Value'],div.inputs[1])
        mul=nodes.new('ShaderNodeMath');mul.operation='MULTIPLY_ADD';mul.inputs[1].default_value=factor;mul.inputs[2].default_value=bias;tree.links.new(div.outputs[0],mul.inputs[0]);values.append(mul)
    combine=nodes.new('ShaderNodeCombineXYZ');tree.links.new(values[0].outputs[0],combine.inputs[0]);tree.links.new(values[1].outputs[0],combine.inputs[1])
    tex=nodes.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';tex.extension='EXTEND';tree.links.new(combine.outputs[0],tex.inputs['Vector'])
    diffuse=nodes.new('ShaderNodeBsdfPrincipled');diffuse.inputs['Roughness'].default_value=.8;tree.links.new(tex.outputs['Color'],diffuse.inputs['Base Color'])
    em=nodes.new('ShaderNodeEmission');em.inputs['Strength'].default_value=1;tree.links.new(tex.outputs['Color'],em.inputs['Color'])
    mix=nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.78;tree.links.new(diffuse.outputs[0],mix.inputs[1]);tree.links.new(em.outputs[0],mix.inputs[2])
    out=nodes.new('ShaderNodeOutputMaterial');tree.links.new(mix.outputs[0],out.inputs['Surface'])
    m['texture_source']='single real input; visible appearance includes baked illumination';return m


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(a.protocol.read_text());a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    assert sha(cfg['source_image'])==cfg['source_sha256']
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.unit_settings.system='METRIC'
    W,H=1920,1080;fx=fy=cfg['camera']['focal_px'];alpha=math.radians(cfg['camera']['down_pitch_deg']);roll=math.radians(cfg['camera']['roll_deg'])
    R0=np.array([[1,0,0],[0,-math.sin(alpha),math.cos(alpha)],[0,-math.cos(alpha),-math.sin(alpha)]])
    rz=np.array([[math.cos(roll),-math.sin(roll),0],[math.sin(roll),math.cos(roll),0],[0,0,1]])
    R=R0@rz;camera=np.array(cfg['camera']['position'],float)
    def unproject(pixel,z):
        u,v=np.array(pixel)*1.5;ray=R@np.array([(u-W/2)/fx,(v-H/2)/fy,1.]);return camera+ray*((z-camera[2])/ray[2])
    image=bpy.data.images.load(cfg['source_image']);image.pack()
    objects=[]
    for spec in cfg['boxes']:
        name=spec['id'];top=np.array([unproject(p,spec['height_assumed_m']) for p in spec['top_front_order']]);bottom=[]
        # Three directly visible base corners, fourth completed from top-face offsets.
        known={int(k):unproject(v,0) for k,v in spec['bottom_pixels'].items()}
        translation=np.mean([known[i]-top[i] for i in known],axis=0)
        for i in range(4):
            b=known.get(i,top[i]+translation);b[2]=0;bottom.append(b)
        vertices=np.concatenate([bottom,top]);origin=vertices.mean(axis=0)
        faces=[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]
        mesh=bpy.data.meshes.new(name+'_closed_mesh');mesh.from_pydata((vertices-origin).tolist(),[],faces);mesh.update()
        obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj);obj.location=origin
        obj.data.materials.append(plain(name+'_unobserved_prior',spec['hidden_color_linear']))
        obj.data.materials.append(project_material(name+'_visible_photo_texture',image,origin,camera,R,fx,fy,W,H))
        for face in obj.data.polygons:face.material_index=1 if face.index in spec['visible_faces'] else 0
        bevel=obj.modifiers.new('paper_edge_softness','BEVEL');bevel.width=.0003;bevel.segments=2
        obj['object_id']=name;obj['geometry_origin']='visible manually annotated image corners; assumed-height ray intersections; unseen corner completed'
        obj['scale_status']='assumed';obj['closed_surface']=True;obj['source_sha256']=cfg['source_sha256'];objects.append(obj)
    # Marker assembled as closed cylindrical sections. No visible bare nib invented.
    marker=cfg['marker'];left=unproject(marker['axis_pixels'][0],marker['radius_assumed_m']);right=unproject(marker['axis_pixels'][1],marker['radius_assumed_m']);axis=right-left;length=np.linalg.norm(axis);direction=Vector(axis).normalized()
    for name,lo,hi,radius,color in [('black_cap',0,.23,1.,(.005,.005,.006)),('white_barrel',.23,.95,.92,(.82,.82,.79)),('white_end_plug',.95,1.02,.92,(.88,.88,.84))]:
        center=left+(lo+hi)/2*axis
        bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=marker['radius_assumed_m']*radius,depth=length*(hi-lo),location=center)
        obj=bpy.context.object;obj.name='expo_'+name;obj.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
        # Bake only orientation so local projection coordinates remain in world axes.
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        obj.data.materials.append(plain(obj.name+'_hidden_prior',color));obj.data.materials.append(project_material(obj.name+'_visible_texture',image,center,camera,R,fx,fy,W,H))
        for face in obj.data.polygons:
            face.material_index=1 if Vector(face.normal).dot(Vector(camera-center))>0 else 0
            face.use_smooth=abs(face.normal.dot(direction))<.9
        bevel=obj.modifiers.new('cap_edge','BEVEL');bevel.width=.0005;bevel.segments=3
        obj['object_id']='expo_marker';obj['part_id']=name;obj['scale_status']='assumed';objects.append(obj)
    # Neutral scene support, not a photo billboard. Its unseen extent is arbitrary.
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.39,-.025));table=bpy.context.object;table.name='desk_support';table.dimensions=(1.40,.88,.05);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);table.data.materials.append(plain('desk_charcoal',cfg.get('desk_color',(.058,.061,.068))))
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,.014,.72));wall=bpy.context.object;wall.name='plain_back_wall';wall.dimensions=(2.0,.02,1.44);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);wall.data.materials.append(plain('wall_neutral',cfg.get('wall_color',(.59,.59,.575))))
    data=bpy.data.cameras.new('source_assumed_camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam)
    M=np.eye(4);M[:3,:3]=R@np.diag([1,-1,-1]);M[:3,3]=camera;cam.matrix_world=Matrix(M.tolist());data.sensor_fit='HORIZONTAL';data.sensor_width=36;data.lens=fx*36/W;data.clip_start=.01;data.clip_end=20;scene.camera=cam
    cam['calibration_status']='single-view assumption, not a calibrated or learned camera estimate'
    scene.world=bpy.data.worlds.new('neutral_world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
    light=bpy.data.lights.new('softbox','AREA');light.energy=35;light.shape='DISK';light.size=1.2;lo=bpy.data.objects.new(light.name,light);scene.collection.objects.link(lo);lo.location=(-.15,-.4,1.0)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=cfg['samples'];scene.cycles.use_denoising=True;scene.cycles.seed=0;scene.render.threads_mode='FIXED';scene.render.threads=2
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=0
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene['source_case']='SimFoundry YCB Desk1/Easy';scene['modeling_input_count']=1;scene['scope']='Editable single-view appearance fit with assumed camera/depth; not ground-truth 3D recovery'
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'scene.blend'))
    inventory=[dict(name=o.name,object_id=o.get('object_id'),dimensions=list(o.dimensions),vertex_count=len(o.data.vertices),face_count=len(o.data.polygons)) for o in objects]
    save(a.output/'objects.json',inventory)
    receipt=dict(status='model_frozen_before_comparators',source_sha256=cfg['source_sha256'],protocol_sha256=sha(a.protocol),script_sha256=sha(__file__),model_sha256=sha(a.output/'scene.blend'),editable_object_count=4,foreground_mesh_parts=len(objects),camera_assumed=cfg['camera'],comparison_images_used_for_modeling=False,renders=[])
    save(a.output/'receipt.json',receipt)
    scene.render.filepath=str(a.output/'source_view.png');t=time.monotonic();bpy.ops.render.render(write_still=True)
    receipt['renders'].append(dict(kind='source_corresponding_assumed_camera',path=str(a.output/'source_view.png'),sha256=sha(a.output/'source_view.png'),wall_seconds=time.monotonic()-t))
    # A plainly labelled virtual inspection, never a second real observation.
    original=cam.matrix_world.copy();cam.location=Vector((.38,-.56,.51));target=Vector((-.025,-.16,.07));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();data.lens=38
    scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.filepath=str(a.output/'virtual_inspection.png');t=time.monotonic();bpy.ops.render.render(write_still=True)
    receipt['renders'].append(dict(kind='virtual_only_no_real_reference',path=str(a.output/'virtual_inspection.png'),sha256=sha(a.output/'virtual_inspection.png'),wall_seconds=time.monotonic()-t))
    receipt.update(status='rendered',wall_seconds=time.monotonic()-started,source_unchanged=sha(cfg['source_image'])==cfg['source_sha256'])
    save(a.output/'receipt.json',receipt);print(json.dumps(receipt))


if __name__=='__main__':main()
