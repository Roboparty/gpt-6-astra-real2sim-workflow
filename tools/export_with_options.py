"""Run the real shared export, then make the USD representation deterministic."""
import sys,json,subprocess,os,hashlib
from pathlib import Path
from r2s.core import atomic_json
pfile=Path(sys.argv[1]);p=json.loads(pfile.read_text());out=Path(p['output_directory']);params=p['parameters'];env=os.environ.copy()
if 'cuda_visible_devices' in params:env['CUDA_VISIBLE_DEVICES']=str(params['cuda_visible_devices'])
native=Path(next(a['path'] for a in p['input_artifacts']['agent_physics'] if Path(a['path']).name=='model.blend'));derived=out/'export_input'
r=subprocess.run([params['blender'],'-b',str(native),'-t',str(params.get('threads',8)),'--python-exit-code','12','--python',params['export_prepare_script'],'--',str(derived)],capture_output=True,text=True,env=env);(out/'export_prepare.log').write_text(r.stdout+'\n'+r.stderr)
if r.returncode:raise RuntimeError('Authoritative evaluated export preparation failed')
shutil=__import__('shutil');shutil.copyfile(derived/'authority_geometry_audit.json',out/'authority_geometry_audit.json');derived_packet=json.loads(json.dumps(p));replacement=derived/'model.blend'
for dep,artifacts in derived_packet['input_artifacts'].items():
 for a in artifacts:
  if Path(a['path']).name in ['model.blend','scene.blend']:a.update(path=str(replacement),sha256=hashlib.sha256(replacement.read_bytes()).hexdigest(),bytes=replacement.stat().st_size,role='evaluated export copy derived from native input')
derived_packet['authoritative_native_sha256']=hashlib.sha256(native.read_bytes()).hexdigest();derived_path=out/'export_derived_packet.json';atomic_json(derived_path,derived_packet)
r=subprocess.run([sys.executable,'-m','r2s.stage_worker',str(derived_path)],capture_output=True,text=True,env=env);(out/'base_export_worker.log').write_text(r.stdout+'\n'+r.stderr)
if r.returncode:raise RuntimeError('Shared export failed; inspect base_export_worker.log')
(out/'response.json').rename(out/'base_export_response.json')
(out/'scene.blend').rename(out/'scene_evaluated.blend');shutil.copyfile(native,out/'scene.blend')
if (out/'scene.usdc').exists():(out/'scene.usdc').rename(out/'scene_unadjusted.usdc')
r=subprocess.run([params['blender'],'-b',str(out/'scene_evaluated.blend'),'-t',str(params.get('threads',8)),'--python-exit-code','12','--python',params['usd_adapter_script'],'--',str(out/'scene.usdc')],capture_output=True,text=True,env=env);(out/'usd_adapter.log').write_text(r.stdout+'\n'+r.stderr)
if r.returncode:raise RuntimeError('Evaluated USD export failed; inspect usd_adapter.log')
audit=json.loads((out/'geometry_audit.json').read_text());authority=json.loads((out/'authority_geometry_audit.json').read_text());errors={key:max(abs(a-b) for va,vb in zip(value['world_aabb'],audit['entities'][key]['world_aabb']) for a,b in zip(va,vb)) for key,value in authority['entities'].items()};assert max(errors.values())<.0002,'Export changed authoritative native geometry';audit['authority_comparison']={'status':'passed','maximum_bound_error_m':max(errors.values()),'per_entity_errors_m':errors,'source_native_sha256':authority['source_native_sha256']};audit['usd_export_adapter']=json.loads((out/'usd_export_adapter.json').read_text());atomic_json(out/'geometry_audit.json',audit)
files=[str(f.relative_to(out)) for f in sorted(out.rglob('*')) if f.is_file() and f.name not in {'packet.json','response.json','record.json','stdout.log','stderr.log'}]
atomic_json(out/'response.json',dict(status='complete',artifacts=files,evidence=['native authoritative modifier-evaluated geometry captured before exporter cleanup','actual shared Blender/GLB/USD export and per-entity comparison to native authority','USD evaluated meshes with stable camera identity'],reasoning_summary='Native editable Blender is copied unchanged. Export geometry is baked before normal cleanup, preventing Solidify displacement. Bounds agree with the authoritative native scene; separate reimport checks still required.'))
