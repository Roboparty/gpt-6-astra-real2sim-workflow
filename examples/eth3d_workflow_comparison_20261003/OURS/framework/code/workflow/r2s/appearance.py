"""Whole-scene appearance evidence, texture scope and persistent visual comparisons.

These contracts check evidence and scope, not semantic likeness. The Agent still
has to inspect the original, entire objects, and the complete rendered scene.
"""
import json
from pathlib import Path
from .contracts import ContractError
from .structure import evidence_file, file_sha

GROUPS = ('architecture', 'openings', 'furniture', 'soft_objects',
          'reflective_surfaces', 'lighting', 'exterior')
FIXED_VIEWS = ('comparison_source.png', 'comparison_wide.png', 'comparison_reverse.png')


def enabled(packet):
    return packet.get('refinement', {}).get('limits', {}).get('appearance_contract_version', 0) >= 1


def read(attempt, name, files):
    return json.loads(evidence_file(attempt, name, files).read_text())


def upstream(packet, stage, name):
    matches = [a for a in packet['input_artifacts'].get(stage, []) if Path(a['path']).name == name]
    if len(matches) != 1 or file_sha(matches[0]['path']) != matches[0]['sha256']:
        raise ContractError('Missing or changed appearance input: ' + stage + '/' + name)
    return matches[0]


def observation(data, size):
    targets = {t['entity']: t for t in data['appearance_targets']}
    whole = data.get('scene_appearance', {})
    if not all(whole.get(k) for k in ('global_palette', 'light_distribution', 'contrast_hierarchy', 'uncertainties')):
        raise ContractError('Observe the complete scene before local appearance details')
    coverage = whole.get('coverage', {})
    if set(coverage) != set(GROUPS):
        raise ContractError('Scene coverage must address architecture, openings, furniture, soft objects, reflections, lights and exterior')
    covered = set()
    for group, row in coverage.items():
        entities = row.get('entities', [])
        if bool(entities) == bool(row.get('absent_reason')) or not set(entities) <= targets.keys():
            raise ContractError('Declare observed targets or a concrete absence reason: ' + group)
        covered.update(entities)
    if covered != targets.keys():
        raise ContractError('Every appearance target needs a whole-scene coverage role')
    for target in targets.values():
        box(target['source_crop_xyxy'], size)
        if target.get('whole_object') is not True or type(target.get('soft_surface')) is not bool:
            raise ContractError('Target crop must cover the entire visible object/region and declare soft_surface')
        if not all(target.get('appearance', {}).get(k) for k in ('palette', 'pattern_layout', 'direction', 'scale_evidence', 'uncertainty')):
            raise ContractError('Record whole-object colour, pattern distribution, direction, scale and uncertainty')
    return targets


def box(value, size):
    if len(value) != 4 or not all(type(x) is int for x in value) or not (0 <= value[0] < value[2] <= size[0] and 0 <= value[1] < value[3] <= size[1]):
        raise ContractError('Invalid original-image appearance sample box')


def materials(data, observed, size, attempt, files):
    from PIL import Image
    targets = {t['entity']: t for t in observed['appearance_targets']}
    if data.get('appearance_source_sha256') != observed['appearance_source']['sha256']:
        raise ContractError('Material evidence must bind the accepted original')
    covered = set()
    soft_covered = set()
    for row in data.get('materials', []):
        entity = row.get('entity')
        if not entity or not row.get('material_names') or not row.get('objects'):
            raise ContractError('Material records need a target and actual material/object bindings')
        if entity in targets:
            covered.add(entity)
        elif not row.get('inferred_surface_reason'):
            raise ContractError('Unobserved surface materials require an explicit inference reason')
        if type(row.get('soft_surface')) is not bool:
            raise ContractError('Distinguish soft and rigid material bindings within mixed assemblies')
        if row['soft_surface']:
            soft_covered.add(entity)
        layers = row.get('layers', {})
        if not all(layers.get(k) for k in ('macro_pattern', 'microstructure', 'folds', 'illumination')):
            raise ContractError('Separate macro pattern, fine material detail, folds and illumination')
        if row.get('material_class') not in {'dielectric', 'metal', 'mixed', 'emissive'} or not row.get('parameter_basis'):
            raise ContractError('PBR parameters need a material class and evidence/labelled prior')
        scope = row.get('texture_scope', {})
        if scope.get('source_kind') not in {'original', 'procedural', 'licensed', 'generated', 'constant'}:
            raise ContractError('Texture source kind must be explicit')
        if scope.get('application') not in {'local', 'whole_object', 'tiled', 'constant'} or scope.get('mapping') not in {'uv', 'object', 'world', 'none'}:
            raise ContractError('Declare texture application scope and coordinates')
        if (scope['application'] == 'constant') != (scope['mapping'] == 'none'):
            raise ContractError('Only a constant surface can omit texture coordinates')
        if set(row.get('pbr_parameters', {})) != set(row['material_names']):
            raise ContractError('Declare actual PBR parameters for each bound material name')
        if row['soft_surface'] and scope['application'] != 'constant' and (scope['mapping'] != 'uv' or not scope.get('uv_map')):
            raise ContractError('Textured soft surfaces require a named object-following UV map')
        samples = scope.get('sample_boxes', [])
        for sample in samples:
            box(sample, size)
        if scope['source_kind'] == 'original' and not samples:
            raise ContractError('Source-derived textures must locate their original samples')
        whole_source = scope.get('source_extent') == 'whole_object'
        if whole_source:
            target_box = targets.get(entity, {}).get('source_crop_xyxy')
            if scope['source_kind'] != 'original' or len(samples) != 1 or not target_box or not (samples[0][0] <= target_box[0] and samples[0][1] <= target_box[1] and samples[0][2] >= target_box[2] and samples[0][3] >= target_box[3]):
                raise ContractError('Whole-object source mapping must cover the accepted whole-object crop')
        if scope['application'] == 'tiled' or (scope['source_kind'] == 'original' and scope['application'] == 'whole_object' and not whole_source):
            repeats = scope.get('repetition_boxes', [])
            for sample in repeats:
                box(sample, size)
            if len(repeats) < 2 or not scope.get('repetition_basis'):
                raise ContractError('Extending a sample requires at least two separate observed repeats and a visual explanation')
            for i, a in enumerate(repeats):
                for b in repeats[i+1:]:
                    if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                        raise ContractError('Overlapping crops are not independent evidence of repetition')
        if not scope.get('uncertain_completion') or len(set(row.get('whole_object_evidence', []))) < 2:
            raise ContractError('Record inferred completion and inspect whole-object material evidence')
        for ref in row['whole_object_evidence']:
            with Image.open(evidence_file(attempt, ref, files)) as image:
                image.verify()
    # Untextured and emissive surfaces are included; observed lights can be
    # represented by their visible housing. Hidden shell is audited separately.
    if covered != targets.keys():
        raise ContractError('Materials omit a whole-scene appearance target')
    if {entity for entity,t in targets.items() if t['soft_surface']} - soft_covered:
        raise ContractError('An observed soft object cannot be relabelled entirely rigid')
    for ref in data.get('neutral_light_previews', []):
        with Image.open(evidence_file(attempt, ref, files)) as image:
            image.verify()


def check_stage(name, attempt, response, packet):
    if not enabled(packet) or response['status'] == 'needs_input':
        return
    files = response.get('artifacts', [])
    from PIL import Image
    if name == 'agent_observe':
        data = read(attempt, 'observation.json', files)
        if not data.get('appearance_source'):
            raise ContractError('Whole-scene observation must explicitly bind its original image')
        source = data.get('appearance_source', packet.get('appearance_source'))
        observation(data, Image.open(source['path']).size)
    elif name in {'agent_model', 'agent_materials'}:
        ref = upstream(packet, 'agent_observe', 'observation.json')
        observed = json.loads(Path(ref['path']).read_text())
        if name == 'agent_model':
            scene = read(attempt, 'scene.json', files)
            ids = {o['id'] for o in scene['objects']}
            if not {t['entity'] for t in observed['appearance_targets']} <= ids:
                raise ContractError('Canonical scene omits an observed appearance region')
        else:
            data = read(attempt, 'material_calibration.json', files)
            if data.get('observation_sha256') != ref['sha256']:
                raise ContractError('Materials changed the accepted whole-object observation')
            materials(data, observed, Image.open(observed['appearance_source']['path']).size, attempt, files)
    elif name == 'agent_calibrate_lighting' and response['status'] == 'complete':
        data = read(attempt, 'lighting_calibration.json', files)
        if data.get('material_parameters_locked') is not True:
            raise ContractError('Lighting cannot compensate by changing accepted materials; revise materials first')
        checks = data.get('whole_scene_checks', {})
        if not all(checks.get(k) for k in ('light_distribution', 'shadow_direction', 'reflection_strength', 'contrast_hierarchy')):
            raise ContractError('Lighting needs whole-scene and cross-region consistency checks')


def check_review(attempt, response, packet, data, binding, best):
    if not enabled(packet):
        return
    files = response['artifacts']
    if not binding.get('comparison_protocol') or not binding.get('comparison_images'):
        raise ContractError('Whole-scene review needs the executable fixed-view protocol')
    required_checks = ['global_composition']
    if packet['stage'] == 'agent_review':
        required_checks += ['material_light_consistency', 'texture_scope', 'soft_shape']
        build = upstream(packet, 'build_render', 'appearance_audit.json')
        audit = json.loads(Path(build['path']).read_text())
        if audit.get('model_sha256') != binding['model_sha256'] or data.get('appearance_audit_sha256') != build['sha256']:
            raise ContractError('Appearance audit must bind the current saved model')
        if response['status'] == 'complete' and audit.get('failures'):
            raise ContractError('Actual material mapping or lighting lock failed')
    for key in required_checks:
        row = data.get('checks', {}).get(key, {})
        if row.get('status') not in {'pass', 'revise'} or not row.get('findings') or not row.get('evidence'):
            raise ContractError('Missing holistic appearance check: ' + key)
        hashes = {file_sha(evidence_file(attempt, p, files)) for p in row['evidence']}
        if not hashes <= set(binding['images'].values()):
            raise ContractError('Holistic check cites an image outside the current render')
        if not {binding['images']['source_reference.png'], binding['images']['source_view.png']} <= hashes:
            raise ContractError('Holistic checks must inspect the original and current full scene')
        if key=='material_light_consistency' and (not binding['images'].get('appearance_neutral.png') or binding['images']['appearance_neutral.png'] not in hashes):
            raise ContractError('Material/light review must include the actual full-scene neutral render')
        if response['status'] == 'complete' and row['status'] != 'pass':
            raise ContractError('A whole-scene mismatch cannot be demoted to an accepted limitation')
    for row in data['per_object']:
        if not row.get('whole_object_findings') or not row.get('context_findings'):
            raise ContractError('Review whole-object appearance and its relationship to the full scene')
    if best:
        if best.get('source_sha256') != binding['source_sha256']:
            raise ContractError('A new original belongs in a new case; do not erase the old comparison')
        for role, expected in [('before', best.get('comparison_images', {})), ('after', binding['comparison_images'])]:
            hashes = {file_sha(evidence_file(attempt, p, files)) for p in data['comparison'].get(role, [])}
            if set(expected) != set(FIXED_VIEWS) or not set(expected.values()) <= hashes:
                raise ContractError('Compare all three fixed views on both sides, not a convenient crop')
        if set(best.get('target_entities', [])) - {t['entity'] for t in packet['appearance_targets']}:
            raise ContractError('Observation revision cannot silently remove previously reviewed targets')
    else:
        hashes = {file_sha(evidence_file(attempt, p, files)) for p in data['checks']['global_composition']['evidence']}
        if not set(binding['comparison_images'].values()) <= hashes:
            raise ContractError('First candidate must inspect all fixed comparison views')
