import bpy,json,pathlib,numpy as np,hashlib
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=pathlib.Path(__file__).resolve().parents[1];before=hashlib.sha256((R/'scene.blend').read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(R/'scene.blend'));graph=bpy.context.evaluated_depsgraph_get();vs=[];fs=[];names=[]
for obj in bpy.context.scene.objects:
 if obj.type!='MESH' or obj.hide_render or obj.get('exclude_from_evaluation'):continue
 e=obj.evaluated_get(graph);m=e.to_mesh();m.calc_loop_triangles();off=len(vs);vs.extend(obj.matrix_world@v.co for v in m.vertices)
 for t in m.loop_triangles:fs.append(tuple(off+i for i in t.vertices));names.append(obj.name)
 e.to_mesh_clear()
tree=BVHTree.FromPolygons(vs,fs,all_triangles=True);target=bpy.data.objects['delivery_truck__windshield'];target.data.calc_loop_triangles();targets=[sum((target.matrix_world@target.data.vertices[i].co for i in tri.vertices),Vector())/3 for tri in target.data.loop_triangles];P=json.load(open(R/'inputs/packet.json'));X=np.array(json.load(open(R/'model_from_input.json'))['model_from_input']);rows=[]
for i in [12,13]:
 T=X@np.array(P['frames'][i]['T_world_camera']);origin=Vector(T[:3,3]);hits=[]
 for pt in targets:
  d=pt-origin;dist=d.length;hit=tree.ray_cast(origin,d.normalized(),dist+.02);hits.append({'target_distance_m':dist,'first_hit_distance_m':hit[3],'first_hit_object':names[hit[2]] if hit[2] is not None else None,'glass_first':hit[2] is not None and names[hit[2]]==target.name})
 rows.append({'frame':i,'rays':hits,'all_glass_first':all(k['glass_first'] for k in hits)})
passed=all(r['all_glass_first'] for r in rows);out={'version':2,'model_sha256':before,'frames':rows,'passed':passed,'scope':'visible mesh BVH triangle-centre rays at own mapping12/13; no renders, no full depth pass, no GT; does not certify entire window silhouette'};(R/'analysis/v2_windshield_visibility.json').write_text(json.dumps(out,indent=2));assert hashlib.sha256((R/'scene.blend').read_bytes()).hexdigest()==before;print(json.dumps(out,indent=2));assert passed
