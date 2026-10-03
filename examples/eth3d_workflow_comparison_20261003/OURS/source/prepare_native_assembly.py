"""Measure intended component contacts; never edits model geometry or quality gates."""
import bpy,sys,json,math,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('/home/wqz/real2sim_agent_compare_20261003/OURS')
args=sys.argv[sys.argv.index('--')+1:];OUT=Path(args[0]);WRITE='--write' in args
S=json.loads((OUT/'scene.json').read_text());obsfile=R/'native_case/runs/agent_observe/0001/furniture_observation.json';obs=json.loads(obsfile.read_text())
def owner(o):
 a=o.get('entity_id',o.name);n=o.name
 if a=='wood_crates':return 'wood_crate_'+n[5]
 if a=='lime_skips':return 'lime_skip_'+n[4]
 if a=='mesh_cages':return 'mesh_cage_'+n[4]
 if a=='white_trailer' and n.startswith('flatbed'):return 'flatbed_trailer'
 return a
targets={o['entity'] for o in obs['targets']};deps=bpy.context.evaluated_depsgraph_get();M={};groups={}
for o in scobjects if False else list(bpy.context.scene.objects):
 a=owner(o)
 if o.type!='MESH' or a not in targets:continue
 ev=o.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles();v=[o.matrix_world@p.co for p in me.vertices];tri=[tuple(t.vertices) for t in me.loop_triangles];arr=np.array(v);tree=BVHTree.FromPolygons(v,tri,all_triangles=True)
 M[o.name]=dict(tree=tree,verts=arr,lo=arr.min(0),hi=arr.max(0),owner=a,obj=o);groups.setdefault(a,[]).append(o.name);ev.to_mesh_clear()
def distance(name,p):
 near,n,idx,d=M[name]['tree'].find_nearest(Vector(p))
 if near is None:return float('inf')
 return float(d) if (Vector(p)-near).dot(n)>0 else -float(d)
def contact(a,b):
 lo=np.maximum(M[a]['lo'],M[b]['lo']);hi=np.minimum(M[a]['hi'],M[b]['hi'])
 if np.min(hi-lo)<-.012:return None
 p=(lo+hi)/2
 for _ in range(16):
  ds=[max(0,distance(n,p)) for n in [a,b]]
  if max(ds)<=.009:return dict(parts=[a,b],anchor_world=p.tolist(),tolerance_m=.01,construction_basis='Intended adjacent components of the same observed assembly; actual evaluated mesh contact measured before declaration',outside_distances_m=ds)
  qa=M[a]['tree'].find_nearest(Vector(p))[0];qb=M[b]['tree'].find_nearest(qa)[0]
  candidates=[np.array(qa),np.array(qb),(np.array(qa)+np.array(qb))/2]
  p=min(candidates,key=lambda q:max(max(0,distance(a,q)),max(0,distance(b,q))))
 return None
fits={
'garage_door':(0,[[149,174],[110,745],[617,442]]),
'storage_rack':(8,[[626,127],[779,171],[621,462]]),
'wood_crate_0':(8,[[287,741],[608,675],[285,390]]),
'wood_crate_1':(8,[[208,385],[207,642]]),
'lime_skip_0':(8,[[119,357],[390,350],[145,552]]),
'lime_skip_1':(8,[[92,401],[109,482]]),
'white_trailer':(8,[[878,269],[873,414],[1092,419]]),
'flatbed_trailer':(8,[[758,488],[964,499]]),
'white_van':(12,[[361,311],[368,525],[112,472]]),
'black_car':(12,[[674,369],[691,469],[584,469]]),
'lumber_cart':(24,[[610,583],[780,581],[561,318],[797,318]]),
'mesh_cage_0':(28,[[577,423],[839,422],[842,631]]),
'mesh_cage_1':(28,[[937,421],[1185,431]]),
'mesh_cage_2':(20,[[220,290],[384,312]])}
assemblies=[];reports=[]
for a,names in groups.items():
 edges=[];graph={n:set() for n in names}
 for i,n in enumerate(names):
  for m in names[i+1:]:
   j=contact(n,m)
   if j:edges.append(j);graph[n].add(m);graph[m].add(n)
 comps=[];seen=set()
 for n in names:
  if n in seen:continue
  todo=[n];part=[]
  while todo:
   m=todo.pop()
   if m not in seen:seen.add(m);part.append(m);todo.extend(graph[m]-seen)
  comps.append(part)
 i,uvs=fits[a];cam=S['cameras'][i];C=np.array(cam['position']);RR=np.array(cam['rotation_world_to_cv']);ff=np.array([cam['focal_px'],cam['focal_y_px']]);pp=np.array(cam['principal_point']);landmarks=[]
 for k,uv in enumerate(uvs):
  best=None
  for name in names:
   verts=M[name]['verts'];q=(verts-C)@RR.T;valid=q[:,2]>.1
   if not valid.any():continue
   verts=verts[valid];q=q[valid];project=q[:,:2]/q[:,2,None]*ff+pp;err=np.linalg.norm(project-uv,axis=1);j=int(err.argmin())
   if best is None or err[j]<best[0]:best=(float(err[j]),name,verts[j].tolist(),project[j].tolist())
  landmarks.append(dict(id=a+'_observed_endpoint_'+str(k),part=best[1],world=best[2],uv=uv,frame_id=cam['frame_id'],input_index=i,source_sha256=cam['source_sha256'],association='Nearest actual component vertex to manually observed endpoint; errors retained, visual part semantics still require review',measured_initial_error_px=best[0]))
 lows=sorted([(float(M[n]['lo'][2]),n) for n in names]);supports=[dict(part=n,plane_z=0.,tolerance_m=.025) for z,n in lows if z<=max(.03,lows[0][0]+.006)]
 source_ids=[x['id'] for t in obs['targets'] if t['entity']==a for x in t['observations']]
 assembly=dict(entity=a,parts=[dict(id=n,object=n) for n in names],joints=edges,floor_supports=supports,source_observation_ids=source_ids,frame=dict(yaw_rad=0),fit=dict(frame_id=cam['frame_id'],landmarks=landmarks))
 assemblies.append(assembly);reports.append(dict(entity=a,parts=len(names),connected_components=len(comps),disconnected_groups=comps if len(comps)>1 else [],landmark_errors_px=[x['measured_initial_error_px'] for x in landmarks],lowest_z_m=lows[0][0]))
report=dict(status='connected' if all(r['connected_components']==1 for r in reports) else 'needs_structural_repair',assemblies=reports,source_model_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),note='Author contact preparation does not replace native structural audit or visual acceptance')
report['trailer_debug']={n:dict(lo=M[n]['lo'].tolist(),hi=M[n]['hi'].tolist()) for n in M if n in ['trailer_floor','trailer_towA','trailer_towB']}
(OUT/'contact_preparation_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
if WRITE:
 if report['status']!='connected':raise RuntimeError('Disconnected components: no fabricated joints or native pass will be written')
 for name,m in M.items():o=m['obj'];o['entity_id']=m['owner'];o['furniture_id']=m['owner'];o['part_id']=name
 # Split only semantic metadata: geometry bytes are unchanged in evaluated space.
 old={o['id']:o for o in S['objects']};new=[]
 for ent in old:
  if ent not in ['wood_crates','lime_skips','mesh_cages']:new.append(old[ent])
 for ent in targets:
  verts=np.concatenate([M[n]['verts'] for n in groups[ent]]);lo=verts.min(0);hi=verts.max(0)
  row=dict(id=ent,kind='semantic_assembly',position=((lo+hi)/2).tolist(),dimensions=(hi-lo).tolist(),evidence=['source_observation','measurement_raw.json'],confidence=.7,layout_lock=True,asset_resolution=dict(mode='custom_A'))
  new=[o for o in new if o['id']!=ent];new.append(row)
 S['objects']=new;S['structure']=dict(schema='real2sim.assembly/1',observation_sha256=hashlib.sha256(obsfile.read_bytes()).hexdigest(),assemblies=assemblies,acceptance=dict(landmark_median_px=9,landmark_max_px=18),unexpected_interpenetration_tolerance_m=.008)
 (OUT/'scene.json').write_text(json.dumps(S,indent=2));(OUT/'furniture_observation.json').write_bytes(obsfile.read_bytes());bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model.blend'))
