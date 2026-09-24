"""Rebuild this frozen example from the authorized original and case-specific code.
Runs real tools; does not create or backfill workflow success states. New visual acceptance
still belongs to an Agent. This recipe is deliberately restricted to this source image.
"""
import argparse,os,sys,json,hashlib,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
photo=root/'inputs/utility_room_original.jpg';expected='dfe25afbfb885ae9bc377691dd18ebd4259ffa72917ca725e3809ef40624c29c'
if hashlib.sha256(photo.read_bytes()).hexdigest()!=expected:raise RuntimeError('This is a frozen-case replay, not a model for another image')
py=os.environ.get('R2S_PYTHON',sys.executable);bl=os.environ.get('R2S_BLENDER') or shutil.which('blender')
if not bl:raise RuntimeError('Set R2S_BLENDER')
gpu=os.environ.get('R2S_GPU','0');env=os.environ.copy();env.update(PYTHONPATH=str(root/'workflow'),CUDA_VISIBLE_DEVICES=gpu,MUJOCO_GL='egl',MUJOCO_EGL_DEVICE_ID=gpu);(root/'evidence').mkdir(exist_ok=True)
def run(name,args):
 with (out/(name+'.log')).open('w') as log:r=subprocess.run(args,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(name+' failed; preserved log in output directory')
 print(name+' completed',flush=True)
def blender(name,input_file,script,args):
 argv=[bl,'-b']+([str(input_file)] if input_file else [])+['-t','8','--python-exit-code','12','--python',str(root/'case'/script),'--']+list(map(str,args));run(name,argv)
run('exterior_texture',[py,str(root/'case/make_exterior.py')]);run('carpet_texture',[py,str(root/'case/make_carpet.py')]);run('furniture_fit',[py,str(root/'case/fit_furniture.py')])
blender('model',None,'build_scene.py',[out/'model','neutral','4'])
(out/'structure').mkdir()
run('structure',[bl,'-b',str(out/'model/model.blend'),'-t','8','--python-exit-code','12','--python',str(root/'workflow/r2s/blender_structure.py'),'--',str(out/'model/scene.json'),str(out/'structure')])
if json.loads((out/'structure/structural_audit.json').read_text())['status']!='passed':raise RuntimeError('Rebuilt furniture failed actual visible-mesh structure audit')
blender('materials',out/'model/model.blend','calibrate_materials.py',[out/'materials']);shutil.copyfile(out/'model/scene.json',out/'materials/scene.json')
blender('lighting',out/'materials/model.blend','calibrate_lighting.py',[out/'lighting','10']);shutil.copyfile(out/'materials/scene.json',out/'lighting/scene.json')
blender('physics_setup',out/'lighting/model.blend','prepare_physics.py',[out/'lighting/scene.json',out/'physics',out/'model/cloth_rest.json'])
def artifact(path):return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
params=dict(blender=bl,threads=8,cuda_visible_devices=gpu,usd_adapter_script=str(root/'case/export_usd_evaluated.py'),export_prepare_script=str(root/'case/prepare_export_scene.py'))
packet=dict(case_id='utility_frozen_replay',stage='export',branch='A',mode='single',workflow_profile='quality_v2',physics_options=dict(hinges=True,cloth=True,soft_bodies=True),input_artifacts={'agent_physics':[artifact(out/'physics/model.blend'),artifact(out/'physics/scene.json')]},output_directory=str(out/'export'),parameters=params);(out/'export').mkdir();(out/'export_packet.json').write_text(json.dumps(packet,indent=2));run('export',[py,str(root/'tools/export_with_options.py'),str(out/'export_packet.json')])
packet.update(stage='validate',input_artifacts={'export':[artifact(out/'export/geometry_audit.json')]},output_directory=str(out/'validate'),parameters=dict(dynamics_integrator='discrete'));(out/'validate').mkdir();(out/'validate_packet.json').write_text(json.dumps(packet,indent=2));run('validate',[py,str(root/'tools/validate_with_options.py'),str(out/'validate_packet.json')])
for ext,kind in [('glb','glb'),('usdc','usd')]:blender('reimport_'+kind,None,'reimport_check.py',[out/f'validate/scene.{ext}',out/'validate/authority_geometry_audit.json',out/f'reimport_{kind}.json'])
run('loaded_dynamics',[py,str(root/'case/dynamic_demo.py'),str(out/'validate')]);run('source_comparison',[py,str(root/'case/compare.py'),str(out/'lighting/lighting.png'),str(out/'comparison')])
result=dict(status='artifacts_rebuilt_and_numeric_checks_passed',source_sha256=expected,manual_visual_review_required=True,scope='Frozen single-image recipe replay; not a new autonomous reconstruction or new visual approval',native_blend='export/scene.blend',glb='export/scene.glb',usd='export/scene.usdc',dynamics='validate/scene_dynamic.xml',video='validate/dynamics_demo.mp4');(out/'REBUILD_RESULT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
