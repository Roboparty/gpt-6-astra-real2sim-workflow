"""Synthetic engine regressions, NOT room-task success or material calibration.

Run with the repository's MuJoCo/SciPy environment. --output-dir retains the
independent hinge/cloth/soft XML, trajectories and numerical audit artifacts.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import numpy as np
import mujoco

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import ContractError
from r2s.dynamics import apply_features,export_and_test,validate_requested_features
from r2s.profiles import physics_options,stages_for

REFERENCE='''<mujoco model="synthetic_optional_dynamics">
  <compiler angle="radian" inertiafromgeom="auto"/>
  <option timestep="0.0001" gravity="0 0 -9.81"/>
  <worldbody>
    <geom name="floor" type="plane" size="3 3 .1"/>
    <body name="cabinet" pos=".3 .1 0" quat=".9238795325 0 0 .3826834324">
      <geom name="cabinet_marker" type="box" pos="0 -.6 .5" size=".03 .03 .03"/>
    </body>
    <body name="door" pos="0 0 1">
      <geom name="door_static" type="box" pos=".2 0 0" size=".2 .02 .2"/>
    </body>
    <body name="cloth_piece" pos="1 0 1">
      <geom name="cloth_static" type="box" size=".1 .1 .002"/>
    </body>
    <body name="soft_piece" pos="-1 0 1">
      <geom name="soft_static" type="sphere" size=".05"/>
    </body>
  </worldbody>
</mujoco>'''
HINGE=dict(id='door_hinge',moving_body='door',parent_body='cabinet',
           moving_part_segmented=True,evidence=['synthetic separately authored door'],
           parameter_provenance='assumed',axis_local=[0,0,1],anchor_local=[0,0,0],
           range_rad=[-.7,.7],mass_kg=.5,inertia_diag_kgm2=[.007,.02,.02],
           center_of_mass_local=[.2,0,0],damping=.05,frictionloss=.001,test_torque_nm=.2)
CLOTH=dict(id='cloth_flex',entity='cloth_piece',kind='cloth',
           points_local=[[0,0,0],[.1,0,0],[0,.1,0],[.1,.1,0]],
           elements=[[0,1,2],[1,3,2]],pinned_vertices=[0,1],mass_kg=.02,
           young_pa=1000,poisson=.3,thickness_m=.005,contact_radius_m=.002,
           rest_shape_matched=True,replace_static_geometry=True,
           parameter_provenance='assumed',evidence=['synthetic flat four-vertex patch'])
SOFT=dict(id='soft_flex',entity='soft_piece',kind='soft_body',
          points_local=[[0,0,0],[.08,0,0],[0,.08,0],[0,0,.08]],
          elements=[[0,1,2,3]],pinned_vertices=[0,1,2],mass_kg=.02,
          young_pa=5000,poisson=.3,contact_radius_m=.002,
          rest_shape_matched=True,replace_static_geometry=True,
          parameter_provenance='assumed',evidence=['synthetic one-tetrahedron patch'])


def rejected(fn,exception=ContractError):
    try:fn()
    except exception:return
    raise AssertionError('Invalid or unrequested dynamics was accepted')


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    reference=out/'scene_static.xml';reference.write_text(REFERENCE)
    source_hash=hashlib.sha256(reference.read_bytes()).hexdigest()
    static_model=mujoco.MjModel.from_xml_path(str(reference));static_data=mujoco.MjData(static_model)
    mujoco.mj_forward(static_model,static_data)
    assert physics_options({})==dict(hinges=False,cloth=False,soft_bodies=False)
    assert not any(name in {'agent_physics','agent_review_physics'} for name,_,_ in stages_for({'workflow_profile':'quality_v2'}))
    for key in ('hinges','cloth','soft_bodies'):
        stages={name for name,_,_ in stages_for({'workflow_profile':'quality_v2','physics':{key:True}})}
        assert {'agent_physics','agent_review_physics'}<=stages
        rejected(lambda key=key:physics_options({'physics':{key:'false'}}),ValueError)
    disabled=out/'disabled';disabled.mkdir(exist_ok=True)
    assert export_and_test(reference,{},disabled)['status']=='disabled'
    assert not (disabled/'scene_dynamic.xml').exists()
    na={'dynamics':{'not_applicable':{'cloth':{'reason':'No fabric in synthetic case','evidence':['fixture specification']}}}}
    assert export_and_test(reference,na,disabled,{'cloth':True})['status']=='not_applicable'
    rejected(lambda:export_and_test(reference,{},disabled,{'cloth':True}))
    rejected(lambda:validate_requested_features({}, {'cloth':'false'}))

    cases={'hinges':{'hinges':[HINGE]},'cloth':{'deformables':[CLOTH]},'soft_bodies':{'deformables':[SOFT]}}
    results={}
    for key,recipe in cases.items():
        definitions=copy.deepcopy(recipe);definitions.update(timestep_s=.0001,test_steps=800)
        scene={'dynamics':definitions}
        rejected(lambda:export_and_test(reference,scene,disabled))
        rejected(lambda:export_and_test(reference,scene,disabled,{key:False}))
        destination=out/key;destination.mkdir(exist_ok=True)
        result=export_and_test(reference,scene,destination,{key:True})
        assert result['status']=='passed' and result['steps']==800 and not any(result['solver_warnings'])
        assert result['static_reference_modified'] is False
        assert hashlib.sha256(reference.read_bytes()).hexdigest()==source_hash
        trajectory=json.loads((destination/'dynamics_trajectory.json').read_text())
        assert len(trajectory)>1 and trajectory[-1]['time']>trajectory[0]['time']>0
        dynamic=mujoco.MjModel.from_xml_path(str(destination/'scene_dynamic.xml'))
        if key=='hinges':
            assert dynamic.njnt==1 and dynamic.nflex==0
            assert result['joint_ranges_observed_rad']['door_hinge'][1]>.0001
            assert result['maximum_flex_displacement_m']==0
            zero_pose=mujoco.MjData(dynamic);mujoco.mj_forward(dynamic,zero_pose)
            old_id=mujoco.mj_name2id(static_model,mujoco.mjtObj.mjOBJ_BODY,'door')
            new_id=mujoco.mj_name2id(dynamic,mujoco.mjtObj.mjOBJ_BODY,'door')
            assert np.allclose(zero_pose.xpos[new_id],static_data.xpos[old_id],atol=1e-8)
            assert np.allclose(zero_pose.xmat[new_id],static_data.xmat[old_id],atol=1e-8)
        else:
            assert dynamic.nflex==1
            assert result['maximum_flex_displacement_m']>1e-6,'Flex must numerically move'
            fid=mujoco.mj_name2id(dynamic,mujoco.mjtObj.mjOBJ_FLEX,CLOTH['id'] if key=='cloth' else SOFT['id'])
            assert int(dynamic.flex_dim[fid])==(2 if key=='cloth' else 3)
            removed='cloth_static' if key=='cloth' else 'soft_static'
            retained='soft_static' if key=='cloth' else 'cloth_static'
            assert mujoco.mj_name2id(dynamic,mujoco.mjtObj.mjOBJ_GEOM,removed)<0
            assert mujoco.mj_name2id(dynamic,mujoco.mjtObj.mjOBJ_GEOM,retained)>=0
            if key=='soft_bodies':assert result['deformation_checks'][0]['minimum_volume_ratio']>.05
        results[key]=result
        for field,value in [('test_steps',0),('test_steps',-1),('test_steps',1.5),('test_steps',True),
                            ('timestep_s',0),('timestep_s',float('nan'))]:
            bad=copy.deepcopy(scene);bad['dynamics'][field]=value
            rejected(lambda bad=bad:export_and_test(reference,bad,disabled,{key:True}))

    root=ET.fromstring(REFERENCE);original=ET.tostring(root)
    bad_hinges=[dict(HINGE,moving_body='absent'),dict(HINGE,moving_body='cabinet',parent_body='cabinet'),
                dict(HINGE,moving_part_segmented=False),dict(HINGE,axis_local=[0,0,0]),
                dict(HINGE,mass_kg=0),dict(HINGE,mass_kg=float('nan')),
                dict(HINGE,damping=-1),dict(HINGE,test_torque_nm=float('inf')),
                dict(HINGE,range_rad=[1,2]),dict(HINGE,inertia_diag_kgm2=[1,1,3])]
    for hinge in bad_hinges:rejected(lambda hinge=hinge:apply_features(root,{'hinges':[hinge]}))
    for source in (CLOTH,SOFT):
        for field,value in [('entity','absent'),('replace_static_geometry',False),('rest_shape_matched',False),
                            ('mass_kg',0),('mass_kg',float('nan')),('young_pa',float('nan')),
                            ('poisson',.5),('elastic_damping',-1),('maximum_allowed_edge_strain',float('nan')),
                            ('pinned_vertices',[999]),('pinned_vertices',[.5]),('elements',[])]:
            bad=dict(source,**{field:value})
            rejected(lambda bad=bad:apply_features(root,{'deformables':[bad]}))
        free_root=ET.fromstring(REFERENCE)
        ET.SubElement(free_root.find(f"./worldbody/body[@name='{source['entity']}']"),'freejoint')
        rejected(lambda:apply_features(free_root,{'deformables':[source]}))
    assert ET.tostring(root)==original,'apply_features modified caller reference XML'
    assert hashlib.sha256(reference.read_bytes()).hexdigest()==source_hash
    summary=dict(status='passed',scope='synthetic optional-feature engine regression; no room-task or calibration claim',
                 engine_version=mujoco.__version__,static_sha256=source_hash,static_reference_unchanged=True,
                 results=results)
    (out/'optional_dynamics_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    print('OPTIONAL_DYNAMICS_DEFAULT_OFF_HINGE_CLOTH_SOFT_NEGATIVES_OK')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path);args=parser.parse_args()
    if args.output_dir:run(args.output_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='r2s-optional-dynamics-') as temp:run(Path(temp))
