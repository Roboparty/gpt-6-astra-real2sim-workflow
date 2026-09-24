"""Compare evaluated non-furniture geometry/camera between this task's two candidates."""
import bpy,sys,hashlib,json
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:];excluded={'table','chair_near','chair_far','chair_near_cushion','chair_far_cushion'}
def read(path):
 bpy.ops.wm.open_mainfile(filepath=str(path));deps=bpy.context.evaluated_depsgraph_get();items={}
 for o in sorted(bpy.data.objects,key=lambda o:o.name):
  if o.get('entity_id') in excluded or o.type not in ['MESH','CURVE','CAMERA']:continue
  data=[o.name,o.type]
  if o.type=='CAMERA':data.extend([list(x) for x in o.matrix_world]);data.extend([o.data.lens,o.data.shift_x,o.data.shift_y])
  else:
   ev=o.evaluated_get(deps);me=ev.to_mesh();data.extend([[list(o.matrix_world@v.co) for v in me.vertices],[list(p.vertices) for p in me.polygons]]);ev.to_mesh_clear()
  items[o.name]=hashlib.sha256(json.dumps(data).encode()).hexdigest()
 return items
a,b=read(args[0]),read(args[1]);diff=[n for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)];result=dict(status='passed' if not diff else 'failed',excluded_entities=sorted(excluded),evaluated_objects_compared=len(a),changed=diff,method='Exact evaluated world-geometry and source-camera hashes, excluding explicitly revised furniture entities.')
Path(args[2]).write_text(json.dumps(result,indent=2));assert not diff,diff;print(json.dumps(result))
