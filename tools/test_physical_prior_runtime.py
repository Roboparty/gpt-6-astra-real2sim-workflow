"""Verify actual sphere-floor contact parameters, not just preset JSON."""
import copy
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from r2s.contracts import ContractError
from r2s.physical_prior_runtime import apply_contact_priors, audit_contact_priors

root = ET.fromstring('''<mujoco><worldbody>
<geom name="floor" type="plane" size="1 1 .1" friction=".7 .01 .001"/>
<body pos="0 0 .09"><freejoint/><geom name="sphere" type="sphere" size=".1" mass="1" friction="1.2 .01 .001"/></body>
</worldbody></mujoco>''')
untouched = ET.tostring(root)
report = apply_contact_priors(root, {})
assert untouched == ET.tostring(root) and report['contacts'] == []
config = {'contacts': [{'geom_pair': ['floor', 'sphere'], 'preset': 'mujoco_default_v1',
                        'conditions': 'Synthetic dry-contact mechanism test, not material identification'}]}
report = apply_contact_priors(root, config)
model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)
report = audit_contact_priors(model, data, report)
assert report['contacts'][0]['contact_observed']
assert np.allclose(data.contact[0].friction, [1, 1, .005, .0001, .0001])
assert data.contact[0].dim == 3
visual=ET.SubElement(root.find('worldbody'),'geom',name='visual',type='sphere',size='.1',contype='0',conaffinity='0')
try:
    apply_contact_priors(copy.deepcopy(root),{'contacts':[{'geom_pair':['floor','visual'],'conditions':'must reject visual-only geometry'}]})
except ContractError:pass
else:raise AssertionError('Explicit pair activated visual-only geometry')
for bad in [config, {'contacts': [{'geom_pair': ['floor', 'missing'], 'conditions': 'test'}]}]:
    try:
        apply_contact_priors(copy.deepcopy(root), bad)
    except ContractError:
        pass
    else:
        raise AssertionError('Conflicting or missing contact must be rejected')
print(json.dumps({'status': 'passed', 'engine': mujoco.__version__,
                  'active_contact_friction': data.contact[0].friction.tolist(),
                  'condim': int(data.contact[0].dim), 'default_scene_unchanged': True}))
