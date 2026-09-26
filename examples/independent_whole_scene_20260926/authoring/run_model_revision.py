import sys,json,subprocess,os
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow
w=Workflow(R/'case')
assert not (R/'case/runs/run.lock').exists(),'Wait for the active workflow before revision'
if len(sys.argv)>1:w.revise('agent_model',sys.argv[1])
print(w.run(until='agent_model'),flush=True)
out=Path(w.state['stages']['agent_model']['directory'])
subprocess.run(['/home/wqz/real2sim_fresh_20260921/runtime/blender-4.5.3-linux-x64/blender','-b','-t','4','--python-exit-code','12','--python',str(R/'authoring/build_scene.py')],check=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':'6'})
print('accepted rebuilt model',w.accept('agent_model',out/'response.json'),flush=True);print(w.run(retry_failed=True),flush=True)
