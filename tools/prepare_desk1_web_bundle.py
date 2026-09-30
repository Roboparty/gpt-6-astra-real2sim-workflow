"""Package this session's actual Desk1 source excerpts; no network call."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/research/desk1_web_sources_20260930'

def main():
    candidates=json.loads((BASE/'specification_candidates.json').read_text(encoding='utf-8'))
    ledger=json.loads((BASE/'query_attempt_ledger.json').read_text(encoding='utf-8'))
    queries=[{'id':f'q{i+1:03d}','query':q['q']} for i,q in enumerate(q for c in ledger['calls'] for q in c.get('search_queries',[]))]
    sources=[]
    for key in ['ycb_icar2015','ycb_arxiv2015v1']:
        row=next(s for s in candidates['sources'] if s['id']==key)
        rel='snapshots/'+key+'_table_numeric_excerpt.txt';path=BASE/rel
        sources.append({'id':key,'url':row['url'],'title':row['title'],'publisher':row['publisher'],
            'retrieved_at':'2026-09-30T06:52:59Z',
            'type':'research_paper','snapshot_path':rel,'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    objects=[]
    mapping={'domino_sugar_box':'domino_sugar_box','chocolate_pudding_box':'chocolate_jello_box',
             'strawberry_banana_gelatin_box':'red_jello_box','expo_large_marker':'expo_marker'}
    for row in candidates['objects']:
        key=mapping[row['id']];priors=[]
        for dimension in row['dimension_candidates']:
            raw=dimension['source_raw_dimensions']
            if len(raw)==3:
                a=dimension['axis_mapping'];value=[a['front_width'],a['depth_front_to_back'],a['front_height']]
            else:
                a=dimension['axis_mapping'];value=[a['nominal_transverse_size'],a['nominal_transverse_size'],a['end_to_end_length']]
            for sid in dimension['source_ids']:
                priors.append({'parameter':'dimensions','value':value,'unit':'mm','axis_order':['width','depth','height'],
                    'source_id':sid,'dimension_kind':'object','status':'sourced_prior',
                    'uncertainty_fraction':None,'uncertainty_note':dimension['uncertainty'],
                    'claim_locator':next(s['locator'] for s in candidates['sources'] if s['id']==sid)+
                      ('; semantic axes inferred from observed front; paper does not specify axes' if len(raw)==3 else
                       '; transverse duplicated as width/depth only as an unverified circular-envelope hypothesis; conflicts block consumption')})
        objects.append({'object_id':key,'identity_match':'family','priors':priors,
            'unresolved':[row['image_identity']['sku_match'],row['image_identity']['back_face'],
                          'Published nominal reference dimensions; this photographed instance and tolerance are not independently measured.']})
    row=next(s for s in candidates['sources'] if s['id']=='expo_chisel')
    rel='snapshots/expo_chisel_feature_excerpt.txt';path=BASE/rel
    sources.append({'id':'expo_chisel','url':row['url'],'title':row['title'],'publisher':row['publisher'],
        'retrieved_at':'2026-09-30T07:12:11Z','type':'manufacturer','snapshot_path':rel,
        'snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    objects[-1]['details']=[{'parameter':'tip_family','value':'Current EXPO chisel variant supports varying line widths; the source image does not reveal the capped tip.',
        'source_id':'expo_chisel','status':'sourced_prior','claim_locator':'Product Details, Features, line 87',
        'uncertainty_note':'Family-level hypothesis; hidden tip and retail SKU unconfirmed. Do not expose a chisel nib as an observed detail.'}]
    bundle={'schema':'real2sim.web-research/1','source_sha256':'f125bdbe59e6e978d22e5143131291a1ef5206239928007a01d26aabb1bb9578',
            'queries':queries,'sources':sources,'objects':objects,
            'source_inspection_derivative':candidates['source_image'],
            'research_ledger':'query_attempt_ledger.json','search_budget_registration':'observed counts; no preregistered cap before earlier lookup'}
    (BASE/'web_research.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'queries':len(queries),'sources':len(sources),'objects':len(objects)}))

if __name__=='__main__':main()
