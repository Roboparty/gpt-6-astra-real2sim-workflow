"""Reopen final exports and run the additional loading demonstration in a new QA attempt."""
import sys,os,json,shutil,subprocess,hashlib
from pathlib import Path
from r2s.core import Workflow
root=Path(__file__).resolve().parents[1];branch=sys.argv[1];w=Workflow(root/'case'/branch)
if not w.valid('validate'):raise RuntimeError('Final executable validation must pass first')
val=Path(w.state['stages']['validate']['directory']);base=root/'qa'/branch;base.mkdir(parents=True,exist_ok=True);num=max([int(p.name) for p in base.iterdir() if p.is_dir() and p.name.isdigit()]+[0])+1;out=base/f'{num:04d}';out.mkdir()
for name in ['scene_dynamic.xml','scene.xml','scene.json','dynamics_audit.json','backend_options.json']:shutil.copyfile(val/name,out/name)
os.symlink(val/'meshes',out/'meshes',target_is_directory=True)
params=w.config['stages']['export']['parameters'];blender=params['blender'];sources={name:hashlib.sha256((val/name).read_bytes()).hexdigest() for name in ['scene.blend','scene.glb','scene.usdc','scene_dynamic.xml','authority_geometry_audit.json']};(out/'input_manifest.json').write_text(json.dumps(dict(branch=branch,validation_attempt=w.state['stages']['validate']['attempt'],sources=sources),indent=2))
for ext,kind in [('glb','glb'),('usdc','usd')]:
 p=subprocess.run([blender,'-b','-t','4','--python-exit-code','12','--python',str(root/'case/reimport_check.py'),'--',str(val/f'scene.{ext}'),str(val/'authority_geometry_audit.json'),str(out/f'reimport_{kind}.json')],capture_output=True,text=True);(out/f'reimport_{kind}.log').write_text(p.stdout+'\n'+p.stderr)
 if p.returncode:raise RuntimeError('Final reimport failed: '+kind)
env=os.environ.copy();env.update(MUJOCO_GL='egl',MUJOCO_EGL_DEVICE_ID=str(params.get('cuda_visible_devices','0')))
p=subprocess.run([sys.executable,str(root/'case/dynamic_demo.py'),str(out)],capture_output=True,text=True,env=env);(out/'loading_test.log').write_text(p.stdout+'\n'+p.stderr)
if p.returncode:raise RuntimeError('Final loaded simulation failed; inspect QA log')
result=dict(status='passed',branch=branch,qa_attempt=num,reimport_glb=json.loads((out/'reimport_glb.json').read_text()),reimport_usd=json.loads((out/'reimport_usd.json').read_text()),loading=json.loads((out/'loading_test_audit.json').read_text()))
(out/'qa_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(status='passed',branch=branch,directory=str(out),loading=result['loading']),indent=2))
