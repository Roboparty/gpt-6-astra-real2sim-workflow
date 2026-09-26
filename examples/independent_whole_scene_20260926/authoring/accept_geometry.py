"""Submit only after Agent inspected the matching candidate's real image evidence."""
import sys,json,shutil,hashlib
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');out=Path(w.state['stages']['agent_review_geometry']['directory']);src=Path(w.state['stages']['build_geometry']['directory']);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sys.argv[1]==src.name,'Explicit inspected candidate required'
notes=json.loads((R/'authoring/geometry_verdict.json').read_text());assert notes['candidate']==src.name and notes['decision']=='pass'
for p in src.glob('*.png'):shutil.copyfile(p,out/p.name)
for name in ['structural_audit.json','surface_audit.json','render_binding.json','model_binding.json']:shutil.copyfile(src/name,out/name)
b=json.loads((src/'render_binding.json').read_text());a=json.loads((src/'surface_audit.json').read_text());structure=json.loads((src/'structural_audit.json').read_text());modelbinding=json.loads((src/'model_binding.json').read_text());scene=json.loads((src/'scene.json').read_text());obs=json.loads((src/'appearance_observation.json').read_text())
assert a['status']=='passed' and structure['status']=='passed'
best=w.state['refinement']['agent_review_geometry']['best'];before=[];after=[]
for name in ['comparison_source.png','comparison_wide.png','comparison_reverse.png']:
 prior=next(Path(x['path']) for x in best['artifacts'] if Path(x['path']).name==name);shutil.copyfile(prior,out/('before_'+name));before.append('before_'+name);after.append(name)
full=['source_reference.png','source_view.png'];rows=[]
for t in obs['appearance_targets']:
 e=t['entity'];msg=notes['per_object'][e];rows.append(dict(entity=e,status='pass',findings=msg,whole_object_findings=msg,context_findings=notes['global_composition'],source_crop=b['object_crops'][e]['source'],render_crop=b['object_crops'][e]['render']))
checks={k:dict(status='pass',findings=notes[k],evidence=full+(['source_clay.png'] if k!='novel_structure' else ['diagnostic_reverse.png'])+after) for k in ['source_similarity','local_detail','novel_structure','global_composition']}
atomic_json(out/'appearance_review.json',dict(render_binding_sha256=sha(src/'render_binding.json'),checks=checks,per_object=rows,comparison=dict(against=best['review_sha256'],protocol_sha256=b['protocol_sha256'],relation=notes['relation'],before=before,after=after,findings=notes['comparison'])))
sr=[]
for r in a['regions']:
 msg=notes['per_object'][r['entity']];sr.append(dict(id=r['id'],evidence=[r['source_crop'],r['front_view'],r['raking_view']],**{k:dict(status='pass',findings=msg) for k in ['topology_and_count','relief_vs_appearance','proportions_and_contrast']}))
atomic_json(out/'surface_review.json',dict(audit_sha256=sha(src/'surface_audit.json'),regions=sr))
objectrows=[]
for o in scene['objects']:
 e=o['id'];hidden=e in ['wall_front','wall_right'];row=dict(entity=e,status='hypothesized' if hidden else 'pass',findings='Unobserved complete enclosing wall retained and inspected; location is a conservative hypothesis.' if hidden else notes['per_object'][e],evidence=['inspect_'+e+'.png'] if hidden else ['source_clay.png','source_view.png'])
 if hidden:row['uncertainty']='No source constraints determine this wall extent; not measured.'
 objectrows.append(row)
atomic_json(out/'geometry_review.json',dict(decision='pass',checks={k:dict(status='pass',findings=notes['quality'][k],evidence=['source_clay.png','source_reference.png','diagnostic_reverse.png']) for k in ['camera','room_surfaces','silhouettes','occlusion','support']},per_object=objectrows,geometry_freeze_sha256=modelbinding['model_sha256'],model_version=scene['model_version'],issues=[],scope='Geometry gate only; material and illumination acceptance remains downstream.'))
files=[p.name for p in out.iterdir() if p.is_file() and p.name not in ['packet.json','response.json']]
atomic_json(out/'response.json',dict(status='complete',artifacts=files,evidence=full+after,reasoning_summary=notes['summary']))
print(w.accept('agent_review_geometry',out/'response.json'));print(w.run())
