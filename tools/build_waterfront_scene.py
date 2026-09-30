"""Author an editable Waterfront bedroom from retained multi-view references.

Blender CPU entrypoint: -- --protocol JSON --output NEWDIR
No model inference or camera optimization. All unmeasured dimensions are assumed.
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
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).parent))
from waterfront_primitives import box,cushion,ellipsoid,build_furniture


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False))


def material(name,color,rough=.6,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
    m['prior_status']='assumed';return m


def tagged(obj,name,assembly):
    obj.name=name;obj['assembly']=assembly;obj['part_id']=name;obj['prior_status']='assumed';return obj


def cylinder(name,center,radius,depth,mat,assembly,rotation=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=radius,depth=depth,location=center,rotation=rotation)
    obj=tagged(bpy.context.object,name,assembly);obj.data.materials.append(mat)
    bevel=obj.modifiers.new('edge_softness','BEVEL');bevel.width=.006;bevel.segments=3
    return obj


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(a.protocol.read_text());a.output.mkdir(parents=True,exist_ok=False);t=time.monotonic()
    assert sha(cfg['npz'])==cfg['npz_sha256'];manifest=json.loads(Path(cfg['input_manifest']).read_text());assert sha(cfg['input_manifest'])==cfg['input_manifest_sha256']
    assert len(manifest['frames'])==6
    for f in manifest['frames']:assert sha(f['original_path'])==f['sha256']
    arrays=np.load(cfg['npz']);points=arrays['points'][0];poses=arrays['camera_poses'][0];rays=arrays['rays'][0]
    def point(f,u,v):
        x,y=min(669,round(u*.7)),min(375,round(v*.7))
        return np.median(points[f,max(0,y-2):y+3,max(0,x-2):x+3].reshape(-1,3),axis=0)
    up=point(0,552,96)-point(0,555,520);up/=np.linalg.norm(up)
    along=point(0,73,153)-point(0,358,117);along-=up*np.dot(along,up);along/=np.linalg.norm(along)
    cross=np.cross(along,up);Q=np.stack([cross,along,up]);origin=point(5,680,530)
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    mats={
        'wall':material('Warm white plaster',(0.77,.76,.71),.8),
        'white':material('Cotton white',(.82,.82,.78),.87),
        'cream':material('Ivory upholstery',(.60,.52,.39),.86),
        'dark':material('Charcoal cabinetry',(.028,.034,.033),.39),
        'wood':material('Dark oak',(.045,.036,.029),.67),
        'navy':material('Midnight blue textile',(.012,.021,.046),.94),
        'pink':material('Dusty rose pillows',(.42,.23,.19),.91),
        'rust':material('Rust accent',(.40,.12,.065),.86),
        'blue':material('Blue accent',(.045,.13,.21),.87),
        'brass':material('Brushed warm brass',(.50,.29,.085),.28,.78),
        'black':material('Black details',(.009,.012,.013),.43),
        'mirror':material('Smoky mirrored panel',(.40,.43,.43),.075,.94),
        'floor':material('Smoked timber floor',(.052,.053,.049),.51),
        'green':material('Broad leaves',(.022,.12,.025),.49),
        'pot':material('Dark planter',(.025,.028,.027),.61)}
    for name,values in cfg.get('material_overrides',{}).items():
        shader=mats[name].node_tree.nodes.get('Principled BSDF')
        if 'color' in values:shader.inputs['Base Color'].default_value=(*values['color'],1)
        if 'roughness' in values:shader.inputs['Roughness'].default_value=values['roughness']
    # Editable room envelope; unseen rear extent is a declared completion.
    box('room_floor',(-1,-.20,-.07),(5.5,6.9,.14),mats['floor'],assembly='room')
    box('room_ceiling',(-1,-.20,2.72),(5.5,6.9,.14),mats['wall'],assembly='room')
    box('room_left_wall',(-3.55,-.2,1.3),(.16,6.3,2.6),mats['wall'],assembly='room')
    box('room_rear_unobserved',(-1,-3.55,1.3),(5.1,.14,2.6),mats['wall'],assembly='room')
    box('headboard_dark_wall',(-3.455,.08,1.24),(.035,4.05,2.47),mats['wood'],assembly='room')
    # Right room wall split around observed doorway; no filling the opening.
    box('room_right_main',(1.50,.49,1.3),(.14,4.84,2.6),mats['wall'],assembly='room')
    box('door_lintel',(1.5,-2.65,2.48),(.14,1.05,.25),mats['wall'],assembly='doorway')
    box('door_rear_jamb',(1.5,-3.2,1.19),(.20,.09,2.4),mats['wall'],assembly='doorway')
    box('door_front_jamb',(1.46,-2.1,1.22),(.24,.12,2.44),mats['wall'],assembly='doorway')
    box('hall_backwall_assumed',(2.55,-2.65,1.2),(.10,1.0,2.4),mats['wall'],assembly='doorway')
    box('hall_floor_assumed',(2.0,-2.65,-.035),(1.2,1.05,.07),mats['wall'],assembly='doorway')
    # Window outer frame and individual mullions, preserving actual apertures.
    for name,center,size in [
        ('window_left_jamb',(-3.25,2.92,1.27),(.16,.15,2.55)),
        ('window_right_jamb',(1.4,2.92,1.27),(.16,.15,2.55)),
        ('window_header',(-.94,2.92,2.43),(4.7,.16,.16)),
        ('window_sill',(-.94,2.92,.11),(4.7,.20,.12))]:box(name,center,size,mats['wall'],.006,assembly='window')
    for i,x in enumerate([-1.99,-.74,.48]):box(f'window_mullion_{i}',(x,2.88,1.27),(.045,.08,2.18),mats['wall'],.004,assembly='window')
    # Captured outdoor appearance is a separate, labelled background plane.
    photo=bpy.data.images.load(manifest['frames'][5]['original_path']);photo.pack()
    backdrop=bpy.data.materials.new('Captured exterior reference - not reconstructed');backdrop.use_nodes=True
    nodes=backdrop.node_tree.nodes;nodes.clear();output=nodes.new('ShaderNodeOutputMaterial');em=nodes.new('ShaderNodeEmission');tex=nodes.new('ShaderNodeTexImage');tex.image=photo
    em.inputs['Strength'].default_value=.8;backdrop.node_tree.links.new(tex.outputs['Color'],em.inputs['Color']);backdrop.node_tree.links.new(em.outputs[0],output.inputs['Surface'])
    vertices=[(-3.30,3.08,.05),(1.45,3.08,.05),(1.45,3.08,2.5),(-3.30,3.08,2.5)]
    mesh=bpy.data.meshes.new('exterior_reference_mesh');mesh.from_pydata(vertices,[],[(0,1,2,3)]);mesh.uv_layers.new()
    uv=[(270/960,1-402/540),(670/960,1-402/540),(670/960,1-183/540),(270/960,1-183/540)]
    for i,value in enumerate(uv):mesh.uv_layers.active.data[i].uv=value
    obj=bpy.data.objects.new('exterior_reference_backplate',mesh);scene.collection.objects.link(obj);obj.data.materials.append(backdrop)
    obj['assembly']='exterior_reference';obj['representation']='captured background only, not reconstructed exterior geometry'
    # Mirror wall: separate carcasses, backs, shelves, dividers and base doors.
    front,back=1.07,1.40
    box('mirror_panel',(1.065,.00,1.397),(.025,2.10,1.87),mats['mirror'],.004,assembly='mirror_wall')
    box('mirror_upper_trim',(1.07,.00,2.355),(.08,2.16,.045),mats['dark'],assembly='mirror_wall')
    box('mirror_lower_trim',(1.045,.00,.445),(.09,2.16,.035),mats['dark'],assembly='mirror_wall')
    for side,(low,high) in enumerate([(-2.06,-1.06),(1.06,1.95)]):
        assembly='shelves_entry' if side==0 else 'shelves_window'
        box(assembly+'_back',(back,(low+high)/2,1.37),(.045,high-low,2.10),mats['dark'],assembly=assembly)
        for j,y in enumerate([low,high]):box(assembly+f'_side_{j}',((front+back)/2,y,1.37),(back-front,.035,2.13),mats['dark'],assembly=assembly)
        levels=[.36,.76,1.15,1.55,1.94,2.39] if side else [.42,2.01,2.39]
        for j,z in enumerate(levels):box(assembly+f'_shelf_{j}',((front+back)/2,(low+high)/2,z),(back-front,high-low,.035),mats['dark'],assembly=assembly)
        if side==0:
            box('entry_shelves_divider',((front+back)/2,-1.45,1.4),(back-front,.035,1.95),mats['dark'],assembly=assembly)
            for j,z in enumerate([.96,1.50,1.95]):box(f'entry_narrow_shelf_{j}',((front+back)/2,-1.25,z),(back-front,.39,.028),mats['dark'],assembly=assembly)
    for i,(low,high) in enumerate([(-2.06,-1.46),(-1.44,-1.06),(-1.04,-.36),(-.34,.34),(.36,1.04)]):
        box(f'base_cabinet_{i}',(1.22,(low+high)/2,.23),(.38,high-low,.40),mats['dark'],.008,assembly='base_cabinet')
        box(f'base_door_{i}',(1.015,(low+high)/2,.235),(.027,high-low-.012,.365),mats['dark'],.002,assembly='base_cabinet')
    for i,y in enumerate([1.19,1.49,1.79]):
        box(f'window_low_cubby_back_{i}',(1.37,y,.19),(.04,.27,.25),mats['dark'],assembly='shelves_window')
        box(f'window_low_cubby_divider_{i}',(1.21,y+.14,.19),(.36,.025,.25),mats['dark'],assembly='shelves_window')
    box('window_low_cubby_floor',(1.21,1.52,.045),(.38,.87,.035),mats['dark'],assembly='shelves_window')
    box('cabinet_plaster_header',(1.13,-.05,2.47),(.20,4.40,.14),mats['wall'],assembly='mirror_wall')
    # Shelf contents are independently editable, intentionally approximate props.
    colors=[(.64,.47,.06),(.45,.055,.028),(.72,.71,.65),(.05,.12,.25)]
    books=[(-1.28,1.52,5),(-1.20,.45,4),(1.45,1.17,4)]
    for group,(y,z,count) in enumerate(books):
        for i in range(count):
            m=material(f'book_color_{group}_{i}',colors[i%4],.7)
            box(f'book_{group}_{i}',(1.13,y+i*.047,z+.12+i%2*.027),(.13,.038,.23+i%2*.054),m,.002,assembly='shelf_accessories')
    for i,(y,z) in enumerate([(-1.27,2.13),(1.5,1.78),(1.52,.91)]):
        ellipsoid(f'ceramic_vase_{i}',(1.19,y,z),(.13,.15,.23),mats['white'] if i else mats['dark'],assembly='shelf_accessories')
    ellipsoid('sculptural_bowl',(1.20,-1.77,2.15),(.19,.36,.17),mats['cream'],assembly='shelf_accessories')
    cylinder('display_clock',(1.14,1.56,2.13),.115,.027,mats['white'],'shelf_accessories',(0,math.pi/2,0))
    for i in range(7):
        stem=box(f'dry_stem_{i}',(1.19,-1.77+(i-3)*.016,.73),(.008,.007,.41+(i%3)*.023),mats['wood'],assembly='shelf_accessories');stem.rotation_euler.x=(i-3)*.06
    cylinder('entry_flower_vase',(1.20,-1.77,.56),.053,.20,mats['brass'],'shelf_accessories')
    # Ceiling tray detailing and recessed fittings.
    box('ceiling_window_soffit',(-.92,2.62,2.52),(4.76,.48,.12),mats['wall'],assembly='ceiling_details')
    box('ceiling_left_soffit',(-3.22,-.10,2.53),(.48,5.12,.12),mats['wall'],assembly='ceiling_details')
    for i,(x,y) in enumerate([(-2.3,1.55),(-.5,1.55),(.65,.75),(-2.25,-.5),(-.55,-.5)]):
        box(f'recessed_light_trim_{i}',(x,y,2.635),(.095,.095,.022),mats['white'],assembly='ceiling_details')
        box(f'recessed_light_dark_{i}',(x,y,2.619),(.055,.055,.008),mats['dark'],assembly='ceiling_details')
    cylinder('ceiling_speaker',(-1.6,.5,2.63),.12,.014,mats['white'],'ceiling_details')
    build_furniture(cfg['furniture'],mats)
    for name,offset in cfg.get('part_local_z_offsets',{}).items():
        bpy.data.objects[name].location.z+=offset
    # Reference camera gauge alignment is shared by geometry and all cameras.
    cameras=[];camera_records=[]
    for i in range(6):
        yy,xx=np.mgrid[:378,:672];ray=rays[i];mask=np.isfinite(ray).all(-1)&(ray[...,2]>.1);q=ray[mask]
        sx=q[:,0]/q[:,2];sy=q[:,1]/q[:,2]
        fx,cx=np.linalg.lstsq(np.column_stack([sx,np.ones(len(sx))]),xx[mask],rcond=None)[0]
        fy,cy=np.linalg.lstsq(np.column_stack([sy,np.ones(len(sy))]),yy[mask],rcond=None)[0]
        residual=float(np.sqrt(np.mean((fx*sx+cx-xx[mask])**2+(fy*sy+cy-yy[mask])**2)))
        data=bpy.data.cameras.new(f'real_view_{i:02d}');camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
        R=Q@poses[i,:3,:3]@np.diag([1,-1,-1]);position=Q@(poses[i,:3,3]-origin)
        M=np.eye(4);M[:3,:3]=R;M[:3,3]=position;camera.matrix_world=Matrix(M.tolist())
        data.sensor_fit='HORIZONTAL';data.sensor_width=36;data.lens=float(fx*36/672);data.shift_x=float((336-cx)/672);data.shift_y=float((cy-189)/672)
        data.clip_start=.03;data.clip_end=100;camera['source_frame_ordinal']=i;camera['scale_status']='learned_unvalidated'
        cameras.append(camera);camera_records.append(dict(frame=i,source=manifest['frames'][i],matrix_world=M.tolist(),fx=float(fx),fy=float(fy),cx=float(cx),cy=float(cy),ray_fit_rmse_px=residual))
    scene.world=bpy.data.worlds.new('soft_daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.70,.78,1,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
    for name,location,energy,size in [('window_daylight',(-.9,2.72,1.7),500,4.2),('soft_ceiling_fill',(-1,-.5,2.45),130,4.0)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=size;ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=location
        if name=='window_daylight':
            ob.rotation_euler=(cfg.get('window_light_rotation_x',math.pi/2),0,0)
            data.energy=cfg.get('window_light_energy',energy)
        if cfg.get('hide_area_lights_from_glossy',False):ob.visible_glossy=False
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=cfg['samples'];scene.cycles.use_denoising=True;scene.cycles.seed=0
    scene.render.threads_mode='FIXED';scene.render.threads=2;scene.render.resolution_x=cfg['render_wh'][0];scene.render.resolution_y=cfg['render_wh'][1];scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.7
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene['source_id']='bedroom_waterfront_g0024';scene['scope']='Editable authored reconstruction, unverified scale/materials; source-observed views, not measured geometry or physics'
    # Organize objects into named assembly collections without joining meshes.
    groups={}
    for obj in list(scene.objects):
        if obj.type!='MESH':continue
        name=obj.get('assembly','unassigned');groups.setdefault(name,[]).append(obj)
    for name,objects in groups.items():
        collection=bpy.data.collections.new(name);scene.collection.children.link(collection)
        for obj in objects:
            for old in list(obj.users_collection):old.objects.unlink(obj)
            collection.objects.link(obj)
    scene.camera=cameras[5]
    scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=camera_records[5]['fx']/camera_records[5]['fy']
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'scene.blend'))
    inventory=[dict(name=o.name,assembly=o.get('assembly'),type=o.type,dimensions=list(o.dimensions),location=list(o.location),parent=o.parent.name if o.parent else None) for o in scene.objects if o.type=='MESH']
    save(a.output/'editable_inventory.json',inventory);save(a.output/'cameras.json',camera_records)
    receipt=dict(status='authored',protocol_sha256=sha(a.protocol),script_sha256=sha(__file__),helper_sha256=sha(Path(__file__).with_name('waterfront_primitives.py')),
                 source_npz_sha256=cfg['npz_sha256'],model_sha256=sha(a.output/'scene.blend'),mesh_parts=len(inventory),assemblies={k:len(v) for k,v in groups.items()},
                 alignment={'world_to_room_rotation':Q.tolist(),'world_origin':origin.tolist(),'scale_factor':1.,'status':'assumed gravity/cabinet axes from existing prediction; no measured scale'},renders=[])
    save(a.output/'receipt.json',receipt)
    for i in cfg['views']:
        scene.camera=cameras[i];scene.render.pixel_aspect_x=1;scene.render.pixel_aspect_y=camera_records[i]['fx']/camera_records[i]['fy']
        path=a.output/f'view_{i:02d}.png';scene.render.filepath=str(path);t0=time.monotonic();bpy.ops.render.render(write_still=True)
        receipt['renders'].append(dict(frame=i,path=str(path),sha256=sha(path),wall_seconds=time.monotonic()-t0));save(a.output/'receipt.json',receipt)
    receipt['wall_seconds']=time.monotonic()-t;receipt['source_inputs_unchanged']=all(sha(f['original_path'])==f['sha256'] for f in manifest['frames'])
    receipt['status']='rendered';save(a.output/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'mesh_parts':receipt['mesh_parts'],'views':cfg['views'],'wall_seconds':receipt['wall_seconds']}))


if __name__=='__main__':main()
