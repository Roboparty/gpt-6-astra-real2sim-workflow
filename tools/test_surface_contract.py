"""Source/representation regressions; mesh regressions run in real Blender separately."""
import copy,json,tempfile,sys
from pathlib import Path
from PIL import Image
from r2s.surfaces import observation,realization,enabled,check_response
from r2s.structure import file_sha
from r2s.contracts import ContractError
from r2s.refinement import limits
assert limits({'refinement':{}})['surface_contract_version']==1
check_response(None,'ingest',Path('no-packet-for-ingest'),{'status':'complete'})

with tempfile.TemporaryDirectory() as temp:
 p=Path(temp);Image.new('RGB',(20,20),(100,120,130)).save(p/'original.png');Image.open(p/'original.png').crop((2,2,18,18)).save(p/'crop.png')
 original=dict(appearance_source=dict(path=str(p/'original.png'),sha256=file_sha(p/'original.png')),appearance_targets=[dict(entity='cabinet')])
 obs=dict(schema='real2sim.surface-observation/1',source_sha256=file_sha(p/'original.png'),regions=[dict(id='front',entity='cabinet',pattern='two panels',source_box_xyxy=[2,2,18,18],source_crop='crop.png',allow_repeated_relief=False,features=[dict(id='panels',description='Two bounded inset fields',classification='geometry',count=2,depth_cues=['edge shadow'],confidence=.9),dict(id='lines',description='Faint image lines',classification='uncertain',alternatives=['shading','print'])])])
 model=dict(regions=[dict(id='front',entity='cabinet',pattern='two panels',inspection_objects=['door'],normal_world=[1,0,0],up_world=[0,0,1],features=[dict(id='panels',representation='geometry',count=2,mesh_refs=[dict(object='door',vertex_group='panels')]),dict(id='lines',representation='omitted')])])
 def write(o,m):
  (p/'observation.json').write_text(json.dumps(original));(p/'surface_observation.json').write_text(json.dumps(o));m['observation_sha256']=file_sha(p/'surface_observation.json');(p/'surface_realization.json').write_text(json.dumps(m));return [f.name for f in p.iterdir()]
 files=write(obs,model);observation(p,files,{});realization(p,files);count=1
 for name,mutate in [
  ('wrong count',lambda o,m:m['regions'][0]['features'][0].update(count=12)),
  ('uncertain lines to relief',lambda o,m:m['regions'][0]['features'][1].update(representation='geometry',count=12,mesh_refs=[dict(object='door')])),
  ('uncertain lines to bump',lambda o,m:m['regions'][0]['features'][1].update(representation='micro_bump',depth_m=.0001)),
  ('missing region',lambda o,m:m['regions'].clear()),
  ('wrong surface type',lambda o,m:m['regions'][0].update(pattern='slatted')),
  ('text-only product confirmation',lambda o,m:o['regions'][0].update(product_candidate='Example',manufacturer_image_review='consistent')),
  ('unsupported confidence',lambda o,m:o['regions'][0]['features'][0].update(confidence=.5)),
 ]:
  o=copy.deepcopy(obs);m=copy.deepcopy(model);mutate(o,m);files=write(o,m)
  try:observation(p,files,{});realization(p,files)
  except ContractError:count+=1
  else:raise AssertionError(name+' was accepted')
 files=write(obs,copy.deepcopy(model));Image.new('RGB',(16,16),'white').save(p/'crop.png')
 try:observation(p,files,{})
 except ContractError:count+=1
 else:raise AssertionError('Altered source crop accepted')
 assert not enabled({}) and enabled({'refinement':{'limits':{'surface_contract_version':1}}})
 # Review gate fixtures: a plausible review must not override failed/stale
 # executable evidence or omit the raking view.
 for name,color in [('front.png','grey'),('raking.png','black')]:Image.new('RGB',(16,16),color).save(p/name)
 audit=dict(model_sha256='model-A',status='passed',failures=[],regions=[dict(id='front',source_crop='crop.png',front_view='front.png',raking_view='raking.png')],images={n:file_sha(p/n) for n in ['crop.png','front.png','raking.png']})
 verdict=dict(regions=[dict(id='front',evidence=['crop.png','front.png','raking.png'],**{k:dict(status='pass',findings='Protocol fixture only') for k in ['topology_and_count','relief_vs_appearance','proportions_and_contrast']})])
 for name,mutate,reject in [('valid review',lambda a,r:None,False),('failed mesh audit',lambda a,r:a.update(status='failed',failures=['wrong relief']),True),('stale model',lambda a,r:a.update(model_sha256='model-B'),True),('missing raking view',lambda a,r:r['regions'][0].update(evidence=['crop.png','front.png']),True)]:
  a=copy.deepcopy(audit);r=copy.deepcopy(verdict);mutate(a,r)
  (p/'surface_audit.json').write_text(json.dumps(a));(p/'render_binding.json').write_text(json.dumps(dict(model_sha256='model-A')));r['audit_sha256']=file_sha(p/'surface_audit.json');(p/'surface_review.json').write_text(json.dumps(r))
  (p/'packet.json').write_text(json.dumps(dict(refinement={'limits':{'surface_contract_version':1}},input_artifacts={'build_render':[dict(path=str(p/n),sha256=file_sha(p/n)) for n in ['surface_audit.json','render_binding.json']]})))
  try:check_response(None,'agent_review',p,dict(status='complete',artifacts=[f.name for f in p.iterdir()]))
  except ContractError:
   assert reject,name
  else:assert not reject,name
  count+=1
 print('SURFACE_CONTRACT_REGRESSIONS_PASSED',count)
