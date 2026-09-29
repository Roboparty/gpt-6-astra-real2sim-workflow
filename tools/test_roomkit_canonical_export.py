"""Actual RoomKit -> Blender audit/export -> MuJoCo regression; CPU only.

Run with the existing Python runtime containing numpy and mujoco. Creates a new
output tree, retaining every subprocess log and generated artifact on failure.
"""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import mujoco
import numpy as np

repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'workflow'))
from r2s.shell_collision import SURFACES,shell_boxes
from r2s.structure import file_sha,review_contract

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--blender',required=True);p.add_argument('--skills',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);args=p.parse_args()
args.output.mkdir(parents=True,exist_ok=False);start=time.monotonic();results=[]
env=dict(os.environ,R2S_CPU='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
env.pop('R2S_STRUCTURE_NO_RENDER',None)

def write(path,data):path.write_text(json.dumps(data,indent=2))
def run(command,directory,label,no_render=False,reject=None):
    settings=dict(env)
    if no_render:settings['R2S_STRUCTURE_NO_RENDER']='1'
    with (directory/(label+'.log')).open('w') as log:
        process=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=settings,timeout=300)
    if reject:
        assert process.returncode!=0 and reject in (directory/(label+'.log')).read_text(),label
    else:assert process.returncode==0,(label,directory)
def blender(script,argv,model=None):
    return [args.blender,'-b',*([str(model)] if model else []),'-t','2','--python-exit-code','12','--python',str(repo/'workflow/r2s'/script),'--',*map(str,argv)]

room=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3,thickness=.1,preserve_full_shell=True)
camera=dict(position=[0,-1.5,1.5],rotation_world_to_cv=[[1,0,0],[0,0,-1],[0,1,0]],focal_px=100,principal_point=[80,60],image_size=[160,120])
def fixture(empty):
    objects=[]
    for surface in SURFACES:
        b=shell_boxes(room,surface)[0]
        objects.append(dict(id=surface,kind=surface,structural_role='room_shell',position=b['position'],dimensions=b['dimensions'],evidence=['synthetic fixture'],confidence=.1))
    objects.append(dict(id='lamp',kind='lamp',structural_role='fixed_luminaire',position=[0,0,2.8],dimensions=[.3,.3,.1],evidence=['synthetic fixture'],confidence=.1))
    part=dict(id='lamp',assembly='lamp',kind='box',position=[0,0,2.8],size=[.3,.3,.1],rotation=[0,0,0],collision='box',prior_status='assumed',prior_source='synthetic regression only')
    structure=dict(schema='real2sim.assembly/1',assemblies=[],unexpected_interpenetration_tolerance_m=.002)
    parts=[part]
    if empty:structure.update(scope='empty_room',shell_objects=list(SURFACES),fixed_luminaire_objects=['lamp'])
    else:
        # Non-origin, rotated known category exposes wrong recipe/frame fallback.
        yaw=.35;position=[.9,.4,.35];size=[.6,.4,.7]
        world=[position[0]-.3*math.cos(yaw)+.2*math.sin(yaw),position[1]-.3*math.sin(yaw)-.2*math.cos(yaw),0]
        q=[world[0],1.5,world[1]+1.5];uv=[q[0]/q[2]*100+80,q[1]/q[2]*100+60]
        objects.append(dict(id='sofa',kind='sofa',position=position,dimensions=size,evidence=['synthetic fixture'],confidence=.1))
        parts.append(dict(part,id='sofa_body',assembly='sofa',position=position,size=size,rotation=[0,0,yaw]))
        structure['assemblies']=[dict(entity='sofa',parts=[dict(id='sofa_body',object='sofa_body')],joints=[],source_observation_ids=['corner'],frame=dict(yaw_rad=yaw),floor_supports=[dict(part='sofa_body',plane_z=0,tolerance_m=.002)],fit=dict(landmarks=[dict(id='corner',part='sofa_body',world=world,uv=uv)]))]
    scene=dict(schema_version='real2sim.scene/1.0',case_id='roomkit_export_fixture',branch='A',units='m',up_axis='Z',model_version=1,room=copy.deepcopy(room),camera=copy.deepcopy(camera),objects=objects,structure=structure)
    return scene,dict(schema='roomkit/1',units='m',parts=parts)

for empty in [False,True]:
    name='empty_room' if empty else 'rotated_furniture';directory=args.output/name;directory.mkdir()
    scene,parts=fixture(empty);spec=directory/'scene.json';manifest=directory/'roomkit_parts.json';write(spec,scene);write(manifest,parts)
    run(blender('blender_roomkit_generation.py',[manifest,spec,directory,args.skills]),directory,'adapter')
    model=directory/'model.blend';generated=json.loads(spec.read_text())
    # Match actual evaluated bounds to metadata, exactly as native build_geometry.
    run(blender('blender_metadata.py',[spec,'update',directory/'metadata_sync.json'],model),directory,'metadata')
    run(blender('blender_structure.py',[spec,directory],model),directory,'structure',no_render=not empty)
    audit=json.loads((directory/'structural_audit.json').read_text());assert audit['status']=='passed',audit['failures']
    if empty:
        review=dict(geometry_freeze_sha256=file_sha(model),model_version=1,per_object=[dict(entity=o['id'],status='pass',findings='Synthetic inventory',evidence=['furniture_source_view.png']) for o in scene['objects']],checks=dict(empty_room=dict(status='pass',findings='Synthetic full source view',evidence=['furniture_source_view.png'])))
        review_contract(directory,review,[f.name for f in directory.iterdir() if f.is_file()],json.loads(spec.read_text()),dict(model_sha256=file_sha(model),scene_sha256=file_sha(spec),structural_audit_sha256=file_sha(directory/'structural_audit.json')))
    run(blender('blender_export.py',[spec,directory,'--geometry-only'],model),directory,'export')
    geometry=json.loads((directory/'geometry_audit.json').read_text())
    assert set(geometry['entities'])=={o['id'] for o in scene['objects']}
    assert not any('__collision' in name for name in geometry['entities'])
    run([sys.executable,str(repo/'workflow/r2s/simulation.py'),str(spec),str(directory)],directory,'simulation')
    engine=mujoco.MjModel.from_xml_path(str(directory/'scene.xml'));data=mujoco.MjData(engine);mujoco.mj_forward(engine,data)
    count=0
    for obj in generated['objects']:
        if obj['id'] in SURFACES:continue
        for index,proxy in enumerate(obj['parameters']['collision_proxies']):
            gid=mujoco.mj_name2id(engine,mujoco.mjtObj.mjOBJ_GEOM,obj['id']+f'_agent_collision{index}');assert gid>=0
            np.testing.assert_allclose(data.geom_xpos[gid],proxy['position'],atol=1e-6)
            np.testing.assert_allclose(engine.geom_size[gid]*2,proxy['dimensions'],atol=1e-6)
            assert engine.geom_contype[gid]==1;count+=1
    assert not any('__collision' in (mujoco.mj_id2name(engine,mujoco.mjtObj.mjOBJ_GEOM,i) or '') for i in range(engine.ngeom))
    results.append(dict(case=name,status='passed',canonical_proxy_count=count,visual_entities=len(geometry['entities']),structural_status=audit['status'],simulation=json.loads((directory/'simulation_audit.json').read_text())['status']))

for label,mutate,error in [
    ('all_none',lambda s,p:p['parts'][0].update(collision='none'),'entirely collision:none'),
    ('conflicting_proxies',lambda s,p:s['objects'][-1].update(parameters=dict(collision_proxies=[dict(shape='box')])),'Choose RoomKit collision policies'),
    ('empty_room_name_mismatch',lambda s,p:p['parts'][0].update(id='lamp_mesh'),'one matching mesh/entity name')]:
    directory=args.output/label;directory.mkdir();scene,parts=fixture(True);mutate(scene,parts)
    spec=directory/'scene.json';manifest=directory/'roomkit_parts.json';write(spec,scene);write(manifest,parts)
    run(blender('blender_roomkit_generation.py',[manifest,spec,directory,args.skills]),directory,'adapter',reject=error)
    results.append(dict(case=label,status='rejected_as_expected'))
write(args.output/'summary.json',dict(status='passed',tests=results,wall_seconds=time.monotonic()-start,gpu_hours=0,scope='Synthetic adapter/engine regression; no real reconstruction acceptance',implementation_sha256=file_sha(repo/'workflow/r2s/blender_roomkit_generation.py'),test_sha256=file_sha(__file__)))
print(json.dumps(dict(status='passed',cases=len(results),output=str(args.output))))
