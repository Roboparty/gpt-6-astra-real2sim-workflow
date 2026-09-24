"""Schema regression fixtures, separate from the actual mesh mutation tests."""
import json,copy,tempfile,hashlib,sys
from pathlib import Path
from r2s.structure import review_contract,structure_contract,file_sha
from r2s.contracts import ContractError
root=Path(__file__).resolve().parents[1];fixtures=root/'tests/fixtures';s=json.loads(((fixtures/'scene.json') if fixtures.exists() else (root/'candidates/019/scene.json')).read_text());a=json.loads(((fixtures/'structural_audit.json') if fixtures.exists() else (root/'revision_furniture/mutation_tests03/baseline_intended_contacts/structural_audit.json')).read_text())
results=[]
with tempfile.TemporaryDirectory(prefix='r2s_contract_fixture_') as temp:
 p=Path(temp);(p/'fixture_view.txt').write_text('Contract fixture only. This is not a reconstruction evidence image.')
 for row in a['assemblies']:row['isolated_views']=['fixture_view.txt']
 a['evidence_hashes']={'fixture_view.txt':file_sha(p/'fixture_view.txt')}
 (p/'structural_audit.json').write_text(json.dumps(a));art=['fixture_view.txt','structural_audit.json']
 b=dict(model_sha256=a['source_model_sha256'],scene_sha256=a['source_scene_sha256'],structural_audit_sha256=file_sha(p/'structural_audit.json'))
 review=dict(geometry_freeze_sha256=b['model_sha256'],model_version=s['model_version'],per_object=[dict(entity=o['id'],status='pass',findings='Schema fixture, not real visual approval.',evidence=['fixture_view.txt']) for o in s['objects']],checks={'support':dict(status='pass',evidence=['fixture_view.txt'])})
 cases=[('valid_schema',lambda r:None,False),('missing_object',lambda r:r['per_object'].pop(),True),('wrong_evidence_reference',lambda r:r['per_object'][0].update(evidence=['missing.png']),True),('old_model_hash',lambda r:r.update(geometry_freeze_sha256='0'*64),True),('wrong_model_version',lambda r:r.update(model_version=3),True),('missing_object_status',lambda r:r['per_object'][0].pop('status'),True)]
 for name,mutate,reject in cases:
  r=copy.deepcopy(review);mutate(r)
  try:review_contract(p,r,art,s,b);actual=False;message='accepted'
  except ContractError as e:actual=True;message=str(e)
  assert actual==reject,(name,message);results.append(dict(test=name,rejected=actual,expected_rejected=reject,message=message))
 changed=copy.deepcopy(a);changed['failures']=[{'kind':'hidden_failure'}];(p/'structural_audit.json').write_text(json.dumps(changed))
 try:review_contract(p,review,art,s,b);raise AssertionError('modified executable audit accepted')
 except ContractError as e:results.append(dict(test='reviewer_modified_audit',rejected=True,message=str(e)))
 disconnected=copy.deepcopy(s['structure']);disconnected['assemblies'][0]['joints']=[]
 try:structure_contract(disconnected);raise AssertionError('disconnected graph accepted')
 except ContractError as e:results.append(dict(test='disconnected_declared_graph',rejected=True,message=str(e)))
report=dict(status='passed',scope='Contract fixtures only; real mesh tests are in mutation_test_results.json',tests=results);dest=root/'revision_furniture/contract_test_results.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
