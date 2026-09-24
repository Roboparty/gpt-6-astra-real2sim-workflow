import os
import bpy,sys,json
from pathlib import Path
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).parent))
from viewpoints import diagnostic_focus,safe_camera_position
out=Path(sys.argv[sys.argv.index('--')+1]);sc=bpy.context.scene
for name in ['floor','ceiling','wall_back','wall_front','wall_left','wall_right']:
 o=bpy.data.objects.get(name)
 if o is None or o.hide_render:raise ValueError('Required enclosure surface absent/hidden: '+name)
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 sc.cycles.device='GPU' if os.environ.get('R2S_CPU')!='1' and any(d.use for d in p.devices) else 'CPU'
except Exception:sc.cycles.device='CPU'
S=json.loads((out/'scene.json').read_text());specs=S.get('cameras') or [S['camera']];cameras=[]
for i,c in enumerate(specs):
    name='source_camera' if i==0 else f'source_camera_{i:04d}';camera=bpy.data.objects.get(name)
    if camera is None:bpy.ops.object.camera_add();camera=bpy.context.object;camera.name=name
    camera.location=c['position'];camera.rotation_euler=(Matrix(c['rotation_world_to_cv']).transposed()@Matrix(((1,0,0),(0,-1,0),(0,0,-1)))).to_euler();W,H=c['image_size'];camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=36;camera.data.lens=c['focal_px']*36/W;camera.data.shift_x=(W/2-c['principal_point'][0])/W;camera.data.shift_y=(c['principal_point'][1]-H/2)/W;camera['frame_id']=c.get('frame_id',str(i));cameras.append(camera)
sc.camera=cameras[0];sc.render.resolution_x=specs[0]['image_size'][0];sc.render.resolution_y=specs[0]['image_size'][1];bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
for i,(camera,c) in enumerate(zip(cameras,specs)):
    sc.camera=camera;sc.render.resolution_x=c['image_size'][0];sc.render.resolution_y=c['image_size'][1];sc.render.filepath=str(out/('source_view.png' if i==0 else f'source_view_{i:04d}.png'));bpy.ops.render.render(write_still=True)
(out/'render_manifest.json').write_text(json.dumps({'frames':[{'frame_id':c.get('frame_id',str(i)),'camera':camera.name,'render':'source_view.png' if i==0 else f'source_view_{i:04d}.png','role':'reconstruction_view'} for i,(camera,c) in enumerate(zip(cameras,specs))]},indent=2))
# Geometry-focused review and complete-enclosure views are available before the Agent review gate.
sc.camera=cameras[0];sc.render.resolution_x=specs[0]['image_size'][0];sc.render.resolution_y=specs[0]['image_size'][1];sc.cycles.samples=48
clay=bpy.data.materials.new('review_clay');clay.use_nodes=True;clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.5,.5,.5,1);clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8;sc.view_layers[0].material_override=clay;sc.render.filepath=str(out/'source_clay.png');bpy.ops.render.render(write_still=True);sc.view_layers[0].material_override=None
r=S['room'];xm,xM,ym,yM,h=[r[k] for k in ['x_min','x_max','y_min','y_max','height']];dx=xM-xm;dy=yM-ym;focus=diagnostic_focus(S);diagnostics=[]
for name,pos in [('wide',(xM-dx*.12,ym+dy*.12,h*.73)),('reverse',(xm+dx*.2,yM-dy*.08,h*.65))]:
    chosen=safe_camera_position(S,pos);bpy.ops.object.camera_add(location=chosen);cam=bpy.context.object;cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=22;sc.camera=cam;sc.render.resolution_x=960;sc.render.resolution_y=640;sc.render.filepath=str(out/f'diagnostic_{name}.png');bpy.ops.render.render(write_still=True);diagnostics.append({'name':name,'position':list(chosen),'target':list(focus),'layout_modified':False})
(out/'diagnostic_cameras.json').write_text(json.dumps(diagnostics,indent=2))
packet=json.loads((out/'packet.json').read_text()) if (out/'packet.json').exists() else {}
if packet.get('workflow_profile')=='quality_v2':
    # Inspection cameras do not remove or hide the opposite wall or ceiling.
    center=safe_camera_position(S,((xm+xM)/2,(ym+yM)/2,h*.60))
    wall_targets={'wall_front':((xm+xM)/2,ym,h*.5),'wall_back':((xm+xM)/2,yM,h*.5),'wall_left':(xm,(ym+yM)/2,h*.5),'wall_right':(xM,(ym+yM)/2,h*.5)}
    for name,target in wall_targets.items():
        bpy.ops.object.camera_add(location=center);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=18;sc.camera=cam;sc.render.resolution_x=960;sc.render.resolution_y=640;sc.render.filepath=str(out/f'inspect_{name}.png');bpy.ops.render.render(write_still=True)
    (out/'four_wall_views.json').write_text(json.dumps({'camera_position':list(center),'targets':wall_targets,'all_walls_retained':True,'interpretation':'inspection views, not proof that invisible walls were measured'},indent=2))
