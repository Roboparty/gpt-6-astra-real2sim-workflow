"""Accept the actual C fit at native camera stage only; preserve other pending stages."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow,atomic_json
from r2s.media import file_hash

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,required=True);p.add_argument('--fit',type=Path,required=True)
    p.add_argument('--original-web-report',type=Path);a=p.parse_args()
    w=Workflow(a.case);artifact=next(x for x in w.state['stages']['validate_web_research']['outputs'] if Path(x['path']).name=='web_research_report.json')
    fit=json.loads(a.fit.read_text())
    revalidation=None
    if fit['web_report_sha256']!=artifact['sha256']:
        if a.original_web_report is None or file_hash(a.original_web_report)!=fit['web_report_sha256']:raise ValueError('Fit used a different accepted web report')
        original=json.loads(a.original_web_report.read_text());current=json.loads(Path(artifact['path']).read_text())
        keys=['bundle_sha256','queries','objects','model_priors','model_details','conflicts']
        if any(original.get(k)!=current.get(k) for k in keys):raise ValueError('Changed priors cannot reuse the old camera fit')
        sources=lambda d:[{k:v for k,v in s.items() if k!='snapshot_absolute_path'} for s in d['sources']]
        if sources(original)!=sources(current):raise ValueError('Changed source evidence cannot reuse the old camera fit')
        revalidation={'original_fit_web_report_sha256':fit['web_report_sha256'],'revalidated_web_report_sha256':artifact['sha256'],
            'verified_identical_fields':keys+['source metadata and snapshot hashes excluding relocation path'],
            'new_camera_fit_performed':False,'original_fit_and_hash_preserved':True}
    result=w.execute('agent_calibrate');assert result=='awaiting_agent';out=Path(w.state['stages']['agent_calibrate']['directory'])
    shutil.copyfile(a.fit,out/'calibration.json')
    artifacts=['calibration.json']
    if revalidation:atomic_json(out/'web_revalidation.json',revalidation);artifacts.append('web_revalidation.json')
    atomic_json(out/'submitted.json',{'status':'complete','artifacts':artifacts,
        'evidence':['Actual four-start C fit, source-bound corner residuals and accepted primary-source archive'],
        'reasoning_summary':'Single-image camera/cuboid fit with external nominal family priors; retain worsened same-image heldout error, uncertain metric scale and absent GT.',
        'parameters':{'web_research_consumption':{'report_sha256':artifact['sha256'],'used_priors':fit['web_consumption']}}})
    assert w.accept('agent_calibrate',out/'submitted.json')
    receipt={'status':'native_camera_consumption_passed','fit_sha256':file_hash(a.fit),'accepted_report_sha256':artifact['sha256'],
        'accepted_calibration_artifact':w.state['stages']['agent_calibrate']['outputs'][0],
        'validation_scope':'Actual executable web gate and actual camera-fit acceptance; room/model/material/render/review/export stages of this native case remain unperformed',
        'sota_established':False,'accepted_as_best_method':False,'revalidation':revalidation}
    atomic_json(a.case/'camera_consumption_receipt.json',receipt);print(json.dumps(receipt))

if __name__=='__main__':main()
