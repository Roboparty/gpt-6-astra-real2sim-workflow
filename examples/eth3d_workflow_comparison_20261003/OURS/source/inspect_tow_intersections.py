import bpy,json,hashlib
import numpy as np
from pathlib import Path
R=Path('/home/wqz/real2sim_agent_compare_20261003/OURS');out={};deps=bpy.context.evaluated_depsgraph_get()
for name in ['flatbed_deck','trailer_towA','trailer_towB']:
 o=bpy.data.objects[name];ev=o.evaluated_get(deps);m=ev.to_mesh();m.calc_loop_triangles();v=np.array([o.matrix_world@p.co for p in m.vertices]);f=np.array([tuple(t.vertices) for t in m.loop_triangles]);edges={}
 for tri in f:
  for a,b in zip(tri,np.roll(tri,-1)):
   key=tuple(sorted([int(a),int(b)]));edges.setdefault(key,[]).append([int(a),int(b)])
 volume=float(np.sum(np.einsum('ij,ij->i',v[f[:,0]],np.cross(v[f[:,1]],v[f[:,2]])))/6)
 out[name]=dict(vertices=v.tolist(),faces=f.tolist(),closed=all(len(x)==2 for x in edges.values()),consistently_wound=all(len(x)==2 and x[0]==list(reversed(x[1])) for x in edges.values()),signed_volume_m3=volume,lo=v.min(0).tolist(),hi=v.max(0).tolist())
 ev.to_mesh_clear()
(R/'models/v2/tow_mesh_evidence.json').write_text(json.dumps(dict(source_model_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),objects=out),indent=2))
