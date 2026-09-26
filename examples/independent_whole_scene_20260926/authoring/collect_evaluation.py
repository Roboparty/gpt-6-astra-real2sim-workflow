import json,hashlib,statistics,sys
from pathlib import Path
R=Path('/home/wqz/real2sim_whole_scene_20260926');S=json.loads((R/'case/runs/state.json').read_text());dest=R/'evaluation';dest.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text()) if p.is_file() else None
def stage(n):return Path(S['stages'][n]['directory'])
result={'scope':'Convergence evaluation, not completed formal workflow or independent reality accuracy','source_sha256':hashlib.sha256((R/'input/01_bedroom.jpg').read_bytes()).hexdigest(),'stages':{k:{x:v.get(x) for x in ['status','directory','attempt','finished']} for k,v in S['stages'].items()},'visual_review':read(stage('agent_review')/'review.json'),'lighting':read(stage('agent_calibrate_lighting')/'regional_light_metrics.json'),'diagnostic_checks':read(R/'delivery_candidate/diagnostic_status.json'),'reload':read(R/'delivery_candidate/export/reload_validation.json'),'simulation':read(R/'delivery_candidate/export/simulation_audit.json')}
result['audits']={}
for st,names in [('build_geometry',['structural_audit.json','surface_audit.json']),('build_render',['surface_audit.json','appearance_audit.json'])]:
 for n in names:
  a=read(stage(st)/n)
  if a:result['audits'][st+'/'+n]={k:a.get(k) for k in ['status','failures','warnings']}
a=read(R/'delivery_candidate/export/geometry_audit.json')
if a:
 errors=[l['error_px'] for l in a['camera_reprojection']]
 result['camera_fit']={'landmarks_in_export_audit':len(errors),'median_px':statistics.median(errors) if errors else None,'max_px':max(errors) if errors else None,'interpretation':'No fit landmarks were carried into the export audit; original fit diagnostics are separate in authoring/fit.json, not independent accuracy.'}
 result['source_camera_fit']=read(R/'authoring/fit.json')
 result['geometry']={'entities':len(a['entities']),'warnings':a['warnings'],'usd_export':a.get('usd_export'),'material_portability':a['material_portability']}
result['artifacts']={}
for n in ['scene.blend','scene.glb','scene.usdc','scene.xml','scene.json','source_view_high.png']:
 p=R/'delivery_candidate/export'/n
 if p.is_file():result['artifacts'][n]={'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(dest/'evaluation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['stages','audits','camera_fit','diagnostic_checks'] if k in result},indent=2))
