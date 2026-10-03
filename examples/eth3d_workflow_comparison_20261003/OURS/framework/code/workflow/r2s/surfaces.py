"""Source-bound surface classification. Position accuracy cannot certify panel topology."""
import json
from pathlib import Path
from .contracts import ContractError
from .structure import evidence_file,file_sha

def enabled(packet):
    return packet.get('refinement',{}).get('limits',{}).get('surface_contract_version',0)>=1

def read(attempt,name,files):
    return json.loads(evidence_file(attempt,name,files).read_text())

def observation(attempt,files,packet):
    from PIL import Image
    data=read(attempt,'surface_observation.json',files)
    original=read(attempt,'observation.json',files);source=original.get('appearance_source',packet.get('appearance_source'))
    if data.get('schema')!='real2sim.surface-observation/1' or data.get('source_sha256')!=source['sha256']:
        raise ContractError('Surface observations require the current original-image binding')
    regions=data.get('regions',[]);targets={r['entity'] for r in original['appearance_targets']}
    if {r.get('entity') for r in regions}!=targets or len({r.get('id') for r in regions})!=len(regions):
        raise ContractError('Surface observations must cover every priority entity with unique regions')
    image=Image.open(source['path']).convert('RGB');feature_ids=set()
    if file_sha(source['path'])!=source['sha256']:raise ContractError('Original image changed')
    for r in regions:
        if not r.get('pattern') or type(r.get('allow_repeated_relief')) is not bool or not r.get('features'):
            raise ContractError('Surface region needs a pattern, repetition decision and features')
        box=r.get('source_box_xyxy',[])
        if len(box)!=4 or not all(type(v) is int for v in box) or not (0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height):
            raise ContractError('Invalid surface source crop')
        crop=Image.open(evidence_file(attempt,r['source_crop'],files)).convert('RGB');expected=image.crop(box)
        if crop.size!=expected.size or crop.tobytes()!=expected.tobytes():
            raise ContractError('Surface source crop was altered or does not match the original')
        for e in r.get('manufacturer_images',[]):
            if not e.get('url') or file_sha(evidence_file(attempt,e['artifact'],files))!=e.get('sha256'):
                raise ContractError('Manufacturer image evidence is missing or changed')
        if r.get('product_candidate') and r.get('manufacturer_image_review') not in ['consistent','conflict','unavailable']:
            raise ContractError('Candidate identification needs an explicit product-image structure review')
        if r.get('manufacturer_image_review')=='consistent' and not r.get('manufacturer_images'):
            raise ContractError('Catalogue text alone cannot confirm surface topology')
        for f in r['features']:
            if not f.get('id') or f['id'] in feature_ids or not f.get('description'):
                raise ContractError('Surface features need unique IDs and concrete observations')
            feature_ids.add(f['id']);category=f.get('classification')
            if category not in ['geometry','albedo','lighting','uncertain']:
                raise ContractError('Classify surface edges as geometry, albedo, lighting or uncertain')
            if category=='geometry' and (type(f.get('count')) is not int or f['count']<1 or not f.get('depth_cues') or f.get('confidence',0)<.75):
                raise ContractError('Geometric surface detail needs count, depth cues and supported confidence')
            if category=='uncertain' and not f.get('alternatives'):
                raise ContractError('Ambiguous surface lines need alternative explanations')
    return data

def realization(attempt,files,observation_sha=None):
    obs=read(attempt,'surface_observation.json',files);model=read(attempt,'surface_realization.json',files)
    actual=file_sha(Path(attempt)/'surface_observation.json')
    if model.get('observation_sha256')!=actual or (observation_sha and observation_sha!=actual):
        raise ContractError('Surface realization uses observations different from the accepted source stage')
    observed={r['id']:r for r in obs['regions']};regions=model.get('regions',[])
    if len(regions)!=len(observed) or {r['id'] for r in regions}!=set(observed):
        raise ContractError('Surface realization omits or duplicates regions')
    for r in regions:
        source=observed[r['id']]
        if r.get('pattern')!=source['pattern'] or r.get('entity')!=source['entity']:
            raise ContractError('Model surface type differs from the observed type')
        expected={f['id']:f for f in source['features']};features=r.get('features',[])
        if len(features)!=len(expected) or {f['id'] for f in features}!=set(expected):
            raise ContractError('Every observed surface feature requires an explicit realization decision')
        if not r.get('inspection_objects') or not r.get('normal_world') or not r.get('up_world'):
            raise ContractError('Surface needs executable front/raking inspection bindings')
        for f in features:
            evidence=expected[f['id']];kind=f.get('representation')
            if kind not in ['geometry','albedo','micro_bump','lighting','omitted']:
                raise ContractError('Unknown surface representation')
            if kind=='geometry':
                if evidence['classification']!='geometry' or f.get('count')!=evidence['count'] or not f.get('mesh_refs'):
                    raise ContractError('Unsupported geometric surface detail or feature-count mismatch')
            elif evidence['classification']=='geometry':
                raise ContractError('Observed geometric surface features cannot silently disappear')
            if kind=='micro_bump' and (evidence['classification']!='albedo' or not 0<f.get('depth_m',0)<=.0005):
                raise ContractError('Ambiguous or macroscopic relief cannot be smuggled into a bump map')
            if evidence['classification']=='uncertain' and kind not in ['albedo','omitted']:
                raise ContractError('Ambiguous linework cannot become grooves, slats or displacement')
    return obs,model

def check_response(workflow,name,attempt,response):
    if name not in ['agent_observe','agent_model','agent_review_geometry','agent_review']:return
    packet=json.loads((Path(attempt)/'packet.json').read_text())
    if not enabled(packet) or response['status']=='needs_input':return
    files=response.get('artifacts',[])
    if name=='agent_observe':observation(attempt,files,packet)
    elif name=='agent_model':
        accepted=[a for a in packet['input_artifacts']['agent_observe'] if Path(a['path']).name=='surface_observation.json']
        if len(accepted)!=1:raise ContractError('No accepted surface observations')
        realization(attempt,files,accepted[0]['sha256'])
    elif name in ['agent_review_geometry','agent_review']:
        build='build_geometry' if name=='agent_review_geometry' else 'build_render'
        artifacts={Path(a['path']).name:a for a in packet['input_artifacts'][build]}
        ref=artifacts.get('surface_audit.json')
        if not ref or file_sha(ref['path'])!=ref['sha256']:raise ContractError('Missing current executable surface audit')
        audit=json.loads(Path(ref['path']).read_text());review=read(attempt,'surface_review.json',files)
        binding=artifacts.get('render_binding.json')
        if not binding or file_sha(binding['path'])!=binding['sha256']:raise ContractError('Missing current render binding')
        rendered=json.loads(Path(binding['path']).read_text())
        if audit.get('model_sha256')!=rendered['model_sha256']:raise ContractError('Surface audit belongs to another model')
        if review.get('audit_sha256')!=ref['sha256']:raise ContractError('Surface review is not bound to current geometry')
        regions={r['id']:r for r in audit['regions']};rows=review.get('regions',[])
        if len(rows)!=len(regions) or {r['id'] for r in rows}!=set(regions):raise ContractError('Surface review omitted a region')
        for row in rows:
            r=regions[row['id']]
            for key in ['topology_and_count','relief_vs_appearance','proportions_and_contrast']:
                check=row.get(key,{})
                if check.get('status') not in ['pass','revise'] or not check.get('findings'):raise ContractError('Missing surface falsification check: '+key)
                if response['status']=='complete' and check['status']!='pass':raise ContractError('Unresolved surface mismatch cannot pass')
            refs=row.get('evidence',[]);hashes={file_sha(evidence_file(attempt,p,files)) for p in refs}
            required={audit['images'][p] for p in [r['source_crop'],r['front_view'],r['raking_view']]}
            if not required<=hashes:raise ContractError('Surface review needs original crop and actual neutral front/raking views')
        if response['status']=='complete' and (audit.get('status')!='passed' or audit.get('failures')):
            raise ContractError('Actual surface geometry contradicts its source evidence')
