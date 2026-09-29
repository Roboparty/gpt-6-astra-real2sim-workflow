"""Create a new native case with generation-skill stages; never copies prior runs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.generation_skills import config

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source_config',type=Path);p.add_argument('new_case',type=Path)
p.add_argument('--skills-root',type=Path,required=True);p.add_argument('--blender',required=True)
p.add_argument('--local-protocol',type=Path)
p.add_argument('--reference-mode',choices=['disabled','blocked','consume'],default='blocked')
p.add_argument('--reference-required',action='store_true')
p.add_argument('--reference-manifest',type=Path);p.add_argument('--reference-npz',type=Path);p.add_argument('--reference-provenance',type=Path)
a=p.parse_args();value=json.loads(a.source_config.read_text(encoding='utf-8-sig'))
if value.get('workflow_profile')!='quality_v2':raise ValueError('Existing quality_v2 case configuration required')
if any(not Path(e['path']).is_absolute() for e in value['inputs']):raise ValueError('Resolve original input paths explicitly before creating a case')
reference={'mode':a.reference_mode,'required':a.reference_required,'reason':'Readiness/inference not established by integration; no automatic install or model launch'}
if a.reference_mode=='consume':
    for key,path in [('manifest',a.reference_manifest),('npz',a.reference_npz),('provenance',a.reference_provenance)]:
        if path is None or not path.is_file():raise ValueError('Existing reference '+key+' required')
        reference[key]=str(path.resolve())
value['generation_skills']={'skills_root':str(a.skills_root.resolve()),'blender':a.blender,'reference':reference}
if a.local_protocol:value['generation_skills']['local_protocol']=str(a.local_protocol.resolve())
# Keep existing provenance, agent command, physics switches, refinement budget and
# stage parameters. Native executable workers must resolve to this isolated snapshot.
for name in ('build_geometry','build_render','export','validate','report'):
    stage=value.setdefault('stages',{}).setdefault(name,{})
    stage.setdefault('command',[sys.executable,'-m','r2s.stage_worker','{packet}'])
    stage.setdefault('parameters',{}).setdefault('blender',a.blender)
config(value)
a.new_case.mkdir(parents=True,exist_ok=False)
(a.new_case/'case.json').write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
(a.new_case/'integration_origin.json').write_text(json.dumps({'source_config':str(a.source_config.resolve()),
    'scope':'New case only; no original runs copied, no research continuation budget reset authorized',
    'workflow':str(Path(__file__).resolve().parents[1]/'workflow')},indent=2))
print(str(a.new_case/'case.json'))
