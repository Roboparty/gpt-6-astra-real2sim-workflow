"""Record the inspected convergence candidate without bypassing or rerunning its gate."""
import sys,json,shutil,hashlib
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');assert w.valid('build_render');out=Path(w.state['stages']['agent_review']['directory']);src=Path(w.state['stages']['build_render']['directory']);best=w.state['refinement']['agent_review']['best'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (out/'response.json').exists(),'Preserve previous review'
for p in src.glob('*.png'):shutil.copyfile(p,out/p.name)
for name in ['appearance_audit.json','surface_audit.json','render_binding.json']:shutil.copyfile(src/name,out/name)
b=json.loads((src/'render_binding.json').read_text());a=json.loads((src/'surface_audit.json').read_text());obs=json.loads((src/'appearance_observation.json').read_text());before=[];after=[]
for name in ['comparison_source.png','comparison_wide.png','comparison_reverse.png']:
 old=next(Path(x['path']) for x in best['artifacts'] if Path(x['path']).name==name);shutil.copyfile(old,out/('before_'+name));before.append('before_'+name);after.append(name)
notes={
 'bed':'Bed footprint and furniture structure are credible, but duvet and pillow folds remain too uniform and smooth; source has irregular bunched cloth and a more varied textile pattern. Repeated simplified toy heads are conspicuously unlike the source collection. These block strict appearance acceptance.',
 'shoe_cabinet':'Cabinet topology, two drawers, framed doors and right shelves are retained. Shoes remain simplified repeated forms, with source shape/color variety not reconstructed closely enough.',
 'reflective_board':'Window reflection is physically rendered with a nonmetallic finish, but reflection contrast and shape differ from source and the left highlight is too concentrated. The fitted roughness field is a hypothesis, not measured material truth.',
 'exterior':'Lower shrubs and exposed pale rails improve the prior tall-canopy mismatch. Visible outdoor spatial content remains schematic; exact source rail/urban silhouette and plant distribution are not recovered.',
 'floor':'Dark grey carpet covers the full floor with directional fibres; acceptable component role and contrast. Exact measured carpet material is unknown.',
 'ceiling_fixtures':'Grid, vent, white insert, sprinkler and round fixture roles retained, but vent contrast is too dark and dominant against the source. White insert electrical identity/state unconfirmed.',
}
blocking={'bed','shoe_cabinet','reflective_board','exterior','ceiling_fixtures'};full=['source_reference.png','source_view.png'];rows=[]
for t in obs['appearance_targets']:
 e=t['entity'];msg=notes.get(e,'Source and entire object inspected in source, neutral and fixed novel views: plausible role, scale, topology and placement; no additional blocking finding at this convergence review.');c=b['object_crops'][e]
 rows.append(dict(entity=e,status='revise' if e in blocking else 'pass',findings=msg,whole_object_findings=msg,context_findings='Whole scene remains needs_revision; individual passes do not imply overall approval.',source_crop=c['source'],render_crop=c['render']))
defect='Strict visual acceptance remains blocked by textiles/accessories, reflected appearance and schematic exterior. Stop this convergence round with an honest needs_revision verdict; retain the complete candidate and engineering diagnostics.'
checks={}
for key in ['source_similarity','local_detail','novel_structure','global_composition','material_light_consistency','texture_scope','soft_shape']:
 status='pass' if key in ['novel_structure','global_composition','texture_scope'] else 'revise'
 checks[key]=dict(status=status,findings=defect if status=='revise' else 'Actual fixed/source/neutral images inspected: complete room and correctly scoped full-surface textures preserve the accepted structure; global room layout is credible.',evidence=full+after+['appearance_neutral.png','diagnostic_reverse.png'])
atomic_json(out/'appearance_review.json',dict(render_binding_sha256=sha(src/'render_binding.json'),appearance_audit_sha256=sha(src/'appearance_audit.json'),checks=checks,per_object=rows,comparison=dict(relation='better',against=best['review_sha256'],protocol_sha256=b['protocol_sha256'],before=before,after=after,findings='Three persistent fixed views compared to the previous best and source. Lower outdoor vegetation restores visible rail/urban bands. Interior geometry is retained. Residual appearance deficits still block approval.')))
regions=[]
for r in a['regions']:
 status='revise' if r['entity'] in blocking else 'pass';msg=notes.get(r['entity'],'Source and actual front/raking surfaces inspected; no additional blocking surface topology finding.')
 regions.append(dict(id=r['id'],evidence=[r['source_crop'],r['front_view'],r['raking_view']],**{k:dict(status=status,findings=msg) for k in ['topology_and_count','relief_vs_appearance','proportions_and_contrast']}))
atomic_json(out/'surface_review.json',dict(audit_sha256=sha(src/'surface_audit.json'),regions=regions))
atomic_json(out/'review.json',dict(decision='revise',same_camera_comparison=True,source_comparison=full,issues=[dict(severity='major',blocking=True,description=notes[e]) for e in sorted(blocking)],findings=notes,convergence='Stopped refinement per user request; candidate preserved for delivery and diagnostic checks.'))
files=[p.name for p in out.iterdir() if p.is_file() and p.name not in ['packet.json','response.json']]
atomic_json(out/'response.json',dict(status='changes_requested',artifacts=files,evidence=full+after+['appearance_neutral.png'],reasoning_summary=defect,issues=[dict(entity=e,defect=notes[e],severity='major',evidence=[b['object_crops'][e]['source'],b['object_crops'][e]['render']],responsible_stage='agent_model') for e in sorted(blocking)],revision=dict(stage='agent_model',reason=defect,strategy='If explicitly resumed, prioritize source-shaped textile folds and distinct accessory silhouettes; retain camera, layout and accepted full-room structure. Rebuild materials and recalibrate only after geometry re-review.')))
print(w.accept('agent_review',out/'response.json'))
print('CONVERGENCE_STOP: no route_revision, run, export, validate, report or freeze invoked through Workflow.')
