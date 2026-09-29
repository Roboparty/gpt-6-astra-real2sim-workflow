"""Opt-in integration of the three project skills into the native quality_v2 DAG."""
import importlib.util
import json
from pathlib import Path
import sys
from .contracts import ContractError, digest, scene_check
from .media import file_hash

SKILLS = {'roomkit': 'blender-roomkit', 'reference': 'pi3x-scene-reference',
          'refine': 'real2sim-local-refine'}


def config(value):
    cfg = value.get('generation_skills')
    if cfg is None:
        return None
    if value.get('workflow_profile') != 'quality_v2':
        raise ContractError('Generation skills require quality_v2')
    if not isinstance(cfg, dict) or not cfg.get('skills_root'):
        raise ContractError('Explicit generation_skills.skills_root required')
    root = Path(cfg['skills_root'])
    if not root.is_absolute():
        raise ContractError('skills_root must be absolute')
    for name in SKILLS.values():
        if not (root/name/'SKILL.md').is_file():
            raise ContractError('Required skill not found: ' + name)
    if cfg.get('reference', {}).get('mode', 'disabled') not in ('disabled', 'blocked', 'consume'):
        raise ContractError('No automatic model inference/installation mode')
    timeout = cfg.get('build_timeout_seconds', 120)
    if type(timeout) is not int or timeout <= 0:
        raise ContractError('Positive integer build_timeout_seconds required')
    if type(cfg.get('reference', {}).get('required', False)) is not bool:
        raise ContractError('reference.required must be boolean')
    return cfg


def load(cfg, key, script):
    path = Path(cfg['skills_root'])/SKILLS[key]/'scripts'/script
    spec = importlib.util.spec_from_file_location('generation_' + key, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stages(config_value, original):
    if not config(config_value):
        return original
    result = []
    for name, deps, agent in original:
        deps = list(deps)
        if name in ('agent_observe', 'agent_calibrate', 'agent_calibrate_room'):
            deps.append('scene_reference')
        if name == 'agent_review_geometry':
            deps.append('local_geometry_feedback')
        if name == 'agent_review':
            deps.append('local_appearance_feedback')
        result.append((name, deps, agent))
        if name == 'preprocess':
            result.append(('scene_reference', ['preprocess'], False))
        if name in ('build_geometry', 'build_render'):
            result.append(('local_geometry_feedback' if name == 'build_geometry' else 'local_appearance_feedback', [name, 'agent_calibrate_room'], False))
    return result


def bindings(config_value, stage):
    cfg = config(config_value)
    if not cfg:
        return None
    paths = []
    for name in SKILLS.values():
        paths += [p for p in (Path(cfg['skills_root'])/name).rglob('*') if p.suffix in ('.py', '.md')]
    bound_config = {'skills_root': cfg['skills_root']}
    if stage == 'scene_reference':
        bound_config['reference'] = cfg.get('reference', {})
        for key in ('manifest', 'npz', 'provenance'):
            if cfg.get('reference', {}).get(key):
                paths.append(Path(cfg['reference'][key]))
    if stage == 'agent_model':
        bound_config.update({k:cfg.get(k) for k in ('blender','build_timeout_seconds')})
    local = stage in ('local_geometry_feedback', 'local_appearance_feedback')
    if local:
        bound_config.update({k:cfg.get(k) for k in ('local_protocol','baseline_directory')})
    if local and cfg.get('local_protocol'):
        protocol = Path(cfg['local_protocol']); paths.append(protocol)
        if protocol.is_file():
            data = json.loads(protocol.read_text(encoding='utf-8'))
            paths += [protocol.parent/v['source']['path'] for v in data['views']]
    manifest = cfg.get('reference', {}).get('manifest')
    if stage == 'scene_reference' and manifest and Path(manifest).is_file():
        paths += [Path(f['path']) for f in json.loads(Path(manifest).read_text())['frames']]
    baseline = cfg.get('baseline_directory')
    if local and baseline:
        paths += [p for p in Path(baseline).rglob('*') if p.suffix in ('.png', '.json')]
    return {'config': bound_config, 'files': {str(p.resolve()): file_hash(p) if p.is_file() else 'missing' for p in paths}}


def packet(workflow, name, value):
    cfg = config(workflow.config)
    if not cfg:
        return value
    value['generation_skills'] = cfg
    value['formal_test'] = workflow.config.get('formal_test', True)
    value['skill_instructions'] = {k: str(Path(cfg['skills_root'])/v/'SKILL.md') for k,v in SKILLS.items()}
    value['generation_guidance'] = {
        'agent_model': 'Read RoomKit + Real2Sim skills. For the RoomKit backend deliver canonical scene.json, accepted furniture_observation.json, and roomkit_parts.json; do not also submit model.blend. The runner executes the builder, preserves the complete shell and then uses existing structure/render gates. Custom detailed models may still supply model.blend without a RoomKit manifest. Never replace source-backed detail with a generic primitive to claim fidelity.',
        'agent_calibrate': 'Read scene_reference status and Pi3X skill. Only validated existing outputs can inform calibration; approximate scale remains unvalidated. Missing references are not camera results.',
        'agent_calibrate_room': 'Read scene_reference status. Deliver local_protocol.json using real2sim-generation-roi/1: exact accepted fit source bytes, camera_index, canonical camera digest and part-mapped fixed regions. Freeze this protocol here before modeling. Preserve all six shell surfaces and openings.',
        'agent_review_geometry': 'Read local_geometry_feedback plus structural_audit; map source ROI defects to parts and route one responsible-stage revision. Local image MAE cannot override structure/landmark failures.',
        'agent_review': 'Read local_appearance_feedback, source and other views. Retain all worse/unknown regions. Route geometry, materials and lighting separately; do not mark render completion as acceptance.',
        'agent_materials': 'Change materials only on accepted geometry; use controlled neutral-light checks. Read Real2Sim local-refine skill.',
        'agent_calibrate_lighting': 'Change lighting only on locked geometry/materials/camera. Preserve exposure-albedo gauge; do not invoke material fitting in this stage.'
    }.get(name, 'Read the linked skills relevant to this stage; all original quality gates still apply.')
    value['accepted_source_records'] = [{'path':x['path'], 'sha256':file_hash(x['path'])} for x in workflow.config['inputs'] if workflow.config['mode'] != 'video']
    for artifact in workflow.state['stages'].get('preprocess', {}).get('outputs', []):
        if Path(artifact['path']).name == 'preprocess.json':
            value['accepted_source_records'] += json.loads(Path(artifact['path']).read_text())['accepted']
    if name in ('agent_review', 'agent_review_geometry'):
        value['regression_requirements'] = ['fixed_source_regions', 'other_views', 'evaluated_structure', 'collision_and_openings', 'modifier_export_preservation']
    return value


def prepare_model(workflow, attempt, response):
    """Execute the skill builder in the actual agent_model acceptance path."""
    cfg = config(workflow.config)
    files = response.get('artifacts', [])
    if not cfg or 'roomkit_parts.json' not in files or response.get('status') != 'complete':
        return response
    from .core import run_command
    from .structure import evidence_file
    if 'model.blend' in files or 'scene.blend' in files:
        raise ContractError('Choose authored Blender or RoomKit manifest, not both')
    parts = evidence_file(attempt, 'roomkit_parts.json', files)
    scene_path = evidence_file(attempt, 'scene.json', files)
    scene = json.loads(scene_path.read_text()); scene_check(scene)
    load(cfg, 'roomkit', 'roomkit.py').validate(json.loads(parts.read_text()))
    if not cfg.get('blender'):
        raise ContractError('RoomKit generation needs an existing Blender executable')
    import os
    env = os.environ.copy(); env['R2S_CPU'] = '1'; env['CUDA_VISIBLE_DEVICES'] = ''
    argv = [cfg['blender'], '-b', '-t', '2', '--python-exit-code', '12', '-P',
            str(Path(__file__).with_name('blender_roomkit_generation.py')), '--',
            str(parts), str(scene_path), str(attempt), cfg['skills_root']]
    timeout = cfg.get('build_timeout_seconds', 120)
    if workflow.refining:
        from .refinement import limits
        remaining = limits(workflow.config)['max_seconds'] - workflow.state.get('refinement', {}).get('elapsed_seconds', 0)
        if remaining <= 0:
            raise ContractError('Existing refinement time budget exhausted; no RoomKit launch')
        timeout = min(timeout, remaining)
    result = run_command(argv, attempt, env, timeout)
    (attempt/'roomkit_stdout.log').write_text(result.stdout)
    (attempt/'roomkit_stderr.log').write_text(result.stderr)
    if result.returncode:
        raise ContractError('RoomKit builder failed; retained logs in model attempt')
    generated = [str(p.relative_to(attempt)) for p in (attempt/'roomkit_build').rglob('*') if p.is_file() and p.suffix != '.blend']
    return dict(response, artifacts=files + generated + ['model.blend', 'roomkit_generation.json', 'roomkit_stdout.log', 'roomkit_stderr.log'])


def execute(value, out):
    from .core import atomic_json
    cfg = value['generation_skills']; stage = value['stage']; out = Path(out)
    if stage == 'scene_reference':
        ref = cfg.get('reference', {}); mode = ref.get('mode', 'disabled')
        report = {'mode': mode, 'environment': 'not_ready' if mode == 'blocked' else 'unverified',
                  'inference': 'not_run', 'geometry_accuracy': 'unverified',
                  'reason': ref.get('reason', 'No reference requested'), 'research_budget_consumed': False}
        if mode == 'consume':
            manifest_path = Path(ref['manifest']); manifest = json.loads(manifest_path.read_text())
            accepted = {r['sha256'] for r in value['accepted_source_records'] if file_hash(r['path']) == r['sha256']}
            if any(f['role'] != 'fit' or f['sha256'] not in accepted for f in manifest['frames']):
                raise ContractError('Generation reference includes heldout/unaccepted input')
            provenance = json.loads(Path(ref['provenance']).read_text())
            if value['formal_test'] and provenance.get('kind') != 'backend_output':
                raise ContractError('Synthetic reference cannot enter a formal generation case')
            report.update(load(cfg, 'reference', 'reference.py').consume(manifest_path, Path(ref['npz']), provenance, ref.get('threshold', .5)))
            report['mode'] = 'consume'; report['raw_outputs'] = ref['npz']
        atomic_json(out/'reference_status.json', report)
        status = 'needs_input' if ref.get('required', False) and mode != 'consume' else 'complete'
        return {'status':status, 'artifacts':['reference_status.json'], 'evidence':['Explicit reference status; no model launch'], 'reasoning_summary':'Reference generation readiness remains distinct from output consumption.'}
    if stage not in ('local_geometry_feedback', 'local_appearance_feedback'):
        raise ContractError('Unknown generation skill stage')
    protocol_path = Path(cfg['local_protocol']) if cfg.get('local_protocol') else None
    if protocol_path is None:
        matches = [Path(x['path']) for x in value['input_artifacts'].get('agent_calibrate_room', []) if Path(x['path']).name == 'local_protocol.json']
        if len(matches) == 1:
            protocol_path = matches[0]
    if protocol_path is None:
        atomic_json(out/'local_feedback.json', {'status':'needs_input', 'reason':'Freeze source ROI protocol before generation', 'acceptance':'not_determined'})
        return {'status':'needs_input','artifacts':['local_feedback.json'],'evidence':['Missing required frozen region protocol']}
    frozen = json.loads(protocol_path.read_text())
    if frozen.get('schema') != 'real2sim-generation-roi/1':
        raise ContractError('Unsupported generation ROI protocol')
    artifacts = [a for rows in value['input_artifacts'].values() for a in rows]
    scene_path = next(Path(a['path']) for a in artifacts if Path(a['path']).name == 'scene.json')
    build = scene_path.parent; scene = json.loads(scene_path.read_text())
    cameras = scene.get('cameras') or [scene['camera']]
    baseline = Path(cfg.get('baseline_directory', build))
    old_scene = json.loads((baseline/'scene.json').read_text())
    old_cameras = old_scene.get('cameras') or [old_scene['camera']]
    allowed = {r['sha256'] for r in value['accepted_source_records'] if file_hash(r['path']) == r['sha256']}
    generated = {'schema':'real2sim-roi/1', 'views':[]}
    for view in frozen['views']:
        if view['role'] != 'fit' or view['source']['sha256'] not in allowed:
            raise ContractError('Local generation feedback cannot use heldout or unaccepted source')
        index = view['camera_index']
        if type(index) is not int or not 0 <= index < min(len(cameras), len(old_cameras)):
            raise ContractError('Invalid frozen camera_index')
        known_parts = {p['id'] for assembly in scene.get('structure', {}).get('assemblies', []) for p in assembly['parts']} | {o['id'] for o in scene['objects']}
        if any(not set(region['part_ids']) <= known_parts for region in view['regions']):
            raise ContractError('Local region maps to an unknown canonical part')
        camera = digest(cameras[index]); old_camera = digest(old_cameras[index])
        if camera != view['camera_sha256'] or old_camera != camera:
            raise ContractError('Frozen local-feedback camera drift')
        render = 'source_view.png' if index == 0 else f'source_view_{index:04d}.png'
        generated['views'].append({'id':view['id'], 'role':'fit', 'regions':view['regions'],
            'source_camera_sha256':camera, 'baseline_camera_sha256':old_camera, 'candidate_camera_sha256':camera,
            'source':{'path':str((protocol_path.parent/view['source']['path']).resolve()),'sha256':view['source']['sha256']},
            'baseline':{'path':str(baseline/render),'sha256':file_hash(baseline/render)},
            'candidate':{'path':str(build/render),'sha256':file_hash(build/render)}})
    report = load(cfg, 'refine', 'refine.py').diagnose(generated, out)
    report.update(status='diagnostic_only', protocol_sha256=file_hash(protocol_path),
                  candidate_model_sha256=file_hash(build/'scene.blend'),
                  baseline_kind='same_first_candidate' if baseline == build else 'declared_previous_build',
                  regression_requirements=value.get('regression_requirements', ['structure','collision','other_views']))
    atomic_json(out/'roi_bound_protocol.json', generated); atomic_json(out/'local_feedback.json', report)
    return {'status':'complete','artifacts':['roi_bound_protocol.json','local_feedback.json'],
            'evidence':['Executed real2sim-local-refine on native rendered images'],
            'reasoning_summary':'Diagnostic delivered to the existing Agent quality gate; no automatic acceptance.'}


if __name__ == '__main__':
    from .core import atomic_json
    p = Path(sys.argv[1]); value = json.loads(p.read_text()); out = Path(value['output_directory'])
    atomic_json(out/'response.json', execute(value, out))
