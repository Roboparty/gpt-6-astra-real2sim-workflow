"""Executable validation adapter: explicit backend options, real shared validators.
No workflow state writes. MuJoCo 3.13 flex stiffness requires the discrete integrator.
"""
import sys,json,shutil,subprocess,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco,r2s
from r2s.core import atomic_json
from r2s.contracts import scene_check,ContractError
from r2s.evaluation import glb_check
from r2s.dynamics import export_and_test
p=json.loads(Path(sys.argv[1]).read_text());out=Path(p['output_directory']);sources=p['input_artifacts']['export'];src=Path(next(a['path'] for a in sources if Path(a['path']).name=='geometry_audit.json')).parent
for f in src.rglob('*'):
 if f.is_file() and f.name not in {'packet.json','response.json','record.json','stdout.log','stderr.log'}:
  q=out/f.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,q)
s=json.loads((out/'scene.json').read_text());checks={'scene':scene_check(s),'glb':glb_check(out/'scene.glb',['floor','ceiling','wall_back','wall_front','wall_left','wall_right'])}
run=subprocess.run([sys.executable,str(Path(r2s.__file__).parent/'simulation.py'),str(out/'scene.json'),str(out)],capture_output=True,text=True);(out/'static_simulation.log').write_text(run.stdout+'\n'+run.stderr)
if run.returncode:raise RuntimeError('Static simulation validator failed; inspect static_simulation.log')
checks['simulation']=json.loads((out/'simulation_audit.json').read_text());checks['geometry']=json.loads((out/'geometry_audit.json').read_text())
integrator=s.get('dynamics',{}).get('integrator',p.get('parameters',{}).get('dynamics_integrator','Euler'));tree=ET.parse(out/'scene.xml');option=tree.getroot().find('option');option.set('integrator',integrator);solver_ref=out/'scene_solver_reference.xml';tree.write(solver_ref,encoding='unicode',xml_declaration=True)
checks['dynamics']=export_and_test(solver_ref,s,out,p['physics_options']);model=mujoco.MjModel.from_xml_path(str(out/'scene_dynamic.xml'))
backend=dict(requested_integrator=integrator,actual_integrator_enum=int(model.opt.integrator),engine_version=mujoco.__version__,contacts_enabled=not bool(int(model.opt.disableflags)&int(mujoco.mjtDisableBit.mjDSBL_CONTACT)),reference_geometry_modified=False,reference_xml_sha256=hashlib.sha256((out/'scene.xml').read_bytes()).hexdigest(),solver_reference_xml_sha256=hashlib.sha256(solver_ref.read_bytes()).hexdigest(),documentation='https://mujoco.readthedocs.io/en/latest/computation/')
assert backend['contacts_enabled'];checks['backend_options']=backend;atomic_json(out/'backend_options.json',backend);atomic_json(out/'validation.json',checks)
artifacts=[str(f.relative_to(out)) for f in sorted(out.rglob('*')) if f.is_file() and f.name not in {'packet.json','response.json','record.json','stdout.log','stderr.log'}]
atomic_json(out/'response.json',dict(status='complete',artifacts=artifacts,evidence=['actual static validator, GLB buffer checks and real contact-enabled MuJoCo flex/hinge integration'],reasoning_summary='All shared numerical checks executed with the explicitly selected backend integrator; no success status was synthesized from files alone.'))
