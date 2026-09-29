"""Bind complete manual visible-box inventories to original frozen image hashes.

Validation checks provenance/coverage and representation, not semantic correctness.
No segmentation masks, camera estimates, or metric ground truth are generated.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_annotation(data, source_id, protocol):
    if data.get('schema')!='real2sim.visible-box-annotations/1' or data.get('source_id')!=source_id:
        raise ValueError('Annotation schema/source mismatch')
    objects=data.get('objects',[]);ids=[o.get('id') for o in objects]
    if len(objects)!=protocol['objects_per_source'] or len(set(ids))!=len(ids) or any(not isinstance(i,str) or not i for i in ids):
        raise ValueError('Wrong or duplicate object inventory')
    if any(not isinstance(o.get(k),str) or not o[k].strip() for o in objects for k in ('label','identity_description')):
        raise ValueError('Missing persistent identity description')
    expected={(f,o) for f in range(protocol['frames_per_source']) for o in ids};seen=set()
    for row in data.get('observations',[]):
        frame=row.get('frame_ordinal');key=(frame,row.get('object_id'))
        if type(frame) is not int or key not in expected or key in seen:
            raise ValueError('Missing/duplicate/unknown frame-object observation')
        seen.add(key);state=row.get('state');box=row.get('bbox_xyxy')
        if state not in protocol['states'] or row.get('confidence') not in {'high','medium','low'}:
            raise ValueError('Invalid visibility/confidence label')
        if not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('All observations require a visibility or boundary explanation')
        if state in {'out_of_frame','ambiguous'}:
            if box is not None:raise ValueError('Unobserved or ambiguous object cannot have inferred box')
        else:
            if not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) for x in box):
                raise ValueError('Visible extent requires four finite coordinates')
            x0,y0,x1,y1=box;w,h=protocol['image_size']
            if not 0<=x0<x1<=w or not 0<=y0<y1<=h:raise ValueError('Box outside original raster')
        if frame==0 and state not in {'visible','partial'}:
            raise ValueError('Selected persistent object must be observed in first frozen frame')
    if seen!=expected:raise ValueError('Incomplete fixed observation denominator')
    return dict(Counter(r['state'] for r in data['observations']))


def freeze(protocol_path, frames_path, inputs, output):
    if output.exists():raise ValueError('Frozen outputs are immutable; use a new version')
    protocol=json.loads(protocol_path.read_text());frames=json.loads(frames_path.read_text())
    if protocol['schema']!='real2sim.visible-box-annotation-protocol/1':raise ValueError('Wrong protocol')
    if sha(frames_path)!=protocol['source_frame_manifest_sha256']:raise ValueError('Frozen source manifest bytes changed')
    sources={s['id']:s for s in frames['sources']}
    if len(sources)!=len(frames['sources']) or set(sources)!=set(protocol['sources']):raise ValueError('Source cohort changed')
    annotations={}
    for path in inputs:
        data=json.loads(path.read_text());key=data['source_id']
        if key in annotations:raise ValueError('Duplicate source submission')
        annotations[key]=(path,data)
    if set(annotations)!=set(protocol['sources']):raise ValueError('Missing source submission; retain blocked source')
    result={'schema':'real2sim.visible-box-freeze/1','protocol_sha256':sha(protocol_path),
            'frames_manifest_sha256':sha(frames_path),'script_sha256':sha(__file__),
            'data_role':protocol['data_role'],'annotation_provenance':protocol['annotation_provenance'],
            'boundary_uncertainty_px_assumed':protocol['boundary_uncertainty_px_assumed'],
            'scope':protocol['scope'],'sources':[]}
    counts=Counter()
    for source_id in protocol['sources']:
        source=sources[source_id];path,data=annotations[source_id]
        counts.update(validate_annotation(data,source_id,protocol))
        selected=source['selected_frames']
        if len(selected)!=protocol['frames_per_source'] or any(f['image_size']!=protocol['image_size'] for f in selected):
            raise ValueError('Frozen input dimensions/count changed')
        if len({f['sha256'] for f in selected})!=len(selected):raise ValueError('Repeated frame bytes')
        result['sources'].append({'id':source_id,'source_video_sha256':source['expected_source_sha256'],
            'annotation_file':str(path),'annotation_sha256':sha(path),'objects':data['objects'],
            'frames':[{'ordinal':i,'path':f['path'],'sha256':f['sha256'],'image_size':f['image_size'],
                       'decoded_frame_index':f['decoded_frame_index'],'pts_seconds':f['best_effort_timestamp_time']} for i,f in enumerate(selected)],
            'observations':data['observations']})
    if sum(counts.values())!=protocol['expected_observations']:raise ValueError('Protocol observation total mismatch')
    result['coverage']={'sources':len(result['sources']),'frames':sum(len(s['frames']) for s in result['sources']),
                        'objects':sum(len(s['objects']) for s in result['sources']),
                        'observations':sum(counts.values()),'states':dict(counts)}
    result['validation']='Representation and manifest binding passed; semantic/manual review is separate, no image accuracy assertion'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','frames','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--annotation',type=Path,action='append',required=True)
    a=p.parse_args();print(json.dumps(freeze(a.protocol,a.frames,a.annotation,a.output)['coverage']))
