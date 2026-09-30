"""Append this completed manual comparison without resetting old resource ledgers."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    research=ROOT/'docs/research';evidence=research/'evidence/gpt6_peers_20260930';p=read(evidence/'pi3x/receipt.json');m=read(evidence/'moge/upgrade_receipt.json');scenes=[read(f) for f in (evidence/'scenes').glob('*.json')];gpu=p['gpu_process_wall_seconds']+m['cumulative_gpu_seconds']
    summary={'schema':'real2sim.gpt6-peer-summary/1','date':'2026-09-30','status':'manual_adaptation_comparison_completed_original_framework_ranking_unverified',
        'report':'DESK1_GPT6_PROJECT_COMPARISON_20260930.md','catalog':'GPT6_PROJECT_CATALOG_20260930.json','source_sha256':'f125bdbe59e6e978d22e5143131291a1ef5206239928007a01d26aabb1bb9578',
        'public_projects_checked':4,'static_routes_adapted':2,'full_original_peer_frameworks_run':0,'independent_gpt6_astra_sessions':0,
        'inference_attempts':{'pi3x':1,'moge3':2,'moge3_failed':1,'moge3_completed':1},'scene_candidates':4,'render_cells':8,
        'gpu_process_seconds_conservative':gpu,'new_gpu_hours_conservative':gpu/3600,'new_paid_external_api_requests':0,'network_conservative_bytes':m['network_conservative_bytes_total'],
        'measured_scene_process_wall_sum_seconds':sum(s['wall_seconds'] for s in scenes),'scene_walls_note':'Some paired renders overlapped; sum is process time, not elapsed total. Coordination/agent/otherCPU cost unknown.',
        'automation':'stopped; no schedule restart','sota_established':False,'true_3d_accuracy':None,'metric_scope':'same-mask source RGB/convex prebevel footprint diagnostics; different supervision/optimization and no real heldout view',
        'failures_retained':['CPU-only Triton driver import diagnostic','HF canonical transport reset; official CDN metadata-only repair','first actual MoGe forward on Triton3.2 compilation failure','property-shim hash lookup diagnostic failure before another model call','Pi3X confidence-key CPU adapter error; raw tensors salvaged without rerun','two pre-render background-threshold detections failed, empty output dirs retained'],
        'source_snapshot_scope':'Actual scripts used for initial runs preserved under evidence/code; current Pi3X confidence-key and builder metadata corrected afterward, not reassigned as historical code.',
        'evidence_hashes':{str(f.relative_to(research)):sha(f) for f in evidence.rglob('*.json')}}
    write(research/'GPT6_PEER_RESULT_SUMMARY_20260930.json',summary)
    path=research/'STATE.json';state=read(path)
    if 'gpt6_peer_manual_20260930' in state:
        state['gpt6_peer_manual_20260930']=summary;write(path,state);print(json.dumps({'status':'metadata_refreshed','cost_added_twice':False}));return
    state.setdefault('manual_task_history',[]).append(state.get('pending_user_request'))
    state['pending_user_request']={'task':'Search other GPT6 Real2Sim projects and compare Desk1 reconstruction effects','status':summary['status'],'report':summary['report'],'scope':'Two static reference-route adaptations; full original/Astra framework comparison remains unverified'}
    state['latest_update']=summary['report'];state['gpt6_peer_manual_20260930']=summary
    state['completed']+=['Four current GPT6 project sources/commits checked; correct public Real2Gym repository discovered',
        'Actual single-image Pi3X and MoGe3 reference routes adapted to Desk1; all4objects retained and4actualscenes/8CPUrenders preserved with paired RGB-background revisions',
        'Saved Blender models reopened and same-mask image/footprint diagnostics recomputed; no full-framework or SOTA ranking claimed']
    resource=state['resource_accounting'];resource['new_gpu_hours']+=gpu/3600;resource['appearance_unique_proposals_used']+=4;resource.update(gpt6_peer_new_gpu_seconds=gpu,gpt6_peer_scene_candidates=4,gpt6_peer_render_cells=8,gpt6_peer_moge_attempts=2,gpt6_peer_pi3x_attempts=1,gpt6_peer_remote_download_conservative_bytes=m['network_conservative_bytes_total'])
    state.setdefault('resolved_blockers',[]).append('Real2Gym discovery path corrected from unavailable cskrren link to public real2gym/Real2Gym512548cd; resolves source access, not full Desk1 original-framework reproduction')
    state['retained_attempts']+=['gpt6_peers_20260930/moge3 (CPUdriver/bootstrap/transport plus one actual failedforward)',
        'gpt6_peers_20260930/moge3_retry (failed GPU hash lookup diagnostic,0additionalmodelcalls)',
        'gpt6_peers_20260930/moge3_triton34 (original source/weights, actual hashroundtrip+one completed forward; no old cost reset)',
        'gpt6_peers_20260930/pi3x_single (one actual forward; conf-key CPU adapter correction, no inference rerun)',
        'gpt6_peers_20260930/{aha_pi3x,real2gym_moge3}_adapted_scene and rgb_repaired (all original and revised models, frozenforeground/camera,8renders)']
    state['next']=['Use independent matching geometry/cameras or a real secondview for true3D validation; source-image appearance alone cannot prove SOTA.',
        'For full GPT6 framework ranking, match exactmodel, supervision and agent/compute budgets in independent original-framework runs; do not relabel these component adaptations.',
        'Keep automatic task stopped and priorBOP/TUM/Desk1 failures, budgets, source hashes and remote artifacts preserved.']
    write(path,state);print(json.dumps({'status':'recorded','new_gpu_seconds':gpu,'cumulative_gpu_hours':resource['new_gpu_hours'],'appearance_proposals_cumulative':resource['appearance_unique_proposals_used']}))

if __name__=='__main__':main()
