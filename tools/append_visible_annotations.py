"""Append a fixed annotation inventory without replacing any frozen observation."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from freeze_visible_annotations import sha, validate_annotation


def append(protocol_path,parent_path,inputs,output):
    if output.exists():raise ValueError('Frozen output already exists; retain it')
    protocol=json.loads(protocol_path.read_text());parent=json.loads(parent_path.read_text())
    if protocol['schema']!='real2sim.visible-box-addendum-protocol/1':raise ValueError('Wrong addendum protocol')
    if sha(parent_path)!=protocol['parent_manifest_sha256']:raise ValueError('Parent frozen bytes changed')
    if parent['frames_manifest_sha256']!=protocol['source_frame_manifest_sha256']:raise ValueError('Original frame binding changed')
    if [s['id'] for s in parent['sources']]!=protocol['sources']:raise ValueError('Parent source cohort differs')
    drafts={}
    for path in inputs:
        data=json.loads(path.read_text());key=data['source_id']
        if key in drafts:raise ValueError('Duplicate source addendum')
        drafts[key]=(path,data)
    if set(drafts)!=set(protocol['sources']):raise ValueError('All sources must remain in the addendum')
    result=copy.deepcopy(parent);new_count=0;counts=Counter()
    for original,combined in zip(parent['sources'],result['sources']):
        path,data=drafts[original['id']];validate_annotation(data,original['id'],protocol)
        old_ids={o['id'] for o in original['objects']};new_ids={o['id'] for o in data['objects']}
        if old_ids & new_ids:raise ValueError('Addendum cannot redefine frozen object identities')
        if len(original['frames'])!=protocol['frames_per_source']:raise ValueError('Frame denominator differs')
        combined['objects'].extend(copy.deepcopy(data['objects']))
        combined['observations'].extend(copy.deepcopy(data['observations']))
        combined['annotation_addendum']={'file':str(path),'sha256':sha(path),'object_ids':sorted(new_ids)}
        assert combined['objects'][:len(original['objects'])]==original['objects']
        assert combined['observations'][:len(original['observations'])]==original['observations']
        assert combined['frames']==original['frames']
        new_count+=len(data['observations']);counts.update(r['state'] for r in combined['observations'])
    if new_count!=protocol['expected_new_observations'] or sum(counts.values())!=protocol['expected_combined_observations']:
        raise ValueError('Combined observation denominator differs from protocol')
    result.update(annotation_version=2,parent_manifest={'path':str(parent_path),'sha256':sha(parent_path)},
                  protocol_sha256=sha(protocol_path),script_sha256=sha(__file__),
                  validation_helper_sha256=sha(Path(__file__).with_name('freeze_visible_annotations.py')),
                  scope=protocol['scope'],parent_observations_preserved=True,
                  new_observations=new_count)
    result['coverage']={'sources':len(result['sources']),'frames':sum(len(s['frames']) for s in result['sources']),
                        'objects':sum(len(s['objects']) for s in result['sources']),
                        'observations':sum(counts.values()),'states':dict(counts),
                        'frames_with_observed_boxes':sum(len({o['frame_ordinal'] for o in s['observations'] if o['bbox_xyxy'] is not None}) for s in result['sources'])}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','parent','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--annotation',type=Path,action='append',required=True)
    a=p.parse_args();print(json.dumps(append(a.protocol,a.parent,a.annotation,a.output)['coverage']))
