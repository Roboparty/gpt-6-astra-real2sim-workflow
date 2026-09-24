"""Real Blender mesh failure-injection checks; all files stay in a new test directory."""
import bpy,sys,json,runpy,os
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:];root=Path(args[0]);candidate=Path(args[1]);out=Path(args[2]);out.mkdir(parents=True,exist_ok=True)
os.environ['R2S_STRUCTURE_NO_RENDER']='1';results=[]
for label in ['baseline_intended_contacts','detached_leg','wrong_crossbar','table_chair_interpenetration','wrong_part_owner','stale_source_landmarks_after_rigid_move']:
 bpy.ops.wm.open_mainfile(filepath=str(candidate/'model.blend'))
 scene=json.loads((candidate/'scene.json').read_text())
 if label=='detached_leg':bpy.data.objects['chair_near__front_left_leg'].location.z-=.07
 if label=='wrong_crossbar':bpy.data.objects['table__cross_near'].location.x+=.16
 if label=='table_chair_interpenetration':
  target=bpy.data.objects['table__leg_near_right'];moving=bpy.data.objects['chair_near__front_left_leg'];moving.location=target.location.copy()
 if label=='wrong_part_owner':bpy.data.objects['chair_near__back_rail']['furniture_id']='table'
 if label=='stale_source_landmarks_after_rigid_move':
  for o in bpy.data.objects:
   if o.get('furniture_id')=='chair_near':o.location.x+=.4
  for a in scene['structure']['assemblies']:
   if a['entity']=='chair_near':
    for j in a['joints']:j['anchor_world'][0]+=.4
    for f in a['floor_supports']:f['point_world'][0]+=.4
 dest=out/label;dest.mkdir(exist_ok=True);(dest/'scene.json').write_text(json.dumps(scene));bpy.ops.wm.save_as_mainfile(filepath=str(dest/'model.blend'));sys.argv=['blender','--',str(dest/'scene.json'),str(dest)]
 try:runpy.run_path(str(root/'workflow/r2s/blender_structure.py'),run_name='__main__')
 except SystemExit as e:
  if e.code not in [0,None]:raise
 result=json.loads((dest/'structural_audit.json').read_text());expected='passed' if label=='baseline_intended_contacts' else 'failed';assert result['status']==expected,(label,result['status'])
 if label=='stale_source_landmarks_after_rigid_move':assert any(f['kind']=='landmark_part_mismatch' for f in result['failures']) and not any(f['kind']=='disconnected_joint' for f in result['failures'])
 results.append(dict(test=label,expected=expected,actual=result['status'],failures=result['failures']))
(out/'mutation_test_results.json').write_text(json.dumps(dict(status='passed',tests=results),indent=2));print(json.dumps(results,indent=2))
