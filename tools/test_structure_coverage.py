"""Real Blender audit must reject omitted visible assembly-owned geometry."""
import bpy,json,sys,tempfile,subprocess,os
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
parts=[]
for name,pos,size in [('base',(-.2,0,.2),(.4,.4,.4)),('top',(-.2,0,.5),(.3,.3,.2)),('dressing',(.05,0,.2),(.1,.1,.2))]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o['entity_id']='cabinet';o['furniture_id']='cabinet';o['part_id']=name;parts.append({'id':name,'object':name})
bpy.ops.object.camera_add(location=(2,-3,2));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.3))-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.scene.camera=cam;bpy.context.view_layer.update();rot=cam.matrix_world.to_3x3().transposed();R=[list(rot[0]),list(-rot[1]),list(-rot[2])];point=Vector((-.4,-.2,0));q=Vector([sum(R[i][j]*(point[j]-cam.location[j]) for j in range(3)) for i in range(3)]);uv=[q.x/q.z*200+160,q.y/q.z*200+120]
assembly={'entity':'cabinet','parts':parts,'joints':[dict(parts=['base','top'],anchor_world=[-.2,0,.4],tolerance_m=.002),dict(parts=['base','dressing'],anchor_world=[0,0,.2],tolerance_m=.002)],'floor_supports':[dict(part='base',plane_z=0,tolerance_m=.002)],'fit':{'landmarks':[dict(id='corner',world=list(point),uv=uv,part='base')]}}
scene={'model_version':'coverage_fixture','camera':dict(position=list(cam.location),rotation_world_to_cv=R,focal_px=200,principal_point=[160,120],image_size=[320,240]),'structure':dict(assemblies=[assembly],acceptance=dict(landmark_median_px=1,landmark_max_px=1),unexpected_interpenetration_tolerance_m=.002)}
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);blend=p/'model.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 for omitted in [False,True]:
  out=p/('omitted' if omitted else 'complete');out.mkdir();spec=json.loads(json.dumps(scene))
  if omitted:spec['structure']['assemblies'][0]['parts']=parts[:2];spec['structure']['assemblies'][0]['joints']=assembly['joints'][:1]
  (out/'scene.json').write_text(json.dumps(spec));env={**os.environ,'R2S_STRUCTURE_NO_RENDER':'1','R2S_CPU':'1'}
  result=subprocess.run([bpy.app.binary_path,'-b',str(blend),'-t','2','--python-exit-code','12','--python',str(root/'workflow/r2s/blender_structure.py'),'--',str(out/'scene.json'),str(out)],capture_output=True,text=True,env=env);assert result.returncode==0,result.stderr
  audit=json.loads((out/'structural_audit.json').read_text())
  if omitted:assert any(f['kind']=='unbound_visible_assembly_geometry' and f['object']=='dressing' for f in audit['failures'])
  else:assert audit['status']=='passed',audit['failures']
print('STRUCTURE_VISIBLE_COVERAGE_OK')
