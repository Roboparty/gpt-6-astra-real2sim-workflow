from pathlib import Path
import sys,json,hashlib
import bpy,numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r/'workflow'))
from r2s.blender_camera import apply_camera
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.image_settings.file_format='PNG';sc.world.color=(.5,.5,.5)
bpy.ops.object.camera_add();cam=bpy.context.object
specs=[]
for fid,C,R,size,f,pp in [('viewA',[-2,-4,1],[[1,0,0],[0,0,-1],[0,1,0]],[160,120],[150,120],[73.5,56.5]),('viewB',[2,4,1],[[-1,0,0],[0,0,-1],[0,-1,0]],[180,130],[130,160],[90.2,61.8])]:
 specs.append(dict(frame_id=fid,position=C,rotation_world_to_cv=R,image_size=size,focal_px=f[0],focal_y_px=f[1],principal_point=pp,pixel_coordinates='integer_centers'))
assemblies=[];checks=[]
for idx,(name,x,y,cal) in enumerate([('left_box',-2,-.5,specs[0]),('right_box',2,.5,specs[1])]):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(x,0,.5));obj=bpy.context.object;obj.name=name;obj['furniture_id']=name;obj['part_id']='body'
 mat=bpy.data.materials.new(name);mat.diffuse_color=(1,0,0,1) if idx==0 else (0,0,1,1);obj.data.materials.append(mat)
 apply_camera(sc,cam,cal);bpy.context.view_layer.update();landmarks=[]
 for j,(dx,z) in enumerate([(-.5,0),(.5,0),(-.5,1),(.5,1)]):
  p=np.array([x+dx,y,z]);q=np.array(cal['rotation_world_to_cv'])@(p-np.array(cal['position']));uv=q[:2]/q[2]*[cal['focal_px'],cal['focal_y_px']]+cal['principal_point']
  ndc=world_to_camera_view(sc,cam,Vector(p));actual=np.array([ndc.x*cal['image_size'][0]-.5,(1-ndc.y)*cal['image_size'][1]-.5]);err=np.linalg.norm(actual-uv);assert err<1e-4,(actual,uv)
  lm=dict(id=name+str(j),part='body',world=p.tolist(),uv=uv.tolist())
  if idx:lm['frame_id']='viewB'
  landmarks.append(lm);checks.append(float(err))
 assemblies.append(dict(entity=name,parts=[dict(id='body',object=name)],joints=[],floor_supports=[dict(part='body',plane_z=0,tolerance_m=.005)],source_observation_ids=[cal['frame_id']],frame=dict(yaw_rad=0),fit=dict(frame_id='viewA',landmarks=landmarks)))
apply_camera(sc,cam,specs[0]);bpy.context.view_layer.update()
scene=dict(model_version='synthetic-camera-review',camera=specs[0],cameras=specs,objects=[dict(id=a['entity']) for a in assemblies],structure=dict(schema='real2sim.assembly/1',assemblies=assemblies,unexpected_interpenetration_tolerance_m=.005,acceptance=dict(landmark_median_px=.001,landmark_max_px=.001)))
(r/'scene.json').write_text(json.dumps(scene,indent=2));(r/'projection_check.json').write_text(json.dumps(dict(blender=bpy.app.version_string,max_projection_error_px=max(checks),count=len(checks)),indent=2))
(r/'output').mkdir(exist_ok=True);(r/'output/packet.json').write_text(json.dumps({'parameters':{'inspection_resolution':[64,64]}}))
bpy.ops.wm.save_as_mainfile(filepath=str(r/'model.blend'))
print('FIXTURE_OK',max(checks))
