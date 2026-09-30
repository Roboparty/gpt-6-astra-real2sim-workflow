"""Prepare one identity-preserving LabWeft semantic patch from source-bound results."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--labweft',type=Path,required=True);a=p.parse_args()
    env={**os.environ,'PYTHONIOENCODING':'utf-8'}
    context=subprocess.run([sys.executable,str(a.labweft),'context',str(a.workspace),'--full'],capture_output=True,encoding='utf-8',env=env,check=True)
    d=json.loads(context.stdout);root=Path(__file__).resolve().parents[1];evidence='docs/research/evidence/desk1_web_phase_20260930/'
    records=json.loads((root/evidence/'comparison_diagnostics_blend_verified.json').read_text())['records']
    def ev(path,locator='document'):
        matches=[f for f in d['files'].values() if f['source']=='code' and f['path']==path and not f.get('missing')]
        if len(matches)!=1:raise ValueError('Evidence not uniquely indexed: '+path)
        f=matches[0];return {'file_id':f['id'],'sha256':f['sha256'],'locator':locator}
    report=ev('docs/research/DESK1_WEB_COMPARISON_20260930.md');numeric=ev(evidence+'comparison_diagnostics_blend_verified.json')
    protocol=ev('docs/research/DESK1_WEB_PHASE_20260930.json');hreport=ev('docs/research/DESK1_HUNYUAN2_20260930.md')
    nodes=[];edges=[];study='study-desk1-spec-priors'
    rows=[[r['arm'].split('_')[0],'-' if r['same_image_heldout_corner_mean_distance_px'] is None else f"{r['same_image_heldout_corner_mean_distance_px']:.3f}",
           f"{r['foreground_rgb_mae_0_255']:.3f}"] for r in records]
    summary={lang:{'intro':intro,'columns':['Method','Same-image holdout px','RGB MAE /255'],'rows':rows,'note':note}
        for lang,intro,note in [('en','One frozen Desk1 RGB: cuboid parameterization and sourced nominal priors.','A used all corners. Three same-image heldout corners; no independent3D/SOTA.'),
            ('zh','同一Desk1原图：比较正交参数化与联网名义尺寸。','A已使用全部角点；仅3处同图留出点，没有独立三维精度或SOTA。')]}
    nodes.append({'id':study,'kind':'module','label':'联网规格约束未改善同图对齐 / Web specifications did not improve same-image alignment',
        'parent_id':'study-benchmark','status':'recorded','description':'Controlled development comparison on user-selected Desk1; retain negative alignment result and metric-prior/instance-accuracy distinction.',
        'attrs':{'role':'study','design':{'hypothesis':'Nominal product dimensions constrain physical plausibility but may conflict with single-image evidence',
            'factor':'external nominal dimension constraints in joint camera/cuboid fitting','levels':['existing ray solids','image cuboids with assumed sugar height','web soft dimensions','web fixed dimensions'],
            'held_constant':['original RGB and object identities','source annotations','B/C/D optimizer, four starts and training selection','local source-photo materials','renderer settings'],
            'co_varying':['A used all corners; B/C/D hold out3','B fixed sugar-height gauge vs C soft3-object dimensional scale vs D fixed3-object scale','B/C/D camera and layout are fitted outcomes'],
            'selection_rule':'lowest robust training cost across4starts; heldout never selects start'},'study_summary':summary},'evidence':[report,numeric,protocol]})
    baseline=copy.deepcopy(d['nodes']['artifact-desk1-model']);baseline['parent_id']=study;nodes.append(baseline)
    for index,r in enumerate(records[1:],1):
        code=r['arm'].split('_')[0];cell='cell-desk1-priors-'+code.lower();run='run-desk1-priors-'+code.lower()
        labels={'B':'图像与既有高度假设 / Image and retained height assumption','C':'联网软尺寸约束 / Soft web dimensions','D':'固定联网名义尺寸 / Fixed nominal web dimensions'}
        ref=ev(evidence+'comparison_diagnostics_blend_verified.json',f'$.records[{index}]')
        configuration={'arm':r['arm'],'source_sha256':'f125bdbe59e6e978d22e5143131291a1ef5206239928007a01d26aabb1bb9578','eval_protocol':'desk1-web-frozen-20260930'}
        nodes.append({'id':cell,'kind':'cell','label':labels[code],'parent_id':study,'status':'recorded','description':'One deterministic condition; four solver initializations are not independent training seeds.',
            'attrs':{'config':configuration},'evidence':[ref,protocol]})
        metrics={'same_image_holdout_corner_distance_px':r['same_image_heldout_corner_mean_distance_px'],'foreground_rgb_mae_0_255':r['foreground_rgb_mae_0_255'],
                 'box_orthogonality_max_deviation_deg':r['box_orthogonality_max_deviation_deg'],'nominal_prior_relative_absolute_deviation':r['prior_relative_absolute_deviation_mean']}
        nodes.append({'id':run,'kind':'run','label':labels[code],'parent_id':cell,'status':'completed','description':'Actual saved model/two renders; reopened blend verified. No GT or qualification.',
            'attrs':{'run_id':'desk1_web_phase_20260930/'+r['arm'],'seed':0,'code_revision':None,'source_code_binding':'original snapshot native_code; later review fixes not assigned to this historical model',
                'config':configuration,'eval_protocol':'desk1-web-frozen-20260930','metrics':metrics,'model_sha256':r['bindings']['model_sha256']},'evidence':[ref]})
        nodes.append({'id':'evaluation-desk1-priors-'+code.lower(),'kind':'evaluation','label':'实际网格与渲染诊断 / Actual mesh and render diagnostics','parent_id':run,'status':'recorded',
            'description':'Three correlated same-image heldout points; source projection MAE and nominal deviation are diagnostics, not true3D accuracy.',
            'attrs':{'protocol':'desk1-web-frozen-20260930','metrics':metrics},'evidence':[ref]})
        edges.append({'id':'edge-desk1-'+code.lower()+'-baseline','source':run,'target':'artifact-desk1-model','relation':'compares','evidence':[ref]})
    nodes.append({'id':'claim-desk1-soft-prior-alignment','kind':'claim','label':'规格一致性提高，同图角点误差变大 / Prior consistency improves while same-image corner error rises',
        'parent_id':study,'status':'recorded','description':'B/C heldout mean2.741/5.800px; nominal-prior deviation7.080/2.536percent. The latter is objective consistency, not true dimension accuracy.',
        'attrs':{'scope':'One development image;3heldout manual corners with3-8px uncertainty; no GT or statistical superiority.',
            'finding':{'type':'negative_result','priority':'secondary','comparison':{'baseline_cell_ids':['cell-desk1-priors-b'],'treatment_cell_ids':['cell-desk1-priors-c'],'factor':'web nominal dimension regularization'},
                'endpoint':{'metric':'same_image_holdout_corner_distance','unit':'px','dataset':'Desk1 single RGB','protocol':'desk1-web-frozen-20260930','readout':'three manual heldout corners'},
                'estimate':{'delta':records[2]['same_image_heldout_corner_mean_distance_px']-records[1]['same_image_heldout_corner_mean_distance_px'],'sample_unit':'scene','n':1},
                'basis':'independent_recalculation','limitations':['manual point uncertainty','only one scene','nominal dimensions not instance truth','different metric-scale constraints']}},'evidence':[numeric,report]})
    nodes.append({'id':'study-desk1-learning-shape','kind':'module','label':'Hunyuan四对象形状基线真实运行 / Hunyuan four-object shape baseline executed',
        'parent_id':study,'status':'recorded','description':'Shape assets only; no complete scene or ranking against scene image metrics.',
        'attrs':{'role':'evidence_audit','study_summary':{lang:{'intro':intro,'columns':['Endpoint','Result'],'rows':[['Object attempts','4/4 once each'],['Independent watertight readback','4/4'],['GPU process','78.145 s']],
            'note':note} for lang,intro,note in [('en','Pinned local inference, no paid service.','Canonical assets; scale/pose/camera/material/layout and SOTA unverified.'),('zh','冻结模型的实际推理，未调用付费服务。','只有对象形状，真实尺度、姿态、相机、材质、布局和SOTA均未验证。')]}},'evidence':[hreport,ev(evidence+'independent_mesh_audit.json')]})
    nodes.append({'id':'run-desk1-hunyuan-shape','kind':'run','label':'Hunyuan3D-2 seed2026 / Four shape assets','parent_id':'study-desk1-learning-shape','status':'completed',
        'description':'All four raw outputs retained. One fixed seed/30steps/octree256; no retries, mesh repair, texture or GT alignment.',
        'attrs':{'run_id':'desk1_web_phase_20260930/hunyuan2','seed':2026,'code_revision':'f8db63096c8282cb27354314d896feba5ba6ff8a',
            'eval_protocol':'desk1-shape-only-20260930','metrics':{'generated_objects':4,'expected_objects':4,'watertight_objects':4,'gpu_process_wall_seconds':json.loads((root/evidence/'receipt.json').read_text())['gpu_process_wall_seconds']}} ,
        'evidence':[hreport,ev(evidence+'inference_receipt.json'),ev(evidence+'independent_mesh_audit.json')]})
    nodes.append({'id':'artifact-desk1-web-chain','kind':'artifact','label':'原生联网证据门与实际相机消费 / Native web gate and actual camera consumption',
        'parent_id':study,'status':'recorded','description':'35contract tests and actual Desk1 partial native acceptance. Remaining native room/model/material/review/export stages unperformed.',
        'attrs':{'role':'native_integration','scope':'Evidence integrity and declared consumer decisions; not independent product/instance truth or full native reconstruction acceptance'},
        'evidence':[report,ev(evidence+'after_review/partial_gate_receipt.json'),ev(evidence+'after_review/camera_consumption_receipt.json')]})
    target=a.workspace/'.research/desk1_spec_patch.json'
    target.write_text(json.dumps({'base_revision':d['revision'],'reason':'Link actual Desk1 source-backed prior ablations and independent learned shape baseline; preserve old model identity, failures, budgets and no-SOTA boundary.','nodes':nodes,'edges':edges},ensure_ascii=False,indent=2),encoding='utf-8')
    outline=a.workspace/'.research/desk1_study_outline.md'
    outline.write_text('# Desk1 scientific outline\n\nObjective: independently evidenced Real2Sim superiority; currently unestablished.\n'
        'Source: frozen Desk1 real RGB and matching manual observations, one scene.\n'
        'Methods: retained ray solids; joint camera/orthogonal cuboids with source-height gauge; soft/fixed nominal web specifications; separately scoped raw Hunyuan shapes.\n'
        'Hypothesis: nominal specifications constrain dimensions but can conflict with the photographed instance.\n'
        'Endpoints: same-image holdout3corner distances; source-projected foreground MAE; orthogonality; nominal-prior deviation. None measures independent3D truth.\n'
        'Learning endpoint: four once-only raw shapes, independent topology readback; no full-scene scale/camera/pose/material comparison.\n'
        'Negative evidence: web prior improves nominal consistency while corner error rises; oldraymodel retains lower MAE but is nonorthogonal.\n'
        'Missing: exact instance specification/GT/calibration/secondrealview and complete SAM3D/SimFoundry replay. No automatic task restart.\n'
        'Evidence: docs/research/DESK1_WEB_COMPARISON_20260930.md and source-bound JSONs linked in the patch.\n',encoding='utf-8')
    print(json.dumps({'patch':str(target),'base_revision':d['revision'],'nodes':len(nodes),'edges':len(edges)}))

if __name__=='__main__':main()
