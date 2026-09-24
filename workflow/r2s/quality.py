"""Evidence gates; engineering success never implies visual acceptance."""
import json
from pathlib import Path
from .contracts import ContractError

def _read(attempt,name,artifacts):
    if name not in artifacts:raise ContractError('Required calibration/review artifact missing: '+name)
    return json.loads((Path(attempt)/name).read_text())

def _review(data,dimensions):
    if data.get('decision')!='pass':raise ContractError('Visual quality decision is not pass')
    if any(i.get('severity') in {'major','critical'} or i.get('blocking') for i in data.get('issues',[])):
        raise ContractError('Major visual mismatch cannot be relabelled as a nonblocking limitation')
    for key in dimensions:
        d=data.get('checks',{}).get(key,{})
        if d.get('status')!='pass' or not d.get('evidence'):raise ContractError('Missing independent quality check: '+key)

def check_quality_stage(stage,attempt,response,profile):
    if profile!='quality_v2':return
    files=response.get('artifacts',[])
    if stage=='agent_observe':
        d=_read(attempt,'furniture_observation.json',files)
        if not d.get('source_sha256') or not d.get('acceptance_before_fit'):raise ContractError('Part observation requires source binding and predeclared acceptance')
        if not d.get('targets') and not d.get('no_applicable_furniture_reason'):raise ContractError('Furniture observation scope must be explicit')
        for t in d.get('targets',[]):
            if not all(t.get(k) for k in ['entity','parts','constraints','observations','uncertain']):raise ContractError('Furniture lacks part ownership, constraints, observations or uncertainty')
            if any(o.get('visibility') not in ['observed','partial','unobserved'] for o in t['observations']):raise ContractError('Part observation visibility must be explicit')
    elif stage=='agent_model':
        from .structure import structure_contract,file_sha
        d=_read(attempt,'scene.json',files);required=structure_contract(d.get('structure'))
        obs=_read(attempt,'furniture_observation.json',files)
        if required!={o['entity'] for o in obs['targets']}:raise ContractError('Model omits an observed assembly')
        if d['structure']['observation_sha256']!=file_sha(Path(attempt)/'furniture_observation.json'):raise ContractError('Model not bound to actual part observations')
        packet=json.loads((Path(attempt)/'packet.json').read_text());up=[a for a in packet['input_artifacts']['agent_observe'] if Path(a['path']).name=='furniture_observation.json']
        if len(up)!=1 or up[0]['sha256']!=d['structure']['observation_sha256']:raise ContractError('Builder used observations different from accepted observation stage')
        if response.get('parameters',{}).get('model_version')!=d['model_version']:raise ContractError('Model response version differs from actual model')
    elif stage=='agent_calibrate_room':
        d=_read(attempt,'room_calibration.json',files);surfaces={s['id']:s for s in d.get('surfaces',[])}
        required={'wall_front','wall_back','wall_left','wall_right','floor','ceiling'}
        if set(surfaces)!=required:raise ContractError('Room calibration must account for every wall, floor and ceiling')
        for s in surfaces.values():
            if not s.get('plane') or not s.get('evidence'):raise ContractError('Surface lacks geometric parameters/evidence')
            if s.get('visibility')=='unobserved':
                if s.get('status')!='hypothesized' or not s.get('uncertainty'):raise ContractError('Invisible wall cannot be claimed calibrated')
            elif s.get('visibility') in {'observed','partial'}:
                if s.get('status')!='fitted' or not s.get('image_constraints') or not s.get('residuals'):raise ContractError('Visible wall needs source constraints and residuals')
            else:raise ContractError('Unknown surface visibility')
        if not d.get('openings_and_columns_reviewed'):raise ContractError('Window, doorway, pillar and wall-return review required')
    elif stage=='agent_review_geometry':
        d=_read(attempt,'geometry_review.json',files);_review(d,['camera','room_surfaces','silhouettes','occlusion','support'])
        if not d.get('per_object') or any(x.get('critical_mismatch') for x in d['per_object']):raise ContractError('Per-object silhouette review is incomplete')
        if not d.get('geometry_freeze_sha256'):raise ContractError('Freeze geometry before material/light calibration')
        from .structure import review_contract
        packet=json.loads((Path(attempt)/'packet.json').read_text());art=packet['input_artifacts']['build_geometry'];src={Path(a['path']).name:Path(a['path']) for a in art}
        review_contract(attempt,d,files,json.loads(src['scene.json'].read_text()),json.loads(src['model_binding.json'].read_text()))
    elif stage=='agent_materials':
        if not {'scene.json','model.blend'}<=set(files):raise ContractError('Material stage must deliver the editable scene, not only recommendations')
        d=_read(attempt,'material_calibration.json',files)
        if not d.get('materials') or not d.get('neutral_light_previews'):raise ContractError('Materials need per-material records and neutral-light previews')
        for m in d['materials']:
            if not all(k in m for k in ['entity','pbr_parameters','texture_scale_m','evidence','uncertainty']):raise ContractError('Incomplete physically scaled material record')
    elif stage=='agent_calibrate_lighting':
        if not {'scene.json','model.blend'}<=set(files):raise ContractError('Light calibration must deliver the calibrated scene')
        d=_read(attempt,'lighting_calibration.json',files)
        if not d.get('camera_locked') or not d.get('geometry_locked'):raise ContractError('Light fitting must not compensate by moving geometry/camera')
        if not all(d.get(k) for k in ['lights','comparison_before','comparison_after','metrics_before','metrics_after','uncertainty']):raise ContractError('Lighting needs before/after evidence and residuals')
        if not d.get('exposure_albedo_gauge_fixed'):raise ContractError('Exposure/albedo ambiguity must be controlled')
    elif stage=='agent_review':
        d=_read(attempt,'review.json',files);_review(d,['geometry','materials','lighting','source_alignment','novel_view_completeness'])
        if not d.get('source_comparison') or not d.get('same_camera_comparison'):raise ContractError('Original and render must be compared in the same camera')
        from .structure import evidence_file
        furniture=d.get('furniture_local_review',{})
        if furniture.get('status')!='pass' or not furniture.get('source_crop') or not furniture.get('render_crop') or not furniture.get('findings'):raise ContractError('Final appearance review must recheck furniture locally')
        for key in ['source_crop','render_crop']:evidence_file(attempt,furniture[key],files)
    elif stage=='agent_physics':
        d=_read(attempt,'physics_setup.json',files)
        if not d.get('reference_pose_preserved') or not d.get('parameters_are_measured_or_prior_labelled'):raise ContractError('Physics must preserve reference pose and label parameter provenance')
        if not d.get('target_decisions'):raise ContractError('Explicit physics targets or justified not-applicable decisions required')
    elif stage=='agent_review_physics':
        d=_read(attempt,'physics_review.json',files)
        if d.get('no_generated_physics'):
            if not d.get('not_applicable_reasons'):raise ContractError('No physics needs explicit not-applicable evidence')
            _review(d,['reference_pose'])
        else:_review(d,['reference_pose','limits_or_strain','contact','solver_stability','actual_simulation'])
