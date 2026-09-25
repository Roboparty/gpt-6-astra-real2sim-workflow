"""Run in Blender on a rejected and corrected cabinet: measured geometry regression."""
import bpy,json,sys,tempfile,shutil
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:];old,new,manifest=map(Path,args[:3]);sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow/r2s'))
from blender_surfaces import audit
results=[]
with tempfile.TemporaryDirectory(prefix='surface_mesh_regression_') as temp:
 out=Path(temp)
 for p in manifest.iterdir():
  if p.suffix in ['.json','.png','.jpg']:shutil.copy2(p,out/p.name)
 m=json.loads((out/'surface_realization.json').read_text());correct=json.loads(json.dumps(m))
 # The old cabinet has no panel groups. Bind its entire front objects: this
 # still cannot hide the 22 real thin strips from evaluated component screening.
 m['regions'][0]['features'][0]['mesh_refs']=[dict(object=f'shoe__door{i}',whole_surface=True) for i in [0,1]]
 (out/'surface_realization.json').write_text(json.dumps(m));bpy.ops.wm.open_mainfile(filepath=str(old));bad=audit(out,render=False)
 assert bad['status']=='failed' and any(f['kind']=='unsupported_repeated_relief' for f in bad['failures']),bad
 assert any(f['kind']=='overlapping_exterior_component_faces' for f in bad['failures']),bad
 results.append(dict(case='actual_rejected_cabinet',status=bad['status'],failures=bad['failures']))
 (out/'surface_realization.json').write_text(json.dumps(correct));bpy.ops.wm.open_mainfile(filepath=str(new));good=audit(out,render=False)
 assert good['status']=='passed',good
 results.append(dict(case='corrected_two_panel_doors',status=good['status'],counts=good['regions'][0]['features']))
 obj=bpy.data.objects['shoe__door0'];mod=obj.modifiers.new('Unexpected duplicated panels','ARRAY');mod.count=2
 bpy.context.view_layer.update();duplicated=audit(out,render=False)
 assert any(f['kind']=='feature_count' for f in duplicated['failures']),duplicated
 results.append(dict(case='evaluated_modifier_changes_panel_count',rejected=True,failures=duplicated['failures']))
 obj.modifiers.remove(mod);bpy.context.view_layer.update()
 # Removing one actual feature, without changing its declaration, must fail.
 obj=bpy.data.objects['shoe__door0'];obj.vertex_groups.remove(obj.vertex_groups['panel_upper'])
 try:audit(out,render=False)
 except ValueError as e:results.append(dict(case='removed_actual_panel_binding',rejected=True,reason=str(e)))
 else:raise AssertionError('Missing actual feature accepted')
Path(args[3]).write_text(json.dumps(dict(status='passed',tests=results),indent=2));print('ACTUAL_SURFACE_MESH_REGRESSIONS_PASSED',results)
