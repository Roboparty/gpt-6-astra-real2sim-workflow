"""Stdlib single-part/no-joint contract tests; not physical or Blender evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import ContractError
from r2s.structure import file_sha,review_contract


def fixture(part_count):
    parts=[dict(id=f'p{i}',object=f'leaf_part_{i}') for i in range(part_count)]
    joints=[dict(parts=[f'p{i}',f'p{i+1}'],anchor_world=[0,0,.1+i],tolerance_m=.005) for i in range(part_count-1)]
    assembly=dict(entity='leaf',parts=parts,joints=joints,source_observation_ids=['fixture'],floor_supports=[dict(part='p0',plane_z=0,tolerance_m=.005)])
    scene=dict(model_version=1,objects=[dict(id='leaf')],structure=dict(schema='real2sim.assembly/1',assemblies=[assembly]))
    audit=dict(status='passed',failures=[],source_model_sha256='1'*64,source_scene_sha256='2'*64,evaluated_visible_meshes=True,
        assemblies=[dict(entity='leaf',ownership_checked=True,joints_checked=[dict(j,status='pass',measured_anchor_outside_distances_m=[0,0]) for j in joints],
            floor_checked=[dict(part='p0',status='pass')],source_landmarks=[dict(id='fixture')],isolated_views=['evidence.txt'])],interassembly_checks=[])
    review=dict(geometry_freeze_sha256='1'*64,model_version=1,per_object=[dict(entity='leaf',status='pass',findings='Synthetic contract fixture only',evidence=['evidence.txt'])])
    return scene,audit,review


def run():
    results=[]
    with tempfile.TemporaryDirectory(prefix='r2s-single-part-contract-') as tmp:
        path=Path(tmp);(path/'evidence.txt').write_text('Schema evidence only, not an image or simulation.')
        def check(name,scene,audit,review,reject=False,stale_hash=False):
            (path/'structural_audit.json').write_text(json.dumps(audit))
            binding=dict(model_sha256='1'*64,scene_sha256='2'*64,structural_audit_sha256=file_sha(path/'structural_audit.json'))
            if stale_hash:binding['structural_audit_sha256']='0'*64
            try:review_contract(path,review,['structural_audit.json','evidence.txt'],scene,binding)
            except ContractError as exc:
                assert reject,(name,str(exc));results.append(dict(name=name,rejected=True));return
            assert not reject,name+' incorrectly accepted'
            results.append(dict(name=name,rejected=False))

        one,audit,review=fixture(1)
        check('single_part_explicit_zero_internal_joints',one,audit,review)
        for field,value in [('ownership_checked',False),('floor_checked',[]),('source_landmarks',[]),('isolated_views',[]),('joints_checked',None)]:
            bad=copy.deepcopy(audit);bad['assemblies'][0][field]=value
            check('single_requires_'+field,one,bad,review,True)
        bad=copy.deepcopy(audit);bad['assemblies'][0].pop('joints_checked')
        check('single_rejects_missing_joint_list',one,bad,review,True)
        bad=copy.deepcopy(one);bad['structure']['assemblies'][0].pop('joints')
        check('single_requires_explicit_joint_declaration',bad,audit,review,True)
        fake=dict(parts=['p0','invented'],anchor_world=[0,0,0],tolerance_m=.005,status='pass',measured_anchor_outside_distances_m=[0,0])
        bad=copy.deepcopy(audit);bad['assemblies'][0]['joints_checked']=[fake]
        check('single_rejects_fabricated_second_part',one,bad,review,True)
        bad=copy.deepcopy(one);bad['structure']['assemblies'][0]['joints']=[dict(fake,parts=['p0','p0'])]
        check('single_rejects_self_joint',bad,audit,review,True)
        bad=copy.deepcopy(audit);bad['assemblies'].append(copy.deepcopy(bad['assemblies'][0]))
        check('duplicate_assembly_audit',one,bad,review,True)
        check('static_audit_hash_still_required',one,audit,review,True,stale_hash=True)
        bad=copy.deepcopy(review);bad['geometry_freeze_sha256']='0'*64
        check('model_hash_still_required',one,audit,bad,True)
        empty=copy.deepcopy(one);empty['structure']['assemblies']=[]
        check('zero_assemblies_not_enabled',empty,audit,review,True)

        multi,audit,review=fixture(3)
        check('multi_complete_measured_joint_coverage',multi,audit,review)
        for label,edit in [('empty',lambda rows:rows.clear()),('missing',lambda rows:rows.pop()),
            ('duplicate_replaces_missing',lambda rows:rows.__setitem__(1,copy.deepcopy(rows[0]))),
            ('wrong_part',lambda rows:rows[0].update(parts=['p0','invented'])),
            ('wrong_pair',lambda rows:rows[0].update(parts=['p0','p2'])),
            ('wrong_anchor',lambda rows:rows[0].update(anchor_world=[0,0,9])),
            ('relaxed_tolerance',lambda rows:rows[0].update(tolerance_m=.009)),
            ('failed_status',lambda rows:rows[0].update(status='fail')),
            ('missing_measurement',lambda rows:rows[0].pop('measured_anchor_outside_distances_m')),
            ('excess_distance',lambda rows:rows[0].update(measured_anchor_outside_distances_m=[0,.006])),
            ('negative_distance',lambda rows:rows[0].update(measured_anchor_outside_distances_m=[0,-.001])),
            ('nan_distance',lambda rows:rows[0].update(measured_anchor_outside_distances_m=[0,float('nan')]))]:
            bad=copy.deepcopy(audit);edit(bad['assemblies'][0]['joints_checked'])
            check('multi_rejects_'+label,multi,bad,review,True)
        bad=copy.deepcopy(multi);bad['structure']['assemblies'][0]['joints'].pop()
        check('multi_disconnected_graph_still_rejected',bad,audit,review,True)
        reversed_audit=copy.deepcopy(audit);reversed_audit['assemblies'][0]['joints_checked'][0]['parts'].reverse()
        check('reversed_pair_has_same_constraint_identity',multi,reversed_audit,review)
        # Two anchors on the same part pair are distinct physical constraints.
        two,audit,review=fixture(2)
        second=dict(two['structure']['assemblies'][0]['joints'][0],anchor_world=[0,0,.2])
        two['structure']['assemblies'][0]['joints'].append(second)
        audit['assemblies'][0]['joints_checked'].append(dict(second,status='pass',measured_anchor_outside_distances_m=[0,0]))
        check('same_pair_distinct_anchors_checked',two,audit,review)
        bad=copy.deepcopy(audit);bad['assemblies'][0]['joints_checked'][1]=copy.deepcopy(bad['assemblies'][0]['joints_checked'][0])
        check('same_pair_cannot_duplicate_one_anchor',two,bad,review,True)
    print(json.dumps(dict(status='passed',scope='Synthetic contracts only; no new Blender or physical claim',tests=results),indent=2))
    print('SINGLE_PART_NO_JOINT_AND_EXACT_MEASURED_JOINT_COVERAGE_OK')


if __name__=='__main__':run()
