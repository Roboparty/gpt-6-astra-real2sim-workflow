import bpy,json,hashlib,sys,argparse
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser();p.add_argument('--repair-root',type=Path,default=Path('/home/wqz/real2sim_agent_repair_20261003/geometry'));p.add_argument('--candidate',default='candidate_v4');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);R=a.repair_root;O=R/a.candidate;S=json.loads((O/'scene.json').read_text());rows=[];trees={};deps=bpy.context.evaluated_depsgraph_get()
for name in ['floor','ceiling','wall_front','wall_back','wall_left','wall_right']:
 o=bpy.data.objects[name];ev=o.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();v=[o.matrix_world@p.co for p in m.vertices];f=[tuple(t.vertices) for t in m.loop_triangles];edges={}
 for tri in f:
  for a,b in zip(tri,(tri[1],tri[2],tri[0])):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
 faces={}
 for p in m.polygons:faces.setdefault(tuple(sorted(p.vertices)),0);faces[tuple(sorted(p.vertices))]+=1
 volume=sum(v[a].dot(v[b].cross(v[c])) for a,b,c in f)/6
 trees[name]=BVHTree.FromPolygons(v,f,all_triangles=True)
 rows.append(dict(shell=name,closed_manifold=all(len(e)==2 for e in edges.values()),consistent_winding=all(len(e)==2 and e[0]==tuple(reversed(e[1])) for e in edges.values()),duplicate_faces=sum(n-1 for n in faces.values()),signed_volume_m3=volume));ev.to_mesh_clear()
hits=[]
for seg in S['room']['boundary_segments']:
 a,b=Vector((*seg['a'],0)),Vector((*seg['b'],0));mid=(a+b)/2;name=seg['shell'];normal={'wall_front':Vector((0,-1,0)),'wall_back':Vector((0,1,0)),'wall_left':Vector((-1,0,0)),'wall_right':Vector((1,0,0))}[name]
 for z in [.5,2.,4.5]:
  mid.z=z;origin=mid-normal*.08;hit=trees[name].ray_cast(origin,normal,.5)[0];expected=z>=seg['z_min'];hits.append(dict(shell=name,xy=list(mid)[:2],z=z,expected_shell=expected,actual_shell=hit is not None,pass_check=(hit is not None)==expected))
floor=S['room']['topology_regions'];xs=sorted(set(x for r in floor for x in r['bounds'][:2]));ys=sorted(set(y for r in floor for y in r['bounds'][2:]));floorchecks=[]
for i in range(len(xs)-1):
 for j in range(len(ys)-1):
  x=(xs[i]+xs[i+1])/2;y=(ys[j]+ys[j+1])/2;inside=any(a<=x<=b and c<=y<=d for a,b,c,d in [r['bounds'] for r in floor]);got=trees['floor'].ray_cast(Vector((x,y,1)),Vector((0,0,-1)),2)[0] is not None;floorchecks.append(dict(x=x,y=y,expected=inside,actual=got,pass_check=inside==got))
report=dict(status='passed' if all(r['closed_manifold'] and r['consistent_winding'] and not r['duplicate_faces'] and r['signed_volume_m3']>0 for r in rows) and all(r['pass_check'] for r in hits+floorchecks) else 'failed',model_sha256=hashlib.sha256((O/'model.blend').read_bytes()).hexdigest(),shells=rows,boundary_ray_checks=hits,floor_coverage_checks=floorchecks,native_simulation='unsupported/refused by bounds-only guard',scope='Actual generated shell topology, aperture and floor-union coverage; not full-scene collision or source visual acceptance')
(O/'shell_surface_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['boundary_ray_checks','floor_coverage_checks']},indent=2))
