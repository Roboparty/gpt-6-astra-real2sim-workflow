"""One real synthetic empty-furniture room, export, and rejection mutations.
Run inside Blender; all outputs stay in a fresh remote directory.
"""
import copy,json,os,subprocess,sys,time
from pathlib import Path
import bpy
from mathutils import Vector,Matrix

repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'workflow'))
from r2s.structure import review_contract,file_sha
from r2s.contracts import scene_check,ContractError
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
start=time.monotonic();bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
specs=[('floor',(0,0,-.05),(4.2,4.2,.1)),('ceiling',(0,0,3.05),(4.2,4.2,.1)),
 ('wall_back',(0,2.05,1.5),(4.2,.1,3)),('wall_front',(0,-2.05,1.5),(4.2,.1,3)),
 ('wall_left',(-2.05,0,1.5),(.1,4,3)),('wall_right',(2.05,0,1.5),(.1,4,3)),
 ('ceiling_lamp',(0,0,2.94),(.4,.4,.08))]
objects=[]
for name,pos,size in specs:
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);obj=bpy.context.object;obj.name=name;obj.dimensions=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 role='fixed_luminaire' if name=='ceiling_lamp' else 'room_shell';obj['entity_id']=name;obj['geometry_role']=role
 objects.append(dict(id=name,kind=name,structural_role=role,position=list(pos),dimensions=list(size),evidence=['synthetic fixture'],confidence=1))
bpy.ops.object.light_add(type='AREA',location=(0,0,2.8));bpy.context.object.data.energy=300
bpy.ops.object.camera_add(location=(1.6,-1.6,1.6));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1,1.3))-cam.location).to_track_quat('-Z','Y').to_euler();bpy.context.scene.camera=cam
bpy.context.view_layer.update()
scene=dict(schema_version='real2sim.scene/1.0',units='m',up_axis='Z',model_version='empty_room_synthetic_001',
 room=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3,thickness=.1,preserve_full_shell=True),objects=objects,
 camera=dict(position=list(cam.location),rotation_world_to_cv=[list(row) for row in Matrix.Diagonal((1,-1,-1))@cam.matrix_world.to_3x3().transposed()],focal_px=100,principal_point=[80,60],image_size=[160,120]),
 structure=dict(schema='real2sim.assembly/1',scope='empty_room',assemblies=[],shell_objects=[x[0] for x in specs[:-1]],fixed_luminaire_objects=['ceiling_lamp'],unexpected_interpenetration_tolerance_m=.002))
from r2s.blender_camera import apply_camera
apply_camera(bpy.context.scene,cam,scene['camera'])
schema_result=scene_check(scene);spec=out/'scene.json';spec.write_text(json.dumps(scene));model=out/'model.blend';bpy.ops.wm.save_as_mainfile(filepath=str(model))
env=dict(os.environ,R2S_CPU='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2');env.pop('R2S_STRUCTURE_NO_RENDER',None)
def run_worker(script,dest,input_model=model,extra=(),no_render=False):
 dest.mkdir(exist_ok=True);settings=dict(env)
 if no_render:settings['R2S_STRUCTURE_NO_RENDER']='1'
 cmd=[bpy.app.binary_path,'-b',str(input_model),'-t','2','--python-exit-code','12','--python',str(repo/'workflow/r2s'/script),'--',str(spec),str(dest),*extra]
 with (dest/'worker.log').open('w') as log:result=subprocess.run(cmd,env=settings,stdout=log,stderr=subprocess.STDOUT,timeout=300)
 assert result.returncode==0,(dest,result.returncode)
 return json.loads((dest/('geometry_audit.json' if script=='blender_export.py' else 'structural_audit.json')).read_text())
audit=run_worker('blender_structure.py',out/'positive');assert audit['status']=='passed',audit['failures']
def review_for(a,directory):
 return dict(geometry_freeze_sha256=a['source_model_sha256'],model_version=scene['model_version'],
  per_object=[dict(entity=o['id'],status='pass',findings='Synthetic shell or fixed luminaire',evidence=['furniture_source_view.png']) for o in objects],
  checks={'empty_room':dict(status='pass',findings='Synthetic full-frame inventory; not real reconstruction judgement',evidence=['furniture_source_view.png'])})
def check(a,s,r,directory,reject=False):
 try:review_contract(directory,r,[p.name for p in directory.iterdir() if p.is_file()],s,dict(model_sha256=a['source_model_sha256'],scene_sha256=a['source_scene_sha256'],structural_audit_sha256=file_sha(directory/'structural_audit.json')))
 except ContractError:
  assert reject;return
 assert not reject
review=review_for(audit,out/'positive');check(audit,scene,review,out/'positive')
negative=[]
for label,mutation in [('implicit_zero',lambda s:s['structure'].pop('scope')),('omitted_semantic_object',lambda s:s['objects'].pop()),('wrong_semantic_role',lambda s:s['objects'][0].update(structural_role='furniture'))]:
 bad=copy.deepcopy(scene);mutation(bad);check(audit,bad,review,out/'positive',True);negative.append(label)
bad=copy.deepcopy(review);bad['checks']={};check(audit,scene,bad,out/'positive',True);negative.append('missing_explicit_review')
unrendered=run_worker('blender_structure.py',out/'no_render',no_render=True);check(unrendered,scene,review,out/'no_render',True);negative.append('no_render_cannot_pass_review')
export=run_worker('blender_export.py',out/'export',extra=['--geometry-only']);assert len(export['enclosure_present'])==6 and len(export['entities'])==7
# Add actual hidden furniture; it must not disappear from the absence audit.
bpy.ops.mesh.primitive_cube_add(size=.2,location=(0,0,.1));intruder=bpy.context.object;intruder.name='undeclared_chair';intruder.hide_render=True
badmodel=out/'hidden_furniture.blend';bpy.ops.wm.save_as_mainfile(filepath=str(badmodel))
bad=run_worker('blender_structure.py',out/'hidden_furniture',badmodel,no_render=True);assert bad['status']=='failed';negative.append('hidden_furniture_rejected')
bpy.data.objects.remove(intruder,do_unlink=True)
# Geometry Nodes generates an instance even though object.instance_type is NONE.
floor=bpy.data.objects['floor'];mod=floor.modifiers.new('instance_mutation','NODES');tree=bpy.data.node_groups.new('empty_room_instance_mutation','GeometryNodeTree');mod.node_group=tree
tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
inp=tree.nodes.new('NodeGroupInput');output=tree.nodes.new('NodeGroupOutput');instance=tree.nodes.new('GeometryNodeGeometryToInstance');join=tree.nodes.new('GeometryNodeJoinGeometry')
tree.links.new(inp.outputs['Geometry'],instance.inputs['Geometry']);tree.links.new(instance.outputs['Instances'],join.inputs['Geometry']);tree.links.new(inp.outputs['Geometry'],join.inputs['Geometry']);tree.links.new(join.outputs['Geometry'],output.inputs['Geometry'])
assert floor.instance_type=='NONE';badmodel=out/'geometry_nodes_instance.blend';bpy.ops.wm.save_as_mainfile(filepath=str(badmodel))
bad=run_worker('blender_structure.py',out/'geometry_nodes_instance',badmodel,no_render=True);assert bad['status']=='failed' and any(f['kind']=='unsupported_empty_room_evaluated_instances' for f in bad['failures']);negative.append('geometry_nodes_instance_rejected')
report=dict(status='passed',scope='Actual synthetic empty-furniture inventory, source view, canonical scene check and geometry-only export; not full scene reconstruction or dynamics acceptance',
 schema_check=schema_result,assemblies=len(audit['assemblies']),shell_count=6,fixed_luminaires=1,exported_entities=len(export['entities']),negative_checks=negative,wall_seconds=time.monotonic()-start,
 model_sha256=file_sha(model),scene_sha256=file_sha(spec),audit_sha256=file_sha(out/'positive/structural_audit.json'),script_sha256=file_sha(__file__),implementation_sha256={name:file_sha(repo/'workflow/r2s'/name) for name in ['structure.py','blender_structure.py','contracts.py']})
(out/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
