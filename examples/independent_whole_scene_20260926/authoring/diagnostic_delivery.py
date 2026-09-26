"""Export/reload an evaluated candidate without overriding the visual acceptance gate.
These are explicitly diagnostic checks, never Workflow success records.
"""
import sys,json,os,subprocess,shutil,hashlib
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'));from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');assert w.valid('build_render');build=Path(w.state['stages']['build_render']['directory']);root=R/'delivery_candidate';root.mkdir(exist_ok=True)
assert not (root/'diagnostic_status.json').exists(),'Do not overwrite diagnostic attempt'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
packet=dict(stage='export',case_id=w.config['id'],workflow_profile='quality_v2',parameters=w.config['stages']['export']['parameters'],input_artifacts={'build_render':w.state['stages']['build_render']['outputs']},output_directory=str(root/'export'),scope='DIAGNOSTIC ONLY: visual gate not overridden; not official workflow export completion')
(root/'export').mkdir();atomic_json(root/'export/packet.json',packet)
env={**os.environ,'PYTHONPATH':str(R/'repo/workflow'),'CUDA_VISIBLE_DEVICES':'6','BLENDER_USER_CONFIG':str(R/'runtime_config')};results={}
def run(name,argv):
 p=subprocess.run(argv,env=env,capture_output=True,text=True);(root/(name+'.log')).write_text(p.stdout+'\n'+p.stderr);results[name]={'returncode':p.returncode,'status':'passed' if p.returncode==0 else 'failed'};atomic_json(root/'diagnostic_status.json',dict(scope='Evaluated candidate diagnostics, not visual acceptance or formal workflow completion',source_build=str(build),source_model_sha256=sha(build/'scene.blend'),checks=results));return p.returncode==0
if run('export',[sys.executable,'-m','r2s.stage_worker',str(root/'export/packet.json')]):
 blender=packet['parameters']['blender']
 run('reload',[blender,'-b','-t','2','--python-exit-code','12','--python',str(R/'repo/tools/reload_scene_exports.py'),'--',str(root/'export')])
 run('static_engine',[sys.executable,str(R/'repo/workflow/r2s/simulation.py'),str(root/'export/scene.json'),str(root/'export')])
 from r2s.evaluation import glb_check
 try:results['glb']=glb_check(root/'export/scene.glb',['floor','ceiling','wall_back','wall_front','wall_left','wall_right'])
 except Exception as e:results['glb']={'status':'failed','error':str(e)}
atomic_json(root/'diagnostic_status.json',dict(scope='Evaluated candidate diagnostics, not visual acceptance or formal workflow completion',source_build=str(build),source_model_sha256=sha(build/'scene.blend'),checks=results,physics={'hinges':'disabled','cloth':'disabled','soft_bodies':'disabled','static_probe':'see static_engine; not calibrated real furniture dynamics'}))
print(json.dumps(results,indent=2))
