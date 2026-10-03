from pathlib import Path
import bpy,numpy as np,json,sys,hashlib,time
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
r=Path('/data/wqz/real2sim-agent-compare-20261003/comparison');t=Path('/data/wqz/real2sim-awsm-20261003/eth3d/benchmark_v1/evaluation');out=r/'audit';sys.path.insert(0,'/data/wqz/real2sim-agent-compare-20261003/reference_prep/evaluator_review')
from render_visibility import render_members,include_instance
f=np.load(t/'truth_grid.npz');truth=f['depth'];rays=f['rays'];poses=f['poses'];laser=np.load(t/'laser_sample.npy');start=time.monotonic()
for method in ['OURS','AWSM']:
 freeze=json.loads((r/'freeze'/f'{method}.json').read_text());G=np.array(freeze['model_from_input']);inverse=np.linalg.inv(G);bpy.ops.wm.open_mainfile(filepath=str(r/'models'/method/'scene.blend'),load_ui=False,use_scripts=False);bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();members=render_members(bpy.context.scene);vertices=[];inputv=[];faces=[];owners=[];records=[]
 for instance in graph.object_instances:
  if not include_instance(instance,members):continue
  obj=instance.object;mesh=obj.to_mesh();mesh.calc_loop_triangles();offset=len(vertices);vm=[instance.matrix_world@v.co for v in mesh.vertices];vi=[(Matrix(inverse.tolist())@instance.matrix_world)@v.co for v in mesh.vertices];vertices.extend(vm);inputv.extend(vi);faces.extend(tuple(offset+i for i in tri.vertices) for tri in mesh.loop_triangles);owners.extend([obj.original.name]*len(mesh.loop_triangles));records.append(dict(name=obj.original.name,vertices=len(vm),triangles=len(mesh.loop_triangles)));obj.to_mesh_clear()
 tree=BVHTree.FromPolygons(vertices,faces,all_triangles=True);saved=np.load(r/'evaluation'/method/'rendered_z.npy');recalc=np.full(saved.shape,np.nan)
 for i,(T,ray,domain) in enumerate(zip(poses,rays,np.isfinite(truth))):
  Tm=G@T;origin=Vector(Tm[:3,3]);directions=ray@Tm[:3,:3].T;length=np.linalg.norm(directions,axis=1)
  for j in np.flatnonzero(domain):
   hit,_,_,distance=tree.ray_cast(origin,Vector(directions[j]/length[j]),30*length[j])
   if hit is not None:recalc[i,j]=distance/length[j]
 samevalid=np.array_equal(np.isfinite(recalc),np.isfinite(saved));good=np.isfinite(recalc)&np.isfinite(saved);delta=np.abs(recalc[good]-saved[good]);back=[]
 for point in laser:
  q=(G@np.r_[point,1])[:3];hit,_,_,dist=tree.find_nearest(Vector(q));back.append(float(dist) if dist is not None else np.nan)
 oldback=np.load(r/'evaluation'/method/'gt_to_model_m.npy');bd=np.abs(np.array(back)-oldback)
 xyz=np.array(inputv);tri=xyz[np.array(faces)];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2;rng=np.random.default_rng(20261003);chosen=rng.choice(len(faces),100000,p=area/area.sum());r1=np.sqrt(rng.random(100000));r2=rng.random(100000);samples=((1-r1[:,None])*tri[chosen,0]+(r1*(1-r2))[:,None]*tri[chosen,1]+(r1*r2)[:,None]*tri[chosen,2]).astype(np.float32);old=np.load(r/'evaluation'/method/'model_surface_samples.npy');owner=np.asarray(owners)[chosen];np.save(out/f'{method}_sample_owners.npy',owner)
 result=dict(method=method,depth_valid_masks_identical=samevalid,depth_compared_positions=int(good.sum()),depth_max_difference_m=float(delta.max()),depth_mean_difference_m=float(delta.mean()),depth_differences_over_1mm=int((delta>.001).sum()),laser_nearest_compared=len(back),laser_nearest_max_difference_m=float(bd.max()),laser_nearest_mean_difference_m=float(bd.mean()),laser_nearest_differences_over_1mm=int((bd>.001).sum()),sample_regeneration_byte_identical=np.array_equal(samples,old),sample_regeneration_max_difference_m=float(abs(samples-old).max()),area_total_m2=float(area.sum()),unique_visible_objects=len(records),seconds=time.monotonic()-start,verification_convention='Independent model-coordinate BVH queries: transform INPUT camera/laser points forward by G; evaluator used inverseG geometry in INPUT gauge. Transparent faces remain opaque for geometry. No model writes.')
 (out/f'{method}_blender_requery.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
