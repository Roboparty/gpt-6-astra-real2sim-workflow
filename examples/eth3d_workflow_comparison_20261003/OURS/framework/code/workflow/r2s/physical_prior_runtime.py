"""Apply explicit contact priors and inspect the compiled engine representation."""
import xml.etree.ElementTree as ET

import numpy as np

from .contracts import ContractError
from .physical_priors import validate_physical_priors


def apply_contact_priors(root, config, entity_ids=None):
    report = validate_physical_priors(config, entity_ids)
    geoms = {geom.get('name'): geom for geom in root.findall('.//geom')}
    contact = root.find('contact')
    existing = set()
    if contact is not None:
        existing = {tuple(sorted((p.get('geom1'), p.get('geom2')))) for p in contact.findall('pair')}
    for index, row in enumerate(report['contacts']):
        a, b = row['geom_pair']
        if a not in geoms or b not in geoms:
            raise ContractError('Physical prior refers to unknown collision geoms: ' + str([a, b]))
        if any(int(geoms[name].get('contype','1'))==0 and int(geoms[name].get('conaffinity','1'))==0 for name in [a,b]):
            raise ContractError('Contact priors cannot activate non-colliding visual geometry')
        if tuple(sorted((a, b))) in existing:
            raise ContractError('Contact prior would overwrite an existing pair')
        if contact is None:
            contact = ET.SubElement(root, 'contact')
        sliding, torsional, rolling = row['prior']['friction']
        values = [sliding, sliding, torsional, rolling, rolling]
        name = 'physical_prior_pair_' + str(index)
        ET.SubElement(contact, 'pair', name=name, geom1=a, geom2=b,
                      friction=' '.join(map(str, values)), condim=str(row['prior']['condim']))
        row.update(pair_name=name, xml_friction=values)
    report['material_application'] = 'Reference metadata only; existing masses and Blender shaders are not overwritten'
    report['completion_application'] = 'Recorded authored geometry assumption, not a recovered observation'
    return report


def audit_contact_priors(model, data, report):
    import mujoco
    for row in report['contacts']:
        pid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_PAIR, row['pair_name'])
        if pid < 0 or not np.allclose(model.pair_friction[pid], row['xml_friction'], rtol=0, atol=1e-12):
            raise ContractError('Compiled contact friction differs from requested prior')
        if int(model.pair_dim[pid]) != row['prior']['condim']:
            raise ContractError('Compiled contact dimension differs from requested prior')
        geoms = {int(model.pair_geom1[pid]), int(model.pair_geom2[pid])}
        observations = [dict(friction=c.friction.tolist(), condim=int(c.dim))
                        for c in data.contact if {int(c.geom1), int(c.geom2)} == geoms]
        for observed in observations:
            if observed['condim'] != row['prior']['condim'] or not np.allclose(observed['friction'], row['xml_friction']):
                raise ContractError('Active contact differs from requested prior')
        row.update(compiled_friction=model.pair_friction[pid].tolist(),
                   compiled_condim=int(model.pair_dim[pid]), active_contacts=observations,
                   contact_observed=bool(observations))
    report['engine_version'] = mujoco.__version__
    report['status'] = 'passed'
    return report
