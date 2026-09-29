"""Pure rigid-coordinate regression; no Blender run or historical pilot mutation."""
import copy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import ContractError
from r2s.pose_annotations import update_xy_yaw_annotations


def assembly(entity):
    return dict(entity=entity,frame=dict(position=[1,2,0],yaw_rad=.2),parts=[dict(id='base',object=entity+'_base'),dict(id='top',object=entity+'_top')],
        joints=[dict(parts=['base','top'],anchor_world=[2,2,3],tolerance_m=.006)],
        floor_supports=[dict(part='base',plane_z=0,tolerance_m=.005)],
        fit=dict(landmarks=[dict(id='corner',world=[1,3,4],uv=[100,200],sigma_px=3,
                 visibility='observed',projected=[99,199],error_px=1.414,
                 measured_world_point=[1,3,4],distance_to_bound_mesh_m=0)],
                 median_error_px=1.414,max_error_px=1.414),source_observation_ids=['original'])


def run():
    scene=dict(objects=[dict(id='wardrobe',position=[1,2,5],dimensions=[2,3,4],parameters={}),
                        dict(id='other',position=[9,8,7],dimensions=[1,1,1],parameters={'collision_proxies':[{'shape':'box'}]})],
               room=dict(height=3),camera=dict(position=[4,5,6]),dynamics=dict(not_applicable='Static source scene'),
               structure=dict(assemblies=[assembly('wardrobe'),assembly('other')]))
    before=copy.deepcopy(scene);action=dict(entity='wardrobe',xy_m=[.01,-.02],yaw_deg=90,reason='Synthetic transform oracle')
    # The helper tests exact rigid math; the Blender caller retains the pilot's
    # existing +/- 0.03 m and +/- 2 degree action bounds.
    result,receipt=update_xy_yaw_annotations(scene,[action]);target=result['structure']['assemblies'][0]
    def close(actual,expected):assert all(math.isclose(a,b,abs_tol=1e-12) for a,b in zip(actual,expected)),(actual,expected)
    close(target['joints'][0]['anchor_world'],[1.01,2.98,3])
    close(target['fit']['landmarks'][0]['world'],[.01,1.98,4])
    close(target['frame']['position'],[1.01,1.98,0])
    assert math.isclose(target['frame']['yaw_rad'],.2+math.pi/2)
    assert target['fit']['landmarks'][0]['uv']==[100,200]
    assert target['fit']['landmarks'][0]['sigma_px']==3 and target['fit']['landmarks'][0]['visibility']=='observed'
    assert target['joints'][0]['tolerance_m']==.006
    assert target['floor_supports']==before['structure']['assemblies'][0]['floor_supports']
    assert not {'projected','error_px','measured_world_point','distance_to_bound_mesh_m'}&set(target['fit']['landmarks'][0])
    assert 'median_error_px' not in target['fit'] and 'max_error_px' not in target['fit']
    assert result['structure']['assemblies'][1]==before['structure']['assemblies'][1]
    assert result['objects']==before['objects'] and result['room']==before['room'] and result['camera']==before['camera']
    assert result['dynamics']==before['dynamics'] and scene==before
    assert receipt['entities'][0]['joint_anchors_updated']==1
    # A no-yaw translation and zero action preserve fixed z/observations.
    translated,_=update_xy_yaw_annotations(scene,[dict(action,yaw_deg=0)])
    close(translated['structure']['assemblies'][0]['joints'][0]['anchor_world'],[2.01,1.98,3])
    zero,_=update_xy_yaw_annotations(scene,[dict(action,xy_m=[0,0],yaw_deg=0)])
    close(zero['structure']['assemblies'][0]['fit']['landmarks'][0]['world'],[1,3,4])
    yaw_only_frame=copy.deepcopy(scene);yaw_only_frame['structure']['assemblies'][0]['frame'].pop('position')
    updated,_=update_xy_yaw_annotations(yaw_only_frame,[dict(action,yaw_deg=2)])
    assert set(updated['structure']['assemblies'][0]['frame'])=={'yaw_rad'}
    assert math.isclose(updated['structure']['assemblies'][0]['frame']['yaw_rad'],.2+math.radians(2))
    bad_inputs=[]
    for mutate in [lambda s:s['dynamics'].update(hinges=[{'moving_body':'wardrobe'}]),
                   lambda s:s['dynamics'].update(deformables=[{'entity':'wardrobe'}]),
                   lambda s:s['dynamics'].update(unknown_recipe={}),
                   lambda s:s['objects'][0]['parameters'].update(collision_proxies=[{'shape':'box'}]),
                   lambda s:s['room'].update(collision_proxies={'wall_back':[]}),
                   lambda s:s['structure']['assemblies'][0]['frame'].update(quaternion=[1,0,0,0]),
                   lambda s:s['structure']['assemblies'][0]['joints'][0].update(anchor_world=[0,float('nan'),0])]:
        bad=copy.deepcopy(scene);mutate(bad);bad_inputs.append((bad,[action]))
    bad_inputs.extend([(scene,[action,action]),(scene,[dict(action,entity='missing')]),
                       (scene,[dict(action,xy_m=[0,0,1])]),(scene,[dict(action,yaw_deg=float('nan'))]),
                       (scene,[dict(action,z_m=.1)])])
    for bad,actions in bad_inputs:
        saved=json.dumps(bad,sort_keys=True)
        try:update_xy_yaw_annotations(bad,actions)
        except ContractError:pass
        else:raise AssertionError('Unsupported recipe or malformed action accepted')
        assert json.dumps(bad,sort_keys=True)==saved,'Failed update mutated the original scene'
    print(json.dumps(dict(status='passed',scope='Pure XY/yaw annotation math only',negative_cases=len(bad_inputs),
                          source_and_other_entities_unchanged=True)))
    print('POSE_ANNOTATIONS_RIGID_XY_YAW_UV_PRESERVATION_AND_REJECTION_OK')


if __name__=='__main__':run()
