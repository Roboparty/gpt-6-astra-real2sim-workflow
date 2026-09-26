"""Evidence-bound visual revisions. The Agent judges images; the runner enforces state."""
import json
from pathlib import Path
from .contracts import ContractError
from .media import file_hash
from .structure import evidence_file
from . import appearance

REVIEW_STAGES = {'agent_review_geometry', 'agent_review'}
DIMENSIONS = ('source_similarity', 'local_detail', 'novel_structure')
DEFAULTS = {'max_revisions': 8, 'max_stagnant': 3, 'max_seconds': 7200}


def write_render_binding(packet, out):
    """Called by the executable renderer, after rendering the saved scene."""
    from PIL import Image
    from .contracts import digest
    out = Path(out)
    scene = json.loads((out / 'scene.json').read_text())
    render = Image.open(out / 'source_view.png')
    source_record = packet.get('appearance_source')
    if packet.get('mode') == 'video' and not source_record:
        raise ContractError('Video review requires an explicitly selected accepted frame')
    source_path = Path(source_record['path'] if source_record else packet['original_input_allowlist'][0])
    if source_record and file_hash(source_path) != source_record['sha256']:
        raise ContractError('Selected appearance source changed')
    source = Image.open(source_path)
    original_size = source.size
    source = source.convert('RGB').resize(render.size)
    source.save(out / 'source_reference.png')
    crops = {}
    for i, target in enumerate(packet.get('appearance_targets', [])):
        box = target['source_crop_xyxy']
        if not (0 <= box[0] < box[2] <= original_size[0] and 0 <= box[1] < box[3] <= original_size[1]):
            raise ContractError('Priority crop is outside the source image')
        box = tuple(round(v * render.size[j % 2] / original_size[j % 2]) for j, v in enumerate(box))
        crops[target['entity']] = {}
        for role, image in [('source', source), ('render', render)]:
            name = f'priority_{i:03d}_{role}.png'
            image.crop(box).save(out / name)
            crops[target['entity']][role] = name
    settings = json.loads((out / 'render_manifest.json').read_text()).get('comparison_settings', {})
    if not settings:
        raise ContractError('Renderer must record actual comparison settings')
    binding = {'model_sha256': file_hash(out / 'scene.blend'), 'scene_sha256': file_hash(out / 'scene.json'),
               'source_sha256': file_hash(source_path), 'model_version': scene.get('model_version'),
               'protocol_sha256': digest({'cameras': scene.get('cameras', [scene.get('camera')]), 'settings': settings}),
               'object_crops': crops, 'images': {str(p.relative_to(out)): file_hash(p) for p in out.rglob('*.png')}}
    if appearance.enabled(packet):
        protocol = json.loads((out/'comparison_protocol.json').read_text())
        if packet.get('comparison_protocol') and protocol != packet['comparison_protocol']:
            raise ContractError('Renderer changed the persistent comparison cameras/settings')
        binding.update(comparison_protocol=protocol, protocol_sha256=digest(protocol),
                       comparison_images={name: binding['images'][name] for name in appearance.FIXED_VIEWS})
    (out / 'render_binding.json').write_text(json.dumps(binding, indent=2))
    return binding


def limits(config):
    value = {**DEFAULTS, **config.get('refinement', {})}
    value.setdefault('surface_contract_version', 1)
    value.setdefault('appearance_contract_version', 1)
    if type(value['appearance_contract_version']) is not int or value['appearance_contract_version'] not in (0, 1):
        raise ContractError('Unknown appearance contract version')
    if type(value['surface_contract_version']) is not int or value['surface_contract_version'] not in (0, 1):
        raise ContractError('Unknown surface contract version')
    for key in DEFAULTS:
        if type(value[key]) is not int or value[key] <= 0:
            raise ContractError('Refinement limits must be positive integers: ' + key)
    return value


def artifacts_valid(items):
    return bool(items) and all(Path(a['path']).is_file() and file_hash(a['path']) == a['sha256'] for a in items)


def check_response(workflow, name, attempt, response):
    if response['status'] == 'needs_input':
        return None
    from .surfaces import check_response as check_surfaces
    check_surfaces(workflow,name,attempt,response)
    packet = json.loads((Path(attempt)/'packet.json').read_text()) if (Path(attempt)/'packet.json').exists() else {}
    appearance.check_stage(name, attempt, response, packet)
    if name == 'agent_observe':
        files = response.get('artifacts', [])
        obs = json.loads(evidence_file(attempt, 'observation.json', files).read_text())
        packet = json.loads((attempt / 'packet.json').read_text())
        source = obs.get('appearance_source', packet.get('appearance_source'))
        if not source or not any(source.get('path') == a['path'] and source.get('sha256') == a['sha256'] for a in packet.get('comparison_inputs', [])):
            raise ContractError('Appearance source must be an authorized image or accepted decoded frame')
        targets = obs.get('appearance_targets', [])
        if not targets or len({t.get('entity') for t in targets}) != len(targets):
            raise ContractError('Declare unique appearance targets before modelling')
        furniture = json.loads(evidence_file(attempt, 'furniture_observation.json', files).read_text())
        if not {t['entity'] for t in furniture.get('targets', [])} <= {t['entity'] for t in targets}:
            raise ContractError('Appearance targets must include observed furniture')
        for t in targets:
            box = t.get('source_crop_xyxy', [])
            if not t.get('features') or len(box) != 4 or not all(type(v) is int for v in box) or not (0 <= box[0] < box[2] and 0 <= box[1] < box[3]):
                raise ContractError('Appearance target needs observed features and a valid pixel crop')
    if response['status'] == 'changes_requested':
        target = response.get('revision', {}).get('stage')
        ancestors = set()
        def visit(n):
            for dep in workflow.stage_map[n][0]:
                if dep not in ancestors:
                    ancestors.add(dep)
                    visit(dep)
        visit(name)
        allowed = {'agent_observe', 'agent_calibrate', 'agent_calibrate_room', 'agent_model', 'agent_materials', 'agent_calibrate_lighting'}
        if name not in REVIEW_STAGES or target not in ancestors or target not in allowed:
            raise ContractError('Revision must target a responsible upstream Agent stage')
        if any(i.get('responsible_stage') != target for i in response.get('issues', [])):
            raise ContractError('Route one responsible stage per revision; keep other findings in review')
        previous = workflow.state.get('revision_requests', {}).get(target, {})
        if workflow.state.get('refinement', {}).get(name, {}).get('stagnant', 0) >= 2 and response['revision'].get('strategy') == previous.get('strategy'):
            raise ContractError('Stagnant revisions require a different modelling strategy')
    if name in REVIEW_STAGES:
        packet = json.loads((attempt / 'packet.json').read_text())
        best = workflow.state.get('refinement', {}).get(name, {}).get('best')
        return review(attempt, response, packet, best)


def review(attempt, response, packet, best):
    """Validate both rejected and accepted candidates before recording either."""
    files = response.get('artifacts', [])
    if any(Path(ref).suffix=='.blend' or (Path(ref).name.startswith('scene') and Path(ref).suffix=='.json') for ref in files):
        raise ContractError('Review cannot supply an unrendered replacement model; revise the responsible stage')
    data = json.loads(evidence_file(attempt, 'appearance_review.json', files).read_text())
    upstream = packet['input_artifacts']
    build = 'build_geometry' if packet['stage'] == 'agent_review_geometry' else 'build_render'
    bindings = [a for a in upstream[build] if Path(a['path']).name == 'render_binding.json']
    if len(bindings) != 1 or not artifacts_valid(bindings):
        raise ContractError('Review requires the current executable render binding')
    binding = json.loads(Path(bindings[0]['path']).read_text())
    if data.get('render_binding_sha256') != bindings[0]['sha256']:
        raise ContractError('Appearance review uses a stale render/model')
    # Reviewed image copies must be byte-identical to actual rendered/source evidence.
    allowed = set(binding['images'].values())
    for key in DIMENSIONS:
        check = data.get('checks', {}).get(key, {})
        if check.get('status') not in {'pass', 'revise'} or not check.get('findings') or not check.get('evidence'):
            raise ContractError('Missing visual dimension: ' + key)
        for ref in check['evidence']:
            if file_hash(evidence_file(attempt, ref, files)) not in allowed:
                raise ContractError('Visual evidence does not belong to this render: ' + ref)
    seen = lambda key: {file_hash(evidence_file(attempt, ref, files)) for ref in data['checks'][key]['evidence']}
    if not {binding['images']['source_reference.png'], binding['images']['source_view.png']} <= seen('source_similarity'):
        raise ContractError('Source similarity must inspect both source and current source-view render')
    novel = {sha for name, sha in binding['images'].items() if Path(name).name.startswith(('diagnostic_', 'inspect_', 'isolated_'))}
    if not novel & seen('novel_structure'):
        raise ContractError('Novel structure needs an actual diagnostic view, not only the fitted source view')
    targets = {t['entity'] for t in packet['appearance_targets']}
    rows = data.get('per_object', [])
    if len(rows) != len(targets) or {r.get('entity') for r in rows} != targets:
        raise ContractError('Appearance review must cover every priority object exactly once')
    for row in rows:
        if row.get('status') not in {'pass', 'revise'} or not row.get('findings'):
            raise ContractError('Object review lacks a decision and findings')
        for role in ('source', 'render'):
            expected = binding.get('object_crops', {}).get(row['entity'], {}).get(role)
            ref = row.get(role + '_crop')
            if not expected or file_hash(evidence_file(attempt, ref, files)) != binding['images'].get(expected):
                raise ContractError('Object crop is missing or stale: ' + row['entity'])
    relation = data.get('comparison', {})
    appearance.check_review(attempt, response, packet, data, binding, best)
    if best:
        if not artifacts_valid(best['artifacts']):
            raise ContractError('Best candidate evidence changed; restore it before comparing')
        if any(not artifacts_valid(stage['outputs']) for stage in best['source_stages'].values()):
            raise ContractError('Best candidate model/render artifacts changed')
        if relation.get('against') != best['review_sha256'] or relation.get('relation') not in {'better', 'equivalent', 'worse'}:
            raise ContractError('Compare against the recorded best candidate')
        if relation.get('protocol_sha256') != binding['protocol_sha256'] or best['protocol_sha256'] != binding['protocol_sha256']:
            raise ContractError('Comparison conditions changed; render a matched baseline before continuing')
        prior_images = set(best['image_hashes'])
        for role, hashes in [('before', prior_images), ('after', allowed)]:
            refs = relation.get(role, [])
            if not refs or any(file_hash(evidence_file(attempt, ref, files)) not in hashes for ref in refs):
                raise ContractError('Comparison requires real before/after images')
            rendered = {a['sha256'] for a in best['artifacts'] if is_render_image(Path(a['path']).name)} if role=='before' else {sha for name,sha in binding['images'].items() if is_render_image(Path(name).name)}
            if not rendered & {file_hash(evidence_file(attempt, ref, files)) for ref in refs}:
                raise ContractError('Comparison must include a rendered image on both sides, not only originals')
    elif relation.get('relation') != 'baseline':
        raise ContractError('First candidate must be explicitly recorded as baseline')
    if not relation.get('findings'):
        raise ContractError('Comparison needs an auditable visual judgement')
    issues = response.get('issues', []) + data.get('issues', [])
    if response['status'] == 'complete':
        if any(c['status'] != 'pass' for c in data['checks'].values()) or any(r['status'] != 'pass' for r in rows):
            raise ContractError('Unresolved appearance defects cannot pass')
        if relation['relation'] == 'worse' or any(i.get('blocking') or i.get('severity') in {'major','critical'} for i in issues):
            raise ContractError('A regressed/blocking candidate cannot pass')
    else:
        request = response.get('revision', {})
        if not request.get('reason') or not request.get('strategy') or not issues:
            raise ContractError('Revision requires defects, reason and a concrete modelling strategy')
        for issue in issues:
            if not all(issue.get(k) for k in ('entity', 'defect', 'evidence', 'responsible_stage')):
                raise ContractError('Each defect needs an owner, evidence and responsible stage')
            for ref in issue['evidence']:
                evidence_file(attempt, ref, files)
    return data, binding


def is_render_image(name):
    return name.startswith(('source_view','source_clay','diagnostic_','inspect_','isolated_')) or (name.startswith('priority_') and name.endswith('_render.png'))
