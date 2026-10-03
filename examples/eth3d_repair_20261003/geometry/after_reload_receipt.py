import bpy,json,hashlib,sys,argparse
import numpy as np
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--baseline-root',type=Path,default=Path('/home/wqz/real2sim_agent_compare_20261003/OURS'));p.add_argument('--repair-root',type=Path,default=Path('/home/wqz/real2sim_agent_repair_20261003/geometry'));p.add_argument('--candidate',default='candidate_v4');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
B=a.baseline_root;R=a.repair_root;V=R/a.candidate;sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest();baseline=B/'models/v3/model.blend';candidate=V/'model.blend';assert sha(baseline)=='4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85';before=sha(candidate)
def collect(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);deps=bpy.context.evaluated_depsgraph_get();rows={};cameras={};lights={}
 for o in bpy.context.scene.objects:
  if o.type=='MESH':
   ev=o.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();v=np.array([o.matrix_world@x.co for x in m.vertices],dtype=np.float64);tri=np.array([tuple(t.vertices) for t in m.loop_triangles],dtype=np.int32)
   rows[o.name]=dict(owner=o.get('entity_id',o.name),vertices=len(v),triangles=len(tri),world_vertices_sha256=hashlib.sha256(v.tobytes()).hexdigest(),triangulation_sha256=hashlib.sha256(tri.tobytes()).hexdigest(),world_bounds=[v.min(0).tolist(),v.max(0).tolist()],hide_render=o.hide_render,exclude=bool(o.get('exclude_from_evaluation')),materials=[s.material.name if s.material else None for s in o.material_slots]);ev.to_mesh_clear()
  elif o.type=='CAMERA':cameras[o.name]=dict(matrix=[list(r) for r in o.matrix_world],lens=o.data.lens,shift=[o.data.shift_x,o.data.shift_y],sensor_width=o.data.sensor_width)
  elif o.type=='LIGHT':lights[o.name]=dict(matrix=[list(r) for r in o.matrix_world],energy=o.data.energy,color=list(o.data.color),kind=o.data.type)
 return rows,cameras,lights,dict(exposure=bpy.context.scene.view_settings.exposure,view_transform=bpy.context.scene.view_settings.view_transform,look=bpy.context.scene.view_settings.look,samples=bpy.context.scene.cycles.samples,max_bounces=bpy.context.scene.cycles.max_bounces)
old,oc,ol,os=collect(baseline);new,nc,nl,ns=collect(candidate);changes=[]
for name in sorted(old.keys()|new.keys()):
 if name not in old:status='added'
 elif name not in new:status='removed'
 elif old[name]['world_vertices_sha256']!=new[name]['world_vertices_sha256']:status='geometry_changed'
 else:status='unchanged'
 if status!='unchanged':changes.append(dict(object=name,status=status,before=old.get(name),after=new.get(name)))
old_receipt=json.loads((V/'geometry_changes.json').read_text());pre_save=[]
for row in old_receipt:
 if 'candidate_evaluated_vertices_sha256' in row:pre_save.append(dict(object=row['object'],pre_save_hash=row['candidate_evaluated_vertices_sha256'],after_reload_hash=new[row['object']]['world_vertices_sha256'],same=row['candidate_evaluated_vertices_sha256']==new[row['object']]['world_vertices_sha256']))
result=dict(status='measured_after_reload',baseline_model_sha256=sha(baseline),candidate_model_sha256=before,candidate_unchanged=sha(candidate)==before,cameras_unchanged=oc==nc,lights_unchanged=ol==nl,render_controls_unchanged=os==ns,visibility_unchanged_for_retained=all(old[n]['hide_render']==new[n]['hide_render'] and old[n]['exclude']==new[n]['exclude'] for n in old.keys()&new.keys()),all_retained_material_bindings_unchanged=all(old[n]['materials']==new[n]['materials'] for n in old.keys()&new.keys()),baseline_meshes=len(old),candidate_meshes=len(new),objects=new,geometry_changes=changes,pre_save_hash_corrections=pre_save,hash_policy='After-reload hashes supersede pre-save candidate hashes for verification only; original receipt and model retained unchanged. Floating save-rounding and n-gon retriangulation are not silently relabelled geometry equality.',pipe_bounds={n:new[n]['world_bounds'] for n in new if n.startswith(('ceiling_pipe','main_ceiling_pipe'))})
(V/'after_reload_evaluated_mesh_receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['objects','geometry_changes','pre_save_hash_corrections','pipe_bounds']},indent=2))
