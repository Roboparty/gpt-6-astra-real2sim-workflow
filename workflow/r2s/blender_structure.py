"""Measure actual evaluated furniture meshes and render isolated/combined evidence.
Inspection hides non-targets only while making diagnostic pictures; never saves that
visibility state as a model. Physical overlap checks use visible meshes, not proxies.
"""
import bpy,sys,json,hashlib,math,os
import numpy as np
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
args=sys.argv[sys.argv.index('--')+1:];scene_file=Path(args[0]);out=Path(args[1]);scene=json.loads(scene_file.read_text());structure=scene['structure']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=dict(schema='real2sim.structure-audit/1',source_model_sha256=sha(bpy.data.filepath),source_scene_sha256=sha(scene_file),model_version=scene['model_version'],evaluated_visible_meshes=True,method='Evaluated triangle BVHs, signed solid membership, world-space joint anchors and floor bounds; surface-intersection screening of all non-joint component pairs. No dynamics proxy is used.',assemblies=[],interassembly_checks=[],failures=[],evidence_hashes={})
deps=bpy.context.evaluated_depsgraph_get();meshes={};owners={}
assembly_entities={a['entity'] for a in structure['assemblies']}
declared_objects={p['object'] for a in structure['assemblies'] for p in a['parts']}
# A declared parts list is not proof that all visible furniture was audited.
# Dressing and accessories sharing an assembly owner need real support bindings
# too; otherwise a modeller could simply omit a detached/penetrating component.
for obj in bpy.context.scene.objects:
 owner=obj.get('entity_id',obj.get('furniture_id',obj.name))
 if owner in assembly_entities and obj.type in {'MESH','CURVE','SURFACE','FONT','META'} and not obj.hide_render and obj.name not in declared_objects:
  result['failures'].append(dict(kind='unbound_visible_assembly_geometry',entity=owner,object=obj.name))
result['visible_assembly_coverage_checked']=True
for a in structure['assemblies']:
 for part in a['parts']:
  o=bpy.data.objects.get(part['object'])
  if o is None or o.get('furniture_id')!=a['entity'] or o.get('part_id')!=part['id']:
   result['failures'].append(dict(kind='ownership',part=part));continue
  ev=o.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles();v=[o.matrix_world@x.co for x in me.vertices];tri=[tuple(t.vertices) for t in me.loop_triangles];bvh=BVHTree.FromPolygons(v,tri,all_triangles=True,epsilon=0)
  arr=np.array(v);meshes[o.name]=dict(tree=bvh,vertices=v,triangles=tri,lo=arr.min(axis=0),hi=arr.max(axis=0));owners[o.name]=a['entity'];ev.to_mesh_clear()
def solid_distance(mesh,point):
 p=Vector(point);near,normal,index,d=mesh['tree'].find_nearest(p)
 if near is None:return float('inf')
 # For closed consistently oriented surfaces, the closest triangle gives the
 # signed distance. Use ray parity only at an ambiguous tangential nearest edge;
 # repeated ray hits on nearly coincident bevel triangles are numerically fragile.
 if d<1e-6:return 0.
 side=(p-near).dot(normal)
 if abs(side)>1e-7:return -float(d) if side<0 else float(d)
 direction=Vector((.827,.379,.416)).normalized();origin=p.copy();hits=0
 for _ in range(128):
  hit,_,_,dist=mesh['tree'].ray_cast(origin,direction)
  if hit is None:break
  hits+=1;origin=hit+direction*1e-5
 return -float(d) if hits%2 else float(d)
for a in structure['assemblies']:
 names={p['id']:p['object'] for p in a['parts']};row=dict(entity=a['entity'],ownership_checked=all(n in meshes for n in names.values()),joints_checked=[],floor_checked=[],source_landmarks=a['fit']['landmarks'],isolated_views=[])
 for j in a['joints']:
  if any(names[p] not in meshes for p in j['parts']):continue
  ds=[max(0.,solid_distance(meshes[names[p]],j['anchor_world'])) for p in j['parts']];ok=max(ds)<=j['tolerance_m'];row['joints_checked'].append(dict(j,measured_anchor_outside_distances_m=ds,status='pass' if ok else 'fail'))
  if not ok:result['failures'].append(dict(kind='disconnected_joint',entity=a['entity'],joint=j['parts'],distances_m=ds))
 for f in a['floor_supports']:
  if names[f['part']] not in meshes:continue
  z=float(meshes[names[f['part']]]['lo'][2]);ok=abs(z-f['plane_z'])<=f['tolerance_m'];row['floor_checked'].append(dict(part=f['part'],actual_lowest_z_m=z,status='pass' if ok else 'fail'))
  if not ok:result['failures'].append(dict(kind='floor',entity=a['entity'],part=f['part'],z=z))
 # Bind every fitted correspondence to its owned evaluated part. Re-measure the
 # closest actual mesh point, not a copied residual from the parameter fitting file.
 cal=scene['camera'];R=np.array(cal['rotation_world_to_cv']);C=np.array(cal['position'])
 for lm in row['source_landmarks']:
  part=lm.get('part')
  if part not in names or names[part] not in meshes:
   result['failures'].append(dict(kind='unbound_source_landmark',entity=a['entity'],landmark=lm['id']));continue
  point,normal,index,distance=meshes[names[part]]['tree'].find_nearest(Vector(lm['world']))
  q=(np.array(point)-C)@R.T;uv=q[:2]/q[2]*cal['focal_px']+np.array(cal['principal_point']);lm.update(measured_world_point=list(point),distance_to_bound_mesh_m=float(distance),projected=uv.tolist(),error_px=float(np.linalg.norm(uv-lm['uv'])))
  if distance>.008:result['failures'].append(dict(kind='landmark_part_mismatch',entity=a['entity'],landmark=lm['id'],distance_m=float(distance)))
 errors=[v['error_px'] for v in row['source_landmarks']];limits=structure.get('acceptance',{'landmark_median_px':9,'landmark_max_px':18})
 row['landmark_median_px']=float(np.median(errors));row['landmark_max_px']=max(errors)
 if row['landmark_median_px']>limits['landmark_median_px'] or max(errors)>limits['landmark_max_px']:result['failures'].append(dict(kind='source_landmarks',entity=a['entity'],median=row['landmark_median_px'],maximum=max(errors)))
 result['assemblies'].append(row)
allowed=set()
for a in structure['assemblies']:
 names={p['id']:p['object'] for p in a['parts']}
 for j in a['joints']:allowed.add(tuple(sorted(names[p] for p in j['parts'])))
names=sorted(meshes);pairs=[]
for i,n in enumerate(names):
 for m in names[i+1:]:
  pair=(n,m);ma,mb=meshes[n],meshes[m];ov=np.minimum(ma['hi'],mb['hi'])-np.maximum(ma['lo'],mb['lo']);cross=owners[n]!=owners[m]
  record=dict(parts=list(pair),owners=[owners[n],owners[m]],expected_joint=pair in allowed,intersects=False,penetration_sample_m=0.)
  if np.min(ov)>.00001:
   overlaps=ma['tree'].overlap(mb['tree'])
   # Surface intersections plus containment catch both crossing and nested solids.
   candidate=[]
   if overlaps:
    for ia,ib in overlaps[:300]:
     for me,idx,other in [(ma,ia,mb),(mb,ib,ma)]:
      verts=[me['vertices'][v] for v in me['triangles'][idx]]
      for p in verts+[sum(verts,Vector())/3]:candidate.append(-solid_distance(other,p))
   else:
    candidate=[-solid_distance(mb,ma['vertices'][0]),-solid_distance(ma,mb['vertices'][0])]
   depth=max(candidate+[0.]);record.update(intersects=bool(overlaps) or depth>0,penetration_sample_m=depth)
   if pair not in allowed and depth>structure['unexpected_interpenetration_tolerance_m']:
    result['failures'].append(dict(kind='unexpected_interpenetration',parts=list(pair),depth_m=depth,cross_furniture=cross))
   elif pair not in allowed and overlaps and depth==0 and np.min(ov)>.01:
    # Ambiguous edge-only crossing must be reviewed, not silently called clear.
    record['requires_visual_intersection_review']=True
  pairs.append(record)
  if cross:result['interassembly_checks'].append(record)
result['component_pair_checks']=pairs
if os.environ.get('R2S_STRUCTURE_NO_RENDER')=='1':
 result['status']='passed' if not result['failures'] else 'failed';(out/'structural_audit.json').write_text(json.dumps(result,indent=2));print('STRUCTURE_RESULT',result['status'],json.dumps(result['failures']));sys.exit(0)
# Views, with coherent shapes exposed from angles unavailable in the source photo.
sc=bpy.context.scene;sourcecam=sc.camera;visibility={o.name:o.hide_render for o in bpy.data.objects};world_original=sc.world
sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True;sc.cycles.device='CPU' if os.environ.get('R2S_CPU')=='1' else 'GPU'
sc.render.resolution_percentage=100;sc.render.resolution_x=scene['camera']['image_size'][0];sc.render.resolution_y=scene['camera']['image_size'][1]
uv=np.array([x['uv'] for a in result['assemblies'] for x in a['source_landmarks']]);lo=np.floor(uv.min(axis=0)-30).astype(int);hi=np.ceil(uv.max(axis=0)+30).astype(int);W,H=scene['camera']['image_size'];lo=np.maximum(lo,0);hi=np.minimum(hi,[W,H]);result['source_crop_xyxy']=[*lo.tolist(),*hi.tolist()]
sc.render.use_border=True;sc.render.use_crop_to_border=True;sc.render.border_min_x=lo[0]/W;sc.render.border_max_x=hi[0]/W;sc.render.border_min_y=1-hi[1]/H;sc.render.border_max_y=1-lo[1]/H;sc.render.filepath=str(out/'furniture_source_view.png');bpy.ops.render.render(write_still=True);sc.render.use_border=False;sc.render.use_crop_to_border=False
sc.render.resolution_x=700;sc.render.resolution_y=700
world=bpy.data.worlds.new('structure_inspection_world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.8,.8,1);world.node_tree.nodes['Background'].inputs[1].default_value=.7;sc.world=world
bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='structure_inspection_camera';cam.data.type='ORTHO';sc.camera=cam
data=bpy.data.lights.new('structure_inspection_area','AREA');data.energy=500;data.shape='DISK';data.size=3;light=bpy.data.objects.new('structure_inspection_area',data);bpy.context.collection.objects.link(light)
for o in bpy.data.objects:
 if o.type=='LIGHT' and o!=light:o.hide_render=True
allparts=set(meshes)
groups=[(a['entity'],{p['object'] for p in a['parts']}) for a in structure['assemblies']]+[('combined',allparts)]
for entity,parts in groups:
 for o in bpy.data.objects:
  if o.type in ['MESH','CURVE']:o.hide_render=o.name not in parts
 lo=np.min([meshes[n]['lo'] for n in parts],axis=0);hi=np.max([meshes[n]['hi'] for n in parts],axis=0);center=(lo+hi)/2;span=max(hi-lo);cam.data.ortho_scale=span*1.55
 yaw=next((a['frame']['yaw_rad'] for a in structure['assemblies'] if a['entity']==entity),0)
 for label,delta in [('front',(1.7,-2.6,1.6)),('rear',(-1.7,2.6,1.5)),('side',(2.8,.3,1.1))]:
  dx,dy,dz=delta;offset=np.array([math.cos(yaw)*dx-math.sin(yaw)*dy,math.sin(yaw)*dx+math.cos(yaw)*dy,dz])*span;cam.location=center+offset;cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler();light.location=center+[-1,-2,3];light.rotation_euler=(Vector(center)-light.location).to_track_quat('-Z','Y').to_euler();name=f'structure_{entity}_{label}.png';sc.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
  if entity!='combined':next(a for a in result['assemblies'] if a['entity']==entity)['isolated_views'].append(name)
  else:result.setdefault('combined_views',[]).append(name)
for o in bpy.data.objects:
 if o.name in visibility:o.hide_render=visibility[o.name]
sc.camera=sourcecam;sc.world=world_original
result['status']='passed' if not result['failures'] else 'failed'
for p in out.glob('structure_*.png'):result['evidence_hashes'][p.name]=sha(p)
result['evidence_hashes']['furniture_source_view.png']=sha(out/'furniture_source_view.png')
(out/'structural_audit.json').write_text(json.dumps(result,indent=2));print('STRUCTURE_RESULT',result['status'],json.dumps(result['failures']))
