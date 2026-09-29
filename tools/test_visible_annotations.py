"""Reject missing observations, invented hidden boxes and changed source bindings."""
import copy
import json
from pathlib import Path
import tempfile

from freeze_visible_annotations import freeze, validate_annotation


def main():
    repo=Path(__file__).resolve().parents[1]
    protocol_path=repo/'docs/research/ANNOTATION_PROTOCOL_20260929.json'
    protocol=json.loads(protocol_path.read_text())
    sources=protocol['sources'];inputs=[repo/'docs/research/annotations_20260929'/f'{s}.initial.json' for s in sources]
    base=json.loads(inputs[0].read_text());results=[]
    def reject(name, mutate):
        data=copy.deepcopy(base);mutate(data)
        try:validate_annotation(data,sources[0],protocol)
        except (ValueError,TypeError,KeyError):results.append({'case':name,'rejected':True})
        else:raise AssertionError('Accepted invalid annotation: '+name)
    reject('drop_missing_observation',lambda d:d['observations'].pop())
    reject('duplicate_replaces_observation',lambda d:d['observations'].__setitem__(-1,copy.deepcopy(d['observations'][0])))
    reject('switch_object_identity',lambda d:d['observations'][0].update(object_id='replacement_object'))
    reject('infer_hidden_box',lambda d:d['observations'][-1].update(state='out_of_frame',bbox_xyxy=[0,0,20,20]))
    reject('nan_coordinate',lambda d:d['observations'][0].update(bbox_xyxy=[0,0,float('nan'),20]))
    reject('outside_image',lambda d:d['observations'][0].update(bbox_xyxy=[0,0,961,20]))
    reject('zero_area',lambda d:d['observations'][0].update(bbox_xyxy=[1,0,1,20]))
    reject('missing_reason',lambda d:d['observations'][0].update(reason=''))
    reject('boolean_frame',lambda d:d['observations'][0].update(frame_ordinal=False))
    reject('first_frame_unseen_identity',lambda d:d['observations'][0].update(state='ambiguous',bbox_xyxy=None))
    frames=repo/'docs/research/evidence/heartbeat_0825/frames.json'
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp);out=directory/'frozen.json'
        actual=freeze(protocol_path,frames,inputs,out)
        assert actual['coverage']['observations']==36
        for name,frame_path,submitted,dest in [('missing_source',frames,inputs[:-1],directory/'missing.json'),
                                               ('overwrite_frozen_output',frames,inputs,out)]:
            try:freeze(protocol_path,frame_path,submitted,dest)
            except ValueError:results.append({'case':name,'rejected':True})
            else:raise AssertionError(name)
        changed=directory/'changed-frames.json';changed.write_bytes(frames.read_bytes()+b'\n')
        try:freeze(protocol_path,changed,inputs,directory/'changed.json')
        except ValueError:results.append({'case':'changed_frame_manifest','rejected':True})
        else:raise AssertionError('Changed frame provenance accepted')
    print(json.dumps({'status':'passed','positive_observations':36,'negative_cases':results,
                      'scope':'Contract and source binding checks, not semantic annotation accuracy'},indent=2))


if __name__=='__main__':main()
