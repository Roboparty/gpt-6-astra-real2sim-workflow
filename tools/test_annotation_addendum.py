"""Additions cannot rewrite the old cohort, identities, or missing observations."""
import copy
import json
from pathlib import Path
import tempfile

from append_visible_annotations import append
from freeze_visible_annotations import sha

repo=Path(__file__).resolve().parents[1];research=repo/'docs/research'
protocol=research/'ANNOTATION_ADDENDUM_PROTOCOL_20260929.json'
parent=research/'annotations_20260929/frozen_v1.json'
cfg=json.loads(protocol.read_text());old=json.loads(parent.read_text());before=sha(parent)
inputs=[research/'annotations_20260929'/f'{s}.addendum.initial.json' for s in cfg['sources']]
rows=[]
with tempfile.TemporaryDirectory(prefix='annotation_append_') as temp:
    root=Path(temp);target=root/'v2.json'
    result=append(protocol,parent,inputs,target)
    for a,b in zip(old['sources'],result['sources']):
        assert a['frames']==b['frames'] and a['objects']==b['objects'][:len(a['objects'])]
        assert a['observations']==b['observations'][:len(a['observations'])]
    assert result['coverage']['observations']==72 and sha(parent)==before
    rows.append({'case':'all_old_observations_objects_frames_unchanged','passed':True})
    def reject(name,fn):
        try:fn()
        except ValueError:rows.append({'case':name,'passed':True})
        else:raise AssertionError(name+' was accepted')
    reject('missing_source',lambda:append(protocol,parent,inputs[:-1],root/'missing.json'))
    reject('duplicate_source',lambda:append(protocol,parent,inputs+[inputs[0]],root/'duplicate.json'))
    reject('overwrite_frozen',lambda:append(protocol,parent,inputs,target))
    changed_parent=root/'changed_parent.json';changed_parent.write_bytes(parent.read_bytes()+b'\n')
    reject('parent_bytes_changed',lambda:append(protocol,changed_parent,inputs,root/'changed.json'))
    for name,mutate in [('identity_collision',lambda d:d['objects'][0].update(id=old['sources'][0]['objects'][0]['id'])),
                        ('missing_observation',lambda d:d['observations'].pop()),
                        ('unseen_anchor',lambda d:next(x for x in d['observations'] if x['frame_ordinal']==5).update(state='out_of_frame',bbox_xyxy=None))]:
        d=json.loads(inputs[0].read_text());mutate(d)
        if name=='identity_collision':
            previous=json.loads(inputs[0].read_text())['objects'][0]['id']
            for row in d['observations']:
                if row['object_id']==previous:row['object_id']=d['objects'][0]['id']
        path=root/(name+'.json');path.write_text(json.dumps(d))
        reject(name,lambda path=path,name=name:append(protocol,parent,[path]+inputs[1:],root/(name+'_out.json')))
    for name,mutate in [('changed_frame_binding',lambda d:d.update(source_frame_manifest_sha256='0'*64)),
                        ('changed_denominator',lambda d:d.update(expected_combined_observations=71))]:
        d=copy.deepcopy(cfg);mutate(d);path=root/(name+'.json');path.write_text(json.dumps(d))
        reject(name,lambda path=path,name=name:append(path,parent,inputs,root/(name+'_out.json')))
assert sha(parent)==before
print(json.dumps({'status':'passed','total':len(rows),'tests':rows,'parent_sha256':before,
                  'scope':'Frozen annotation append invariants only; not semantic label or reconstruction accuracy'},indent=2))
