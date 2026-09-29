"""Bake one registered floor normal candidate in Blender; no source edits/rendering.

blender -b -t 2 --python-exit-code 12 -P tools/bake_floor_normal_candidate.py
  -- --protocol /registered.json --output /new-directory
Dependencies: Blender's bpy/numpy and sibling apply_appearance_candidate.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from apply_appearance_candidate import file_sha,object_snapshot,digest


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')


def mesh_signature(mesh,uv_names):
    sha=hashlib.sha256()
    for collection,field,width,dtype in [(mesh.vertices,'co',3,np.float32),(mesh.edges,'vertices',2,np.int32),
        (mesh.loops,'vertex_index',1,np.int32),(mesh.polygons,'loop_start',1,np.int32),
        (mesh.polygons,'loop_total',1,np.int32),(mesh.polygons,'material_index',1,np.int32)]:
        values=np.empty(len(collection)*width,dtype=dtype);collection.foreach_get(field,values);sha.update(values.tobytes())
    for name in uv_names:
        layer=mesh.uv_layers[name];values=np.empty(len(layer.data)*2,dtype=np.float32)
        layer.data.foreach_get('uv',values);sha.update(name.encode());sha.update(values.tobytes())
    return sha.hexdigest()


def node_values(nodes):
    result={}
    for node in nodes:
        sockets=[]
        for socket in node.inputs:
            if not hasattr(socket,'default_value'):continue
            value=socket.default_value
            if not isinstance(value,(float,int,bool,str)):value=list(value)
            sockets.append([socket.identifier,value])
        result[node.name]=dict(type=node.bl_idname,inputs=sockets,
            image=node.image.name if hasattr(node,'image') and node.image else None)
    return result


def links(tree):
    return sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in tree.links)


def image_pixel_sha(image):
    values=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(values)
    return hashlib.sha256(values.tobytes()).hexdigest()


def coverage(mesh,layer,resolution):
    uv=np.empty(len(layer.data)*2,np.float32);layer.data.foreach_get('uv',uv);uv=uv.reshape(-1,2)
    if not np.isfinite(uv).all() or uv.min() < -1e-6 or uv.max() > 1+1e-6:raise ValueError('Bake UVs are not finite/in [0,1]')
    occupied=np.zeros((resolution,resolution),bool);mesh.calc_loop_triangles();area=0.
    for tri in mesh.loop_triangles:
        points=uv[list(tri.loops)]*resolution;a,b,c=points
        cross=lambda u,v:u[...,0]*v[...,1]-u[...,1]*v[...,0]
        signed=float(cross(b-a,c-a));area+=abs(signed)/2/resolution**2
        if abs(signed)<1e-9:continue
        lo=np.maximum(0,np.floor(points.min(axis=0)).astype(int));hi=np.minimum(resolution,np.ceil(points.max(axis=0)).astype(int))
        yy,xx=np.mgrid[lo[1]:hi[1],lo[0]:hi[0]];p=np.stack((xx+.5,yy+.5),axis=-1)
        w1=cross(b-a,p-a)/signed;w2=cross(p-a,c-a)/signed
        occupied[lo[1]:hi[1],lo[0]:hi[0]]|=(w1>=-1e-6)&(w2>=-1e-6)&(w1+w2<=1+1e-6)
    if not occupied.any():raise ValueError('No rasterized UV coverage')
    return occupied,dict(uv_min=uv.min(axis=0).tolist(),uv_max=uv.max(axis=0).tolist(),
        triangle_area_sum=area,pixel_center_coverage=int(occupied.sum()),coverage_fraction=float(occupied.mean()),
        interpretation='Union of base-mesh UV triangles at bake pixel centers; no margin pixels included')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);protocol=json.loads(args.protocol.read_text(encoding='utf-8-sig'))
    expected=dict(resolution=2048,samples=1,margin=16,normal_space='TANGENT',uv_name='PortableFloorNormalUV',
                  smart_project_angle_limit=1.1519173063162575,smart_project_island_margin=.03)
    if protocol.get('bake')!=expected:raise ValueError('Only the registered fixed 2048/1/16/TANGENT bake is supported')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    source_model=Path(protocol['source_model']);source_scene=Path(protocol['source_scene'])
    receipt=dict(schema='real2sim.floor-normal-bake/1',status='started',protocol_sha256=file_sha(args.protocol),
        script_sha256=file_sha(__file__),helper_sha256=file_sha(Path(__file__).with_name('apply_appearance_candidate.py')),bake=expected,
        source_model_sha256=file_sha(source_model),source_scene_sha256=file_sha(source_scene))
    write(output/'receipt.json',receipt)
    def disk_guard(stage):
        free=shutil.disk_usage(output).free
        receipt.setdefault('disk_checks',[]).append(dict(stage=stage,free_bytes=free,reserve_bytes=4*1024**3))
        if free<4*1024**3:raise ValueError('Less than 4 GiB free disk before '+stage)
    try:
        for key in ['source_model_sha256','source_scene_sha256']:
            if receipt[key]!=protocol[key]:raise ValueError('Frozen source hash mismatch: '+key)
        bpy.ops.wm.open_mainfile(filepath=str(source_model));scene=bpy.context.scene
        owned=[o for o in scene.objects if o.get('entity_id',o.get('furniture_id',o.name))=='floor' and o.type in {'MESH','CURVE','SURFACE','FONT','META'}]
        if len(owned)!=1 or owned[0].type!='MESH':raise ValueError('Expected exactly one floor-owned mesh')
        obj=owned[0]
        if obj.hide_render or len(obj.material_slots)!=1 or obj.material_slots[0].link!='DATA':raise ValueError('Expected visible floor with one data-linked material')
        original=obj.material_slots[0].material
        if not original or original.name!='carpet_greytaupe' or not original.use_nodes:raise ValueError('Unsupported floor material')
        if not obj.data.uv_layers.active or expected['uv_name'] in obj.data.uv_layers:raise ValueError('Missing old UV or candidate already applied')
        before=object_snapshot(scene);uv_names={o.name:[u.name for u in o.data.uv_layers] for o in scene.objects if o.type=='MESH'}
        geometry={o.name:mesh_signature(o.data,uv_names[o.name]) for o in scene.objects if o.type=='MESH'}
        image_states={i.name:(i.colorspace_settings.name,i.filepath,tuple(i.size)) for i in bpy.data.images}
        old_uv=obj.data.uv_layers.active.name;old_render_uv=next((u.name for u in obj.data.uv_layers if u.active_render),old_uv)
        obj.data=obj.data.copy();obj.data.name+='__floor_normal_private'
        material=original.copy();material.name+='__floor_normal_private';obj.data.materials[0]=material
        tree=material.node_tree;original_nodes=list(tree.nodes);values_before=node_values(original_nodes);links_before=links(tree)
        principled=[n for n in tree.nodes if n.type=='BSDF_PRINCIPLED']
        if len(principled)!=1:raise ValueError('Expected one Principled shader')
        shader=principled[0];normal_links=list(shader.inputs['Normal'].links)
        if len(normal_links)!=1 or normal_links[0].from_node.type!='BUMP':raise ValueError('Expected original Bump -> Principled Normal')
        color_links=list(shader.inputs['Base Color'].links)
        if len(color_links)!=1 or color_links[0].from_node.type!='TEX_IMAGE':raise ValueError('Expected direct color image')
        color_node=color_links[0].from_node;color_image=color_node.image
        if color_image is None or color_image.colorspace_settings.name!='sRGB':raise ValueError('Expected original sRGB color image')
        color_pixels_before=image_pixel_sha(color_image)
        if len(color_node.inputs['Vector'].links)!=1 or color_node.inputs['Vector'].links[0].from_node.type!='UVMAP':raise ValueError('Expected explicit UVMap -> color image')
        # Pin implicit UVMap nodes before switching render-active UV. Do not
        # change any shared image color space or the old UV coordinates.
        pinned=[]
        for node in original_nodes:
            if node.type=='UVMAP' and not node.uv_map:node.uv_map=old_uv;pinned.append(node.name)
            if node.type=='TEX_IMAGE' and not node.inputs['Vector'].is_linked:raise ValueError('Unsupported implicit image UV dependency')
            if node.type=='TEX_COORD' and node.outputs['UV'].is_linked:raise ValueError('Unsupported implicit Texture Coordinate UV dependency')
        layer=obj.data.uv_layers.new(name=expected['uv_name']);obj.data.uv_layers.active=layer;layer.active_render=True
        bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=1.1519173063162575,island_margin=.03)
        bpy.ops.object.mode_set(mode='OBJECT');layer=obj.data.uv_layers[expected['uv_name']];mask,uv_report=coverage(obj.data,layer,2048)
        image=bpy.data.images.new('PortableFloorNormal',width=2048,height=2048,alpha=True,float_buffer=False)
        image.colorspace_settings.name='Non-Color';image.generated_color=(0,0,0,0)
        texture=tree.nodes.new('ShaderNodeTexImage');texture.name='PortableFloorNormalTexture';texture.image=image
        for node in tree.nodes:node.select=False
        texture.select=True;tree.nodes.active=texture
        settings=(scene.render.engine,scene.cycles.device,scene.cycles.samples,scene.render.threads_mode,scene.render.threads)
        scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.render.threads_mode='FIXED';scene.render.threads=2
        # Bake target is active but unconnected: original Bump shading is intact.
        if links(tree)!=links_before:raise ValueError('Original shading changed before bake')
        disk_guard('bake')
        bake_started=time.monotonic()
        bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',
            use_selected_to_active=False,use_clear=True,margin=16,uv_layer=layer.name,target='IMAGE_TEXTURES')
        receipt['bake_wall_seconds']=time.monotonic()-bake_started
        scene.render.engine,scene.cycles.device,scene.cycles.samples,scene.render.threads_mode,scene.render.threads=settings
        pixels=np.empty(2048*2048*4,np.float32);image.pixels.foreach_get(pixels);pixels=pixels.reshape(2048,2048,4)
        visible=pixels[mask]
        if not np.isfinite(pixels).all() or not np.any(visible[:,:3]>0):raise ValueError('Normal bake is nonfinite or empty')
        receipt['pixels']=dict(finite=True,covered_pixel_count=len(visible),covered_rgb_min=visible[:,:3].min(axis=0).tolist(),
            covered_rgb_max=visible[:,:3].max(axis=0).tolist(),covered_alpha_min=float(visible[:,3].min()),
            covered_nonzero_rgb_fraction=float(np.any(visible[:,:3]>0,axis=1).mean()),raw_sha256=hashlib.sha256(pixels.tobytes()).hexdigest())
        if receipt['pixels']['covered_nonzero_rgb_fraction']<.99:raise ValueError('Normal bake coverage below the registered 99 percent gate')
        uv_node=tree.nodes.new('ShaderNodeUVMap');uv_node.uv_map=layer.name
        normal=tree.nodes.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.uv_map=layer.name
        tree.links.new(uv_node.outputs['UV'],texture.inputs['Vector']);tree.links.new(texture.outputs['Color'],normal.inputs['Color'])
        old_link=normal_links[0];removed=(old_link.from_node.name,old_link.from_socket.identifier,old_link.to_node.name,old_link.to_socket.identifier)
        tree.links.remove(old_link);tree.links.new(normal.outputs['Normal'],shader.inputs['Normal'])
        if node_values(original_nodes)!=values_before:raise ValueError('Original shader values/image bindings changed')
        original_names={n.name for n in original_nodes}
        retained=[l for l in links(tree) if l[0] in original_names and l[2] in original_names]
        if retained!=[l for l in links_before if l!=removed]:raise ValueError('Non-normal original shader links changed')
        after=object_snapshot(scene)
        for name,record in before.items():
            if name==obj.name:
                if any(record[k]!=after[name][k] for k in ['matrix_world','dimensions']):raise ValueError('Floor transform or dimensions changed')
            elif record!=after[name]:raise ValueError('Non-target object/material changed: '+name)
        for item in scene.objects:
            if item.type=='MESH' and mesh_signature(item.data,uv_names[item.name])!=geometry[item.name]:raise ValueError('Geometry or original UV changed: '+item.name)
        if any((bpy.data.images[n].colorspace_settings.name,bpy.data.images[n].filepath,tuple(bpy.data.images[n].size))!=v for n,v in image_states.items()):raise ValueError('Original image state changed')
        if color_node.image!=color_image or color_image.colorspace_settings.name!='sRGB':raise ValueError('Color image drift')
        if image_pixel_sha(color_image)!=color_pixels_before:raise ValueError('Original color pixels changed')
        disk_guard('save_png')
        image.filepath_raw=str(output/'floor_normal.png');image.file_format='PNG';image.save();image.pack()
        shutil.copyfile(source_scene,output/'scene.json')
        disk_guard('save_model')
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
        if file_sha(source_model)!=receipt['source_model_sha256'] or file_sha(source_scene)!=receipt['source_scene_sha256'] or file_sha(args.protocol)!=receipt['protocol_sha256']:raise ValueError('Source/protocol changed')
        receipt.update(status='completed',blender_version=bpy.app.version_string,target_object=obj.name,old_active_uv=old_uv,
            old_render_uv=old_render_uv,pinned_uv_nodes=pinned,uv_coverage=uv_report,
            invariants=dict(vertices_topology_old_uv_unchanged=True,transforms_unchanged=True,non_target_materials_unchanged=True,
                original_node_values_unchanged=True,original_color_image_and_srgb_unchanged=True,source_bytes_unchanged=True,
                original_geometry_sha256=digest(geometry),normal_image_packed=bool(image.packed_file)),
            output_hashes={name:file_sha(output/name) for name in ['model.blend','scene.json','floor_normal.png']},
            output_bytes={name:(output/name).stat().st_size for name in ['model.blend','scene.json','floor_normal.png']},
            original_color_pixels_sha256=color_pixels_before,
            scope='Tangent normal portability candidate; no physical-normal accuracy or appearance acceptance established')
    except Exception as exc:
        receipt.update(status='failed',error=repr(exc));raise
    finally:
        receipt['wall_seconds']=time.monotonic()-started;write(output/'receipt.json',receipt)


if __name__=='__main__':main()
