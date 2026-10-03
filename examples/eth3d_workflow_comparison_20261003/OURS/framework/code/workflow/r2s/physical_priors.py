"""Small, source-bound physical priors; no scene mutation or calibration claims."""
import copy
import hashlib
import json
import math
from pathlib import Path

from .contracts import ContractError

LIBRARY_PATH = Path(__file__).resolve().parents[2] / 'public_contract' / 'physical_priors.json'


def load_library():
    """Read the shipped library and bind reports to its exact bytes."""
    raw = LIBRARY_PATH.read_bytes()
    result = json.loads(raw)
    result['sha256'] = hashlib.sha256(raw).hexdigest()
    return result


def _prior(library, section, key):
    if not isinstance(key, str) or key not in library[section]:
        raise ContractError(f'Unknown physical prior: {section}/{key}')
    return copy.deepcopy(library[section][key])


def material_prior(material_id):
    return _prior(load_library(), 'materials', material_id)


def contact_prior(preset='mujoco_default_v1'):
    return _prior(load_library(), 'contacts', preset)


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f'Physical priors require nonempty {field}')
    return value


def _strings(value, field):
    if not isinstance(value, list) or not value:
        raise ContractError(f'Physical priors require nonempty list: {field}')
    for item in value:
        _text(item, field)
    if len(set(value)) != len(value):
        raise ContractError(f'Duplicate {field}')
    return value


def _fields(row, allowed):
    if not isinstance(row, dict) or set(row) - allowed:
        raise ContractError('Unknown physical-prior field or non-object row')


def validate_physical_priors(config, entity_ids=None):
    """Resolve explicitly assigned priors into a sidecar report.

    Missing material volume stays unknown. No automatic mass, geometry, shader,
    or XML changes occur. Geom pair existence is checked by the XML integration,
    since scene entities and simulator geoms need not have the same names.
    """
    _fields(config, {'materials', 'contacts', 'completions'})
    library = load_library()
    result = {'schema_version': 'real2sim.physical_prior_report/1.0',
              'library_sha256': library['sha256'],
              'materials': [], 'contacts': [], 'completions': [],
              'sources': {}, 'physical_calibration': False,
              'limitations': copy.deepcopy(library['limitations'])}
    for section in ('materials', 'contacts', 'completions'):
        if not isinstance(config.get(section, []), list):
            raise ContractError(f'Physical priors {section} must be a list')

    def entity(row):
        name = _text(row.get('entity'), 'entity')
        if entity_ids is not None and name not in entity_ids:
            raise ContractError('Unknown physical-prior entity: ' + name)
        return name

    def add_sources(ids):
        for source_id in ids:
            result['sources'][source_id] = copy.deepcopy(library['sources'][source_id])

    assigned = set()
    for row in config.get('materials', []):
        _fields(row, {'entity', 'component', 'material_id', 'assignment_basis', 'volume_m3', 'volume_basis'})
        name = entity(row)
        component = _text(row.get('component', name), 'component')
        if (name, component) in assigned:
            raise ContractError('Duplicate physical material assignment')
        assigned.add((name, component))
        prior = _prior(library, 'materials', row.get('material_id'))
        resolved = copy.deepcopy(row)
        resolved.update(entity=name, component=component, prior=prior,
                        parameter_provenance='assumed', estimated_mass_kg=None)
        _text(row.get('assignment_basis'), 'assignment_basis')
        if 'volume_m3' in row:
            volume = row['volume_m3']
            if type(volume) not in (float, int) or not math.isfinite(volume) or volume <= 0:
                raise ContractError('Material volume must be finite and positive')
            if row.get('volume_basis') not in {'closed_material_mesh', 'component_dimensions'}:
                raise ContractError('Material volume needs component geometry; whole entity AABB is not accepted')
            mass = volume * prior['density']['value']
            if not math.isfinite(mass):
                raise ContractError('Nonfinite estimated mass')
            resolved['estimated_mass_kg'] = mass
        elif 'volume_basis' in row:
            raise ContractError('volume_basis requires volume_m3')
        result['materials'].append(resolved)
        add_sources(prior['density']['source_ids'] + prior['optical']['source_ids'])

    pairs = set()
    for row in config.get('contacts', []):
        _fields(row, {'geom_pair', 'preset', 'conditions'})
        pair = _strings(row.get('geom_pair'), 'geom_pair')
        if len(pair) != 2:
            raise ContractError('Contact prior requires two distinct geom names')
        key = tuple(sorted(pair))
        if key in pairs:
            raise ContractError('Duplicate contact pair')
        pairs.add(key)
        _text(row.get('conditions'), 'contact conditions')
        preset = row.get('preset', 'mujoco_default_v1')
        prior = _prior(library, 'contacts', preset)
        result['contacts'].append({**copy.deepcopy(row), 'preset': preset, 'prior': prior,
                                   'parameter_provenance': 'assumed'})
        add_sources(prior['source_ids'])

    completed = set()
    for row in config.get('completions', []):
        _fields(row, {'entity', 'regions', 'basis', 'evidence', 'assumption', 'observed'})
        name = entity(row)
        regions = _strings(row.get('regions'), 'regions')
        for region in regions:
            if (name, region) in completed:
                raise ContractError('Duplicate completed region')
            completed.add((name, region))
        if row.get('basis') not in library['completion_bases']:
            raise ContractError('Unknown backside completion basis')
        if row.get('observed') is not False:
            raise ContractError('Completed hidden geometry must explicitly have observed=false')
        _strings(row.get('evidence'), 'completion evidence')
        _text(row.get('assumption'), 'completion assumption')
        result['completions'].append({**copy.deepcopy(row), 'parameter_provenance': 'assumed'})
    return result
