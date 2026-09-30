"""Require auditable downstream decisions about validated web priors.

This records consumption; it does not prove scene dimensions or material truth.
"""
import json
from pathlib import Path
from .contracts import ContractError
from .media import file_hash

CONSUMERS={'agent_calibrate','agent_calibrate_room','agent_model','agent_materials'}

def check_consumption(workflow,stage,response):
    if stage not in CONSUMERS:return
    outputs=workflow.state['stages']['validate_web_research']['outputs']
    matches=[a for a in outputs if Path(a['path']).name=='web_research_report.json']
    if len(matches)!=1:raise ContractError('Consumer requires one validated web report')
    artifact=matches[0]
    if file_hash(artifact['path'])!=artifact['sha256']:raise ContractError('Web report changed')
    report=json.loads(Path(artifact['path']).read_text(encoding='utf-8-sig'))
    if report.get('status')!='validated':raise ContractError('Web report is not validated')
    decision=response.get('parameters',{}).get('web_research_consumption')
    if not isinstance(decision,dict) or decision.get('report_sha256')!=artifact['sha256']:
        raise ContractError('Consumer must bind its web_research_consumption to the accepted report hash')
    used=decision.get('used_priors')
    if not isinstance(used,list) or any(not isinstance(x,dict) for x in used):raise ContractError('used_priors must be a list of explicit decisions')
    eligible={(p['object_id'],p['parameter']) for p in report.get('model_priors',[])}
    eligible.update((p['object_id'],p['parameter']) for p in report.get('model_details',[]) if p['parameter'].strip().casefold()!='dimensions')
    for prior in used:
        if (prior.get('object_id'),prior.get('parameter')) not in eligible:
            raise ContractError('Consumer used an unknown, shipping or unresolved conflicting prior')
        if not isinstance(prior.get('application'),str) or not prior['application'].strip():
            raise ContractError('Each used prior needs an application to a camera, object or material parameter')
    if not used and (not isinstance(decision.get('unconsumed_reason'),str) or not decision['unconsumed_reason'].strip()):
        raise ContractError('Consumer must use eligible priors or state why they were not used')
