"""Real Desk1 partial native workflow; stop before unperformed room/model stages."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow,atomic_json
from r2s.media import file_hash

def submit(w,stage,artifacts,summary,parameters=None):
    out=Path(w.state['stages'][stage]['directory'])
    atomic_json(out/'submitted.json',{'status':'complete','artifacts':artifacts,'evidence':['Accepted real source photo and archived primary-source excerpts'],
        'reasoning_summary':summary,'parameters':parameters or {}})
    return w.accept(stage,out/'submitted.json')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--bundle-directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    expected='f125bdbe59e6e978d22e5143131291a1ef5206239928007a01d26aabb1bb9578'
    if file_hash(a.source)!=expected:raise ValueError('Original source changed')
    atomic_json(a.output/'case.json',{'id':'desk1-real-web-gate','mode':'single','workflow_profile':'quality_v2',
        'inputs':[{'path':str(a.source),'sha256':expected}],
        'provenance':{'kind':'real_photograph','status':'verified','evidence':['SimFoundry paper Desk1 source RGB, retained exact original bytes']},
        'formal_test':True,'web_research':{'max_queries':32,'max_sources':12},'stages':{'preprocess':{'parameters':{'max_edge':1280}}}})
    w=Workflow(a.output);result=w.run();assert result['stage']=='agent_observe'
    out=Path(result['directory'])
    atomic_json(out/'observation.json',{'source_sha256':expected,'objects':['domino_sugar_box','chocolate_jello_box','red_jello_box','expo_marker'],
        'scope':'single view; visible packaging and capped marker; backside and camera unknown'})
    atomic_json(out/'furniture_observation.json',{'source_sha256':expected,'acceptance_before_fit':True,
        'targets':[{'entity':'desk_support','parts':['table_top'],'constraints':['horizontal support prior'],
            'observations':[{'id':'desk_visible_top','visibility':'partial','evidence':'visible dark support plane under all four foreground objects'}],
            'uncertain':['unseen table extents, underside and legs are not reconstructed in this partial gate test']}],
        'acceptance_scope':'source/evidence gate only; no furniture assembly or room delivery acceptance'})
    submit(w,'agent_observe',['observation.json','furniture_observation.json'],'Identify visible packaging, source support and unobserved regions from the sole real image.')
    result=w.run();assert result['stage']=='agent_identify';out=Path(result['directory'])
    bundle=json.loads((a.bundle_directory/'web_research.json').read_text(encoding='utf-8'));files=['web_research.json']
    shutil.copyfile(a.bundle_directory/'web_research.json',out/'web_research.json')
    for src in bundle['sources']:
        rel=src['snapshot_path'];(out/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.bundle_directory/rel,out/rel);files.append(rel)
    for rel in ['query_attempt_ledger.json','specification_candidates.json']:
        shutil.copyfile(a.bundle_directory/rel,out/rel);files.append(rel)
    submit(w,'agent_identify',files,'Transfer published nominal reference dimensions as family priors; retain exact-SKU uncertainty, marker conflict and actual failed web attempts.')
    result=w.run(until='validate_web_research');assert result['status']=='completed_until'
    artifact=next(x for x in w.state['stages']['validate_web_research']['outputs'] if Path(x['path']).name=='web_research_report.json')
    receipt={'status':'native_partial_gate_passed','required_stages_completed':['ingest','preprocess','agent_observe','agent_identify','validate_web_research'],
        'web_report':artifact,'source_sha256':expected,'remaining_native_stages':'calibration/room/model/material/render/review/export not yet delivered by this smoke case',
        'no_full_workflow_acceptance_claim':True,'workflow_source':str(Path(__file__).resolve().parents[1]/'workflow')}
    atomic_json(a.output/'partial_gate_receipt.json',receipt);print(json.dumps(receipt))

if __name__=='__main__':main()
