import json, os, sys, shutil, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PY=os.environ.get('R2S_PYTHON',sys.executable)
BL=os.environ.get('R2S_BLENDER') or shutil.which('blender')
if not BL:raise RuntimeError('Set R2S_BLENDER to the Blender executable before initializing a fresh replay')
for branch in ['A','B']:
    out=ROOT/'case'/branch;out.mkdir(parents=True,exist_ok=True)
    cfg=dict(id='utility_single_external_example_'+branch, mode='single',branch=branch,formal_test=True,workflow_profile='quality_v2',
      inputs=[dict(path=str(ROOT/'inputs/utility_room_original.jpg'),sha256='dfe25afbfb885ae9bc377691dd18ebd4259ffa72917ca725e3809ef40624c29c',role='reconstruction')],
      provenance=dict(kind='real_photograph',status='verified',evidence=['source_manifest.json: user attested personally/team photographed on 2026-09-22; no EXIF; no metric truth']),
      physics=dict(hinges=True,cloth=True,soft_bodies=True),refinement=dict(max_revisions=8,max_stagnant=3,max_seconds=7200,surface_contract_version=1),stages={})
    cfg['stages']['preprocess']={'parameters':{'max_edge':1702}}
    for stage in ['build_geometry','build_render','export','validate','report']:
        cfg['stages'][stage]={'command':[PY,'-m','r2s.stage_worker','{packet}'],'parameters':{'blender':BL,'threads':8,'cuda_visible_devices':os.environ.get('R2S_GPU','0')},'timeout_seconds':7200}
    cfg['stages']['export']['command']=[PY,str(ROOT/'tools/export_with_options.py'),'{packet}']
    cfg['stages']['export']['parameters'].update(usd_adapter_script=str(ROOT/'case/export_usd_evaluated.py'),export_prepare_script=str(ROOT/'case/prepare_export_scene.py'))
    cfg['stages']['validate']['command']=[PY,str(ROOT/'tools/validate_with_options.py'),'{packet}']
    cfg['stages']['validate']['parameters']['dynamics_integrator']='discrete'
    target=out/'case.json'
    if target.exists(): raise RuntimeError('Refusing to overwrite existing case')
    target.write_text(json.dumps(cfg,indent=2))
print('Initialized two independent quality_v2 branches')
