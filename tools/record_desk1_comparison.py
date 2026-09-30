"""Record completed Desk1 phase without erasing earlier attempts or resetting costs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    research=ROOT/'docs/research';evidence=research/'evidence/desk1_web_phase_20260930'
    result=read(evidence/'comparison_diagnostics_blend_verified.json');native=read(evidence/'native_phase_receipt.json');hunyuan=read(evidence/'receipt.json')
    summary={'schema':'real2sim.desk1-phase-summary/1','date':'2026-09-30','status':'development_comparison_completed_sota_unestablished',
        'source_sha256':result['source_sha256'],'phase_sha256':sha(research/'DESK1_WEB_PHASE_20260930.json'),
        'report':'DESK1_WEB_COMPARISON_20260930.md','sota_established':False,'independent_source_images':1,'expected_objects':4,
        'native_new_scene_candidates':3,'native_new_renders':6,'native_joint_camera_fit_cells':3,'native_solver_starts_total':12,'hunyuan_shape_outputs':4,'hunyuan_expected_outputs':4,
        'native_comparison_wall_seconds':native['wall_seconds'],'hunyuan_gpu_process_wall_seconds':hunyuan['gpu_process_wall_seconds'],
        'new_paid_api_requests':0,'new_remote_download_conservative_bytes':6342946060,
        'tests':[{'suite':'test_web_research.py','passed':23},{'suite':'test_web_research_native.py','passed':11},{'suite':'test_desk1_source_only.py','passed':1}],
        'native_gate_scope':'Actual Desk1 web evidence and camera-fit consumption; remaining full native scene workflow stages unperformed',
        'hunyuan_scope':'Raw shape assets only; no metric scale, pose, camera, texture or complete-scene performance',
        'model_snapshot_scope':'Existing fits/models retain original hashes and native_code snapshot. Review fixes validated separately in native_code_after_review; no model retry or historical source reassignment.',
        'evidence_hashes':{str(p.relative_to(research)):sha(p) for p in evidence.rglob('*.json')},
        'current_validation_code_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'workflow/r2s/core.py',ROOT/'workflow/r2s/profiles.py',ROOT/'workflow/r2s/web_research.py',ROOT/'workflow/r2s/web_integration.py',ROOT/'tools/test_web_research.py',ROOT/'tools/test_web_research_native.py',ROOT/'tools/test_desk1_source_only.py']},
        'automation':'deleted_by_user_request; not restarted','owned_inference_processes':'finished; GPU4 released; completion audit retained',
        'retained_validation_setup_errors':['SCP connection reset before revised camera acceptance helper transfer','Old helper rejected original-web-report CLI flag; corrected after successful transfer'],
        'full_scene_third_party_reruns':{'SAM3D':'not_run','SimFoundry':'not_run','Hunyuan3D2':'shape_assets_only'}}
    write(research/'DESK1_PHASE_SUMMARY_20260930.json',summary)
    state_path=research/'STATE.json';state=read(state_path)
    if 'desk1_web_phase_20260930' in state:
        if state['desk1_web_phase_20260930']['phase_sha256']!=summary['phase_sha256']:raise ValueError('Existing phase identity changed')
        state['desk1_web_phase_20260930']=summary
        state['resource_accounting'].update(desk1_web_joint_camera_fit_cells=3,desk1_web_solver_starts_total=12)
        write(state_path,state)
        print(json.dumps({'status':'already_recorded_metadata_refreshed','cost_not_added_twice':True}));return
    state['latest_update']=summary['report'];state['desk1_web_phase_20260930']=summary
    state['previous_pending_user_request']=state.get('pending_user_request')
    state['pending_user_request']={'task':'User-selected Desk1 comparison and source-backed dimensions/details chain toward evidenced SOTA',
        'status':summary['status'],'phase_protocol':'DESK1_WEB_PHASE_20260930.json','report':summary['report'],'mode':'manual user turn',
        'remaining_evidence':'Independent Desk1 metric geometry/camera/real heldout view and complete third-party scene reruns are unavailable in this phase'}
    state['completed']+=['Source-backed web dimensions/details executable gate integrated into native quality_v2; 35 tests and actual Desk1 evidence/camera acceptance passed',
        'Three actual Desk1 cuboid variants saved/rendered and reopened; web prior consistency improved but same-image heldout error worsened',
        'Pinned Hunyuan3D-2 actual four-object shape inference completed once each; independent raw mesh readback4/4watertight; full-scene/metric/SOTA unverified']
    state['next']=['Obtain independent matching Desk1 dimension/camera/pose or real second-view evidence before claiming metric superiority or SOTA.',
        'Use source-supported SKU uncertainty to weight web priors; retain source-only method and observed alignment regressions.',
        'Complete third-party scene replays only under explicit access/service/resource protocol; published renderings and Hunyuan shape assets are not full scene reruns.',
        'Keep previous BOP work and automatic task stopped; preserve all earlier results and budgets.']
    accounting=state['resource_accounting'];before=accounting['new_gpu_hours'];accounting['gpu_hours_before_desk1_web_phase']=before
    accounting['new_gpu_hours']=before+hunyuan['gpu_process_wall_seconds']/3600
    accounting['appearance_unique_proposals_used']+=3
    accounting.update(desk1_web_native_candidates_used=3,desk1_web_render_cells=6,desk1_web_joint_camera_fit_cells=3,desk1_web_solver_starts_total=12,desk1_hunyuan_object_attempts_used=4,
        desk1_web_native_wall_seconds=native['wall_seconds'],desk1_hunyuan_gpu_wall_seconds=hunyuan['gpu_process_wall_seconds'],
        desk1_hunyuan_download_conservative_bytes=6342946060,desk1_web_accounting_scope='New phase added without resetting oldcamera8/8, oldappearance10 or GPU costs; selected process walls are not total CPU/agent cost')
    state['retained_attempts']+=['desk1_web_phase_20260930/native_case and native_case_after_review (actual source evidence/camera gates, separate code snapshots)',
        'desk1_web_phase_20260930/B,C,D fitting (all4starts each; training-based selection; heldout regressions retained)',
        'desk1_web_phase_20260930/native_phase_receipt.json (all3 pre-model/render import failures plus3 entrypoint repairs retained)',
        'desk1_web_phase_20260930/hunyuan2/setup_revision_001 and setup_revision_002 (same original setup deadline and preserved wheels)',
        'desk1_web_phase_20260930/hunyuan2/objects (all4once-onlyrawshapeoutputs; no retry/best seed/GTalignment)']
    state['delivery_focus']['latest_comparison_report']=summary['report'];state['delivery_focus']['sota_established']=False
    write(state_path,state);print(json.dumps({'status':'recorded','cumulative_gpu_hours':accounting['new_gpu_hours'],'appearance_unique_proposals_used':accounting['appearance_unique_proposals_used']}))

if __name__=='__main__':main()
