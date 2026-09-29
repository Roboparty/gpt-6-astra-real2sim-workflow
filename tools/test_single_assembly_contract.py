"""Stdlib contract fixtures only; not a Blender, image or physical-scene test.

Run: python tools/test_single_assembly_contract.py
"""
import copy
import json
from itertools import combinations
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.contracts import ContractError
from r2s.structure import file_sha,review_contract


def fixture(count):
    assemblies=[]
    for index in range(count):
        owner=f'furniture_{index}'
        assemblies.append(dict(entity=owner,parts=[dict(id='base',object=owner+'_base'),dict(id='top',object=owner+'_top')],
            joints=[dict(parts=['base','top'],anchor_world=[0,0,.4],tolerance_m=.005)],
            source_observation_ids=['synthetic_observation'],floor_supports=[dict(part='base',plane_z=0,tolerance_m=.005)]))
    scene=dict(model_version=1,objects=[dict(id=a['entity']) for a in assemblies],
               structure=dict(schema='real2sim.assembly/1',assemblies=assemblies))
    owners={p['object']:a['entity'] for a in assemblies for p in a['parts']}
    audit=dict(status='passed',failures=[],source_model_sha256='1'*64,source_scene_sha256='2'*64,
               evaluated_visible_meshes=True,assemblies=[dict(entity=a['entity'],ownership_checked=True,
                   joints_checked=[dict(parts=['base','top'],status='pass')],floor_checked=[dict(part='base',status='pass')],
                   source_landmarks=[dict(id='synthetic_landmark')],isolated_views=['fixture_evidence.txt']) for a in assemblies],
               interassembly_checks=[dict(parts=list(pair),owners=[owners[p] for p in pair],intersects=False,penetration_sample_m=0)
                   for pair in combinations(sorted(owners),2) if owners[pair[0]]!=owners[pair[1]]])
    review=dict(geometry_freeze_sha256='1'*64,model_version=1,per_object=[dict(entity=a['entity'],status='pass',
                findings='Synthetic contract fixture, not a visual judgement',evidence=['fixture_evidence.txt']) for a in assemblies])
    return scene,audit,review


def run():
    results=[]
    with tempfile.TemporaryDirectory(prefix='r2s-single-assembly-contract-') as directory:
        path=Path(directory)
        (path/'fixture_evidence.txt').write_text('Synthetic schema evidence only; this is not an image or mesh audit.')
        artifacts=['fixture_evidence.txt','structural_audit.json']
        def check(name,scene,audit,review,should_reject=False):
            audit=copy.deepcopy(audit)
            audit['evidence_hashes']={'fixture_evidence.txt':file_sha(path/'fixture_evidence.txt')}
            (path/'structural_audit.json').write_text(json.dumps(audit))
            binding=dict(model_sha256='1'*64,scene_sha256='2'*64,structural_audit_sha256=file_sha(path/'structural_audit.json'))
            try:review_contract(path,review,artifacts,scene,binding)
            except ContractError as exc:
                assert should_reject,(name,str(exc));results.append(dict(name=name,rejected=True));return
            assert not should_reject,name+' incorrectly accepted'
            results.append(dict(name=name,rejected=False))

        empty,empty_audit,empty_review=fixture(0)
        check('empty_furniture_not_enabled',empty,empty_audit,empty_review,True)
        single,one_audit,one_review=fixture(1)
        assert one_audit['interassembly_checks']==[]
        check('single_assembly_empty_cross_pairs',single,one_audit,one_review)
        for field,value in [('ownership_checked',False),('joints_checked',[]),('floor_checked',[]),
                            ('source_landmarks',[]),('isolated_views',[])]:
            bad=copy.deepcopy(one_audit);bad['assemblies'][0][field]=value
            check('single_still_requires_'+field,single,bad,one_review,True)
        bad_scene=copy.deepcopy(single);bad_scene['structure']['assemblies'][0]['joints']=[]
        check('single_disconnected_parts',bad_scene,one_audit,one_review,True)
        for field,value in [('interassembly_checks',None),('evaluated_visible_meshes',False),('failures',[dict(kind='disconnected_joint')])]:
            bad=copy.deepcopy(one_audit);bad[field]=value
            check('single_invalid_'+field,single,bad,one_review,True)

        for count in (2,3):
            scene,audit,review=fixture(count)
            assert len(audit['interassembly_checks'])==count*(count-1)//2*4
            check(f'{count}_assemblies_complete_pairs',scene,audit,review)
            missing=copy.deepcopy(audit);missing['interassembly_checks'].pop()
            check(f'{count}_assemblies_missing_pair',scene,missing,review,True)
        scene,audit,review=fixture(2)
        for label,change in [
            ('empty',lambda rows:rows.clear()),
            ('duplicate_replaces_missing',lambda rows:rows.__setitem__(-1,copy.deepcopy(rows[0]))),
            ('reversed_duplicate',lambda rows:rows.append(dict(rows[0],parts=list(reversed(rows[0]['parts'])),owners=list(reversed(rows[0]['owners']))))),
            ('unknown_part',lambda rows:rows[0].update(parts=['unknown',rows[0]['parts'][1]])),
            ('same_owner_pair',lambda rows:rows[0].update(parts=['furniture_0_base','furniture_0_top'],owners=['furniture_0','furniture_0'])),
            ('wrong_owner',lambda rows:rows[0].update(owners=['furniture_1','furniture_0']))]:
            bad=copy.deepcopy(audit);change(bad['interassembly_checks'])
            check('cross_pairs_'+label,scene,bad,review,True)
    print(json.dumps(dict(status='passed',scope='Synthetic contract fixtures; no Blender or physical validation',tests=results),indent=2))
    print('SINGLE_ASSEMBLY_EMPTY_CROSS_PAIRS_AND_EXACT_MULTI_COVERAGE_OK')


if __name__=='__main__':run()
