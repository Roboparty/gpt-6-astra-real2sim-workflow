"""Reference-data integrity and provenance/units boundary checks; no simulator needed."""
import copy
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.contracts import ContractError
from r2s.physical_priors import load_library, contact_prior, material_prior, validate_physical_priors


def rejects(config):
    try:
        validate_physical_priors(config, {'cabinet'})
    except ContractError:
        return
    raise AssertionError('Invalid prior configuration was accepted')


def main():
    library = load_library()
    assert len(library['sha256']) == 64
    for material in library['materials'].values():
        density = material['density']
        assert density['unit'] == 'kg/m3' and math.isfinite(density['value']) and density['value'] > 0
        if density['range'] is not None:
            assert 0 < density['range'][0] <= density['value'] <= density['range'][1]
        optical = material['optical']
        assert optical['status'] == 'assumed'
        assert 0 <= optical['roughness_range'][0] <= optical['roughness'] <= optical['roughness_range'][1] <= 1
        assert 0 <= optical['metallic'] <= 1
        for prop in (density, optical):
            for source_id in prop['source_ids']:
                source = library['sources'][source_id]
                assert source['url'].startswith('https://') and source['locator']
                assert source['access'] in {'primary_full_text', 'primary_search_excerpt'}

    original = {
        'materials': [{'entity': 'cabinet', 'component': 'left_panel',
                       'material_id': 'mdf_laminated_15_19mm',
                       'assignment_basis': 'Unidentified panel; MDF is a documented analogue',
                       'volume_m3': 0.02, 'volume_basis': 'component_dimensions'}],
        'contacts': [{'geom_pair': ['cabinet_foot', 'floor'],
                      'preset': 'mujoco_default_v1', 'conditions': 'Dry assumed; finish and load unmeasured'}],
        'completions': [{'entity': 'cabinet', 'regions': ['back'], 'basis': 'symmetry',
                         'evidence': ['front_reference.png'], 'assumption': 'Rear panel follows visible side frame',
                         'observed': False}]
    }
    config = copy.deepcopy(original)
    report = validate_physical_priors(config, {'cabinet'})
    assert config == original, 'Validation must not mutate the source scene'
    assert report['physical_calibration'] is False
    assert report['materials'][0]['estimated_mass_kg'] == 14
    assert report['materials'][0]['parameter_provenance'] == 'assumed'
    assert report['contacts'][0]['prior']['friction'] == [1.0, 0.005, 0.0001]
    assert contact_prior()['units'] == ['dimensionless', 'm', 'm']
    assert contact_prior()['condim'] == 3
    assert material_prior('glass_soda_lime')['density']['range'] is None
    report['materials'][0]['prior']['density']['value'] = 1
    assert material_prior('mdf_laminated_15_19mm')['density']['value'] == 700
    without_volume = copy.deepcopy(original)
    del without_volume['materials'][0]['volume_m3']
    del without_volume['materials'][0]['volume_basis']
    assert validate_physical_priors(without_volume)['materials'][0]['estimated_mass_kg'] is None

    mutations = [
        lambda c: c['materials'][0].update(volume_m3=float('nan')),
        lambda c: c['materials'][0].update(volume_m3=float('inf')),
        lambda c: c['materials'][0].update(volume_m3=True),
        lambda c: c['materials'][0].update(volume_m3=-1),
        lambda c: c['materials'][0].update(volume_basis='whole_entity_aabb'),
        lambda c: c['materials'][0].update(material_id='unknown'),
        lambda c: c['materials'][0].update(entity='missing'),
        lambda c: c['materials'][0].update(parameter_provenance='measured'),
        lambda c: c['materials'][0].update(assignment_basis=''),
        lambda c: c['materials'].append(copy.deepcopy(c['materials'][0])),
        lambda c: c['contacts'][0].update(geom_pair=['floor', 'floor']),
        lambda c: c['contacts'][0].update(geom_pair=['floor']),
        lambda c: c['contacts'][0].update(conditions=''),
        lambda c: c['contacts'][0].update(friction=[0.8, 0.1, 0.1]),
        lambda c: c['contacts'].append({**c['contacts'][0], 'geom_pair': ['floor', 'cabinet_foot']}),
        lambda c: c['completions'][0].update(observed=True),
        lambda c: c['completions'][0].pop('observed'),
        lambda c: c['completions'][0].update(evidence=[]),
        lambda c: c['completions'].append(copy.deepcopy(c['completions'][0])),
        lambda c: c.update(materials='not-a-list'),
        lambda c: c.update(physics={'hinges': True}),
    ]
    for mutate in mutations:
        bad = copy.deepcopy(original)
        mutate(bad)
        rejects(bad)
    assert validate_physical_priors({})['materials'] == []
    print(f'PASS physical prior source integrity, immutable report, SI units, unknown mass and {len(mutations)} rejection cases')


if __name__ == '__main__':
    main()
