"""Prepare a scoped LabWeft patch for actual reference-route adaptations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--labweft',type=Path,required=True);a=p.parse_args();env={**os.environ,'PYTHONIOENCODING':'utf-8'}
    r=subprocess.run([sys.executable,str(a.labweft),'context',str(a.workspace),'--full'],capture_output=True,encoding='utf-8',env=env,check=True);d=json.loads(r.stdout);root=Path(__file__).resolve().parents[1];path='docs/research/evidence/gpt6_peers_20260930/comparison_with_rgb_revision.json';values=json.loads((root/path).read_text())['records']
    def ev(path,locator='document'):
        f=next(x for x in d['files'].values() if x['source']=='code' and x['path']==path and not x.get('missing'));return {'file_id':f['id'],'sha256':f['sha256'],'locator':locator}
    report=ev('docs/research/DESK1_GPT6_PROJECT_COMPARISON_20260930.md');numeric=ev(path);catalog=ev('docs/research/GPT6_PROJECT_CATALOG_20260930.json');study='study-desk1-reference-adaptations';nodes=[]
    rows=[[x['method'],f"{x['foreground_rgb_mae_0_255']:.3f}",f"{x['full_frame_rgb_mae_0_255']:.3f}"] for x in values]
    nodes.append({'id':study,'kind':'module','label':'单图几何参考适配仍有图像偏差 / Single-image geometry adaptations retain image mismatch',
        'parent_id':'study-desk1-spec-priors','status':'recorded','description':'Four current GPT6 project sources checked; two reference mechanisms actually adapted. Not independent Astra or full-framework performance ranking.',
        'attrs':{'role':'study','design':{'factor':'Pi3X/MoGe3 geometry reference with common editable-instance adapter and paired RGB background revision',
            'held_constant':['one original RGB SHA','four manual instance masks','common carton/cylinder adapter across two routes','same renderer settings'],
            'co_varying':['reference resolution/intrinsics/scale estimator','Pi3X sugar-height assumed anchor vs MoGe metric estimate','nativeB/C use explicit2D fitting, adaptations use point-derived primitives','not matched independent GPT6 versions or agent budgets'],
            'selection_rule':'report both initial and revised whole scenes; no per-object best stitching'},
            'study_summary':{lang:{'intro':intro,'columns':['Condition','Foreground MAE /255','Full-frame MAE /255'],'rows':rows,'note':note} for lang,intro,note in [
                ('en','One case, two genuinely inferred reference routes and shared static adapters.','Adaptations, not original full projects. Manual masks; no true3D/physics/independentGpt6 ranking.'),
                ('zh','同一Desk1，实际运行两条几何参考路线与共享静态构建器。','仅流程适配，不是作者框架原版复跑；人工轮廓，没有真实三维/物理或独立GPT6排名。')]}},'evidence':[report,numeric,catalog]})
    for i in [3,4,5,6]:
        x=values[i];ident='pi3x' if i in [3,5] else 'moge3';variant='initial' if i in [3,4] else 'rgb-background';cell='cell-desk1-ref-'+ident+'-'+variant;run='run-desk1-ref-'+ident+'-'+variant;ref=ev(path,f'$.records[{i}]')
        metrics={k:x[k] for k in ['foreground_rgb_mae_0_255','full_frame_rgb_mae_0_255','mean_instance_prebevel_footprint_iou']};config={'reference':ident,'background':variant,'eval_protocol':'desk1-manual-masks-peer-adaptations-20260930','dataset_version':'Desk1-f125bdbe-original-singleRGB'}
        nodes.append({'id':cell,'kind':'cell','label':ident+' '+variant,'parent_id':study,'status':'recorded','description':'One complete static scene condition; not a new training seed or author-provided Desk1 result.','attrs':{'config':config},'evidence':[ref]})
        nodes.append({'id':run,'kind':'run','label':ident+' '+variant+' / Static adaptation','parent_id':cell,'status':'completed','description':'Actual saved scene/source and virtual renders, read-only blend audit; all4objects retained.',
            'attrs':{'run_id':'gpt6_peers_20260930/'+x['method'],'seed':2026,'code_revision':None,'source_code_binding':'Actual builder/runner hashes in receipts; current metadata patches not assigned historically','config':config,'dataset_version':config['dataset_version'],'eval_protocol':config['eval_protocol'],'metrics':metrics,'model_sha256':x['model_sha256']},'evidence':[ref]})
    nodes.append({'id':'artifact-gpt6-peer-source-catalog','kind':'artifact','label':'四个GPT6项目与当前Real2Gym地址 / Four GPT6 sources and resolved Real2Gym URL','parent_id':study,'status':'recorded',
        'description':'Author GPT6 claims and frozen official repos audited; old404 retained, current canonical repo public. Missing matched original Desk1 outputs remains unknown.',
        'attrs':{'scope':'Public source availability/route analysis, not performance or authenticated historic model sessions'},'evidence':[catalog,report]})
    target=a.workspace/'.research/gpt6_peer_patch.json';target.write_text(json.dumps({'base_revision':d['revision'],'reason':'Link genuine Pi3X/MoGe3 static adaptations and paired background revision, preserving scope, originals, failures and no-full-framework ranking.','nodes':nodes,'edges':[]},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'patch':str(target),'nodes':len(nodes),'base_revision':d['revision']}))

if __name__=='__main__':main()
