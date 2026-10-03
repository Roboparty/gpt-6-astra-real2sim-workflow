from pathlib import Path
import subprocess,json,sys,hashlib,ast
r=Path(__file__).resolve().parent;source=r/'source';cases=[]
for label,flag in [('bounds_only',{'bounds_only':True}),('nonrectangular',{'nonrectangular_topology':True}),('topology',{'topology':'orthogonal_union'}),('mesh_policy',{'collision_policy':'mesh_only'})]:
 for entity_case in ['empty_audit','renamed_shell']:
  out=r/f'{label}_{entity_case}';out.mkdir(exist_ok=True)
  room=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3,thickness=.1,**flag)
  scene={'case_id':'review_synthetic','branch':'A','room':room,'objects':[]}
  (out/'scene.json').write_text(json.dumps(scene));entities={} if entity_case=='empty_audit' else {'not_a_canonical_surface':{'local_aabb':[[-2,-2,0],[2,2,3]],'root_position':[0,0,0],'root_quaternion_wxyz':[1,0,0,0]}}
  (out/'geometry_audit.json').write_text(json.dumps({'entities':entities}));p=subprocess.run([sys.executable,str(source/'simulation.py'),str(out/'scene.json'),str(out)],capture_output=True,text=True)
  denied=p.returncode!=0 and 'canonical rectangle fallback is forbidden' in p.stderr
  forbidden_outputs=[name for name in ['scene.xml','collision_recipes.json','simulation_audit.json','probe_test.xml'] if (out/name).exists()]
  cases.append(dict(declaration=label,entity_case=entity_case,returncode=p.returncode,denied_by_room_guard=denied,forbidden_outputs=forbidden_outputs));(out/'stderr.txt').write_text(p.stderr)
# Inspect actual top-level ordering, independently of the shell_boxes helper tests.
tree=ast.parse((source/'simulation.py').read_text());guard=next(n.lineno for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id',None)=='require_canonical_room');root=next(n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and getattr(n.func,'id',None)=='Element')
result=dict(status='PASS' if all(x['denied_by_room_guard'] and not x['forbidden_outputs'] for x in cases) and guard<root else 'FAIL',cases=cases,scope='Eight fresh subprocess tests of actual simulation.py entrypoint using installed MuJoCo runtime, not function-only mocks; canonical old regressions not duplicated.',guard_line=guard,first_XML_root_line=root,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')},limitations=['Requires the scene to retain the nonrectangular/bounds-only declaration under room; geometry alone is not automatically recognized.','This intentionally refuses native MJCF export; it does not implement or validate nonrectangular mesh collision.','Generic custom-object AABB fallback remains for scenes not declared nonrectangular; final nonrectangular candidates must carry the room guard metadata.'])
(r/'entrypoint_guard_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
